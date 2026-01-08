#!/usr/bin/env python3
"""Discord sync tool - Sync messages from Discord to local storage.

Usage:
    python tools/discord_sync.py                       # Quick sync (first run) or incremental
    python tools/discord_sync.py --quick              # Force quick mode (~200 msgs/channel)
    python tools/discord_sync.py --full               # Full historical sync
    python tools/discord_sync.py --fill-gaps          # Fill missing date ranges
    python tools/discord_sync.py --since 2024-01-01   # Sync from specific date
    python tools/discord_sync.py --server SERVER_ID
    python tools/discord_sync.py --channel CHANNEL_ID --days 7
"""

import argparse
import asyncio
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import discord

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.discord_client import (
    DiscordUserClient,
    DiscordClientError,
    AuthenticationError
)
from lib.storage import get_storage, SyncMode
from lib.parallel_sync import ParallelSyncOrchestrator, SyncSummary
from lib.rate_limiter import format_duration
from lib.global_rate_limiter import GlobalRateLimiter
from lib.multi_server_sync import MultiServerSyncOrchestrator


async def sync_channel(
    client: DiscordUserClient,
    storage,
    server_id: str,
    server_name: str,
    channel_id: str,
    channel_name: str,
    days: int,
    incremental: bool,
    max_messages: int = 200
) -> int:
    """Sync messages from a single channel.

    Returns:
        Number of messages synced
    """
    # Get last message ID for incremental sync
    after_id = None
    if incremental:
        after_id = storage.get_last_message_id(server_id, channel_name)
        if after_id:
            print(f"  Incremental sync from message {after_id}")

    # Fetch messages (with limit)
    messages = []
    async for msg in client.fetch_messages(
        server_id=server_id,
        channel_id=channel_id,
        after_id=after_id,
        days=days,
        limit=max_messages
    ):
        messages.append(msg)
        if len(messages) % 50 == 0:
            print(f"  Fetched {len(messages)} messages...")
        if len(messages) >= max_messages:
            print(f"  Reached limit of {max_messages} messages")
            break

    if not messages:
        print(f"  No new messages to sync")
        return 0

    # Save messages to storage
    storage.append_messages(
        server_id=server_id,
        server_name=server_name,
        channel_id=channel_id,
        channel_name=channel_name,
        messages=messages
    )

    # Save channel metadata
    storage.save_channel_metadata(
        server_id=server_id,
        channel_id=channel_id,
        channel_name=channel_name,
        server_name=server_name
    )

    print(f"  Synced {len(messages)} messages")
    return len(messages)


async def sync_single_server(
    client: DiscordUserClient,
    storage,
    config,
    server_info: dict,
    channel_id: Optional[str],
    days: int,
    incremental: bool
) -> int:
    """Sync messages from a single server. Returns total messages synced."""
    server_id = server_info["id"]
    server_name = server_info["name"]
    print(f"\n{'='*50}")
    print(f"Syncing: {server_name} ({server_id})")

    # Save server metadata
    storage.save_server_metadata(
        server_id=server_id,
        server_name=server_name,
        icon=server_info.get("icon"),
        member_count=server_info.get("member_count", 0)
    )

    # Get channels to sync (with access check)
    all_channels = await client.list_channels(server_id, check_access=True)

    # Get sync limits from config
    max_channels = config.max_channels_per_server
    max_messages = config.max_messages_per_channel
    priority_channels = config.priority_channels

    if channel_id:
        # Sync specific channel
        channel_info = next(
            (c for c in all_channels if c["id"] == channel_id),
            None
        )
        if not channel_info:
            print(f"Error: Channel {channel_id} not found in server")
            return 0

        channels_to_sync = [channel_info]
    else:
        # Filter out inaccessible channels first
        accessible_channels = [c for c in all_channels if c.get("accessible", True)]
        inaccessible_count = len(all_channels) - len(accessible_channels)

        if inaccessible_count > 0:
            print(f"Skipping {inaccessible_count} inaccessible channel(s)")

        # Channels with active discussions (prioritized)
        discussion_keywords = ["general", "chat", "discussion", "help", "lounge", "off-topic", "talk", "main"]
        # Channels that typically have static/read-only content (deprioritized)
        static_keywords = ["rules", "guidelines", "welcome", "verify", "readme", "announcements", "info", "faq"]

        # Sort channels: user priority first, then discussion channels, then by position
        def channel_sort_key(ch):
            name = ch.get("name", "").lower()
            # Remove common emoji/special char prefixes for matching
            clean_name = name.lstrip("0123456789-_|｜#🎉📢🔔📋📜👋✨")

            # User-configured priority channels get highest priority
            if clean_name in [p.lower() for p in priority_channels]:
                return -2000 + [p.lower() for p in priority_channels].index(clean_name)

            # Discussion channels get second priority
            if any(kw in clean_name for kw in discussion_keywords):
                # Prefer exact matches like "general" over partial like "general-offtopic"
                if clean_name in discussion_keywords:
                    return -1000 + discussion_keywords.index(clean_name)
                return -500 + ch.get("position", 999)

            # Static/read-only channels get lowest priority
            if any(kw in clean_name for kw in static_keywords):
                return 2000 + ch.get("position", 999)

            # Everything else sorted by position
            return ch.get("position", 999)

        sorted_channels = sorted(accessible_channels, key=channel_sort_key)

        # Limit to max channels
        channels_to_sync = sorted_channels[:max_channels]

        if len(accessible_channels) > max_channels:
            print(f"Limiting to top {max_channels} channels (of {len(accessible_channels)} accessible)")

    print(f"Syncing {len(channels_to_sync)} channel(s) (max {max_messages} msgs each)...")

    total_messages = 0
    failed_channels = []
    for channel in channels_to_sync:
        print(f"  #{channel['name']}:", end=" ")
        try:
            count = await sync_channel(
                client=client,
                storage=storage,
                server_id=server_id,
                server_name=server_name,
                channel_id=channel["id"],
                channel_name=channel["name"],
                days=days,
                incremental=incremental,
                max_messages=max_messages
            )
            total_messages += count
        except (DiscordClientError, discord.Forbidden, discord.HTTPException) as e:
            print(f"Error: {e}")
            failed_channels.append(channel['name'])
            continue

    if failed_channels:
        print(f"  Warning: {len(failed_channels)} channel(s) failed")

    return total_messages


async def sync_all_servers(
    days: int,
    incremental: bool,
    limit: Optional[int] = 200,
    fill_gaps: bool = False,
    since_date: Optional[date] = None,
    use_parallel: bool = True
) -> None:
    """Sync messages from ALL servers.

    Args:
        days: Number of days of history to fetch.
        incremental: Whether to do incremental sync.
        limit: Max messages per channel (None for unlimited).
        fill_gaps: If True, fill missing date ranges.
        since_date: If set, fetch messages from this date onward.
        use_parallel: If True, use parallel channel syncing.
    """
    client = DiscordUserClient()
    storage = get_storage()

    try:
        # Check if first sync
        manifest = storage.get_manifest()
        is_first_sync = not manifest.get("servers")
        if is_first_sync and limit:
            print("First sync detected - limiting to recent messages for speed")
            print("(Run with --full later to fetch complete history)\n")

        print("Fetching your Discord servers...")
        guilds = await client.list_guilds()

        if not guilds:
            print("No servers found in your Discord account.")
            sys.exit(1)

        mode_str = "Full" if not limit else ("Gap Fill" if fill_gaps else f"Limited ({limit}/channel)")
        print(f"Found {len(guilds)} server(s). {mode_str} sync, last {days} day(s)...")

        # Use multi-server parallel sync for faster performance
        rate_limiter = GlobalRateLimiter(
            max_concurrent=10,
            requests_per_second=40.0,
        )

        orchestrator = MultiServerSyncOrchestrator(
            client=client,
            storage=storage,
            global_rate_limiter=rate_limiter,
            max_servers_parallel=5,
            max_channels_parallel=10,
            progress_callback=print,
        )

        await orchestrator.sync_all_servers(
            servers=guilds,
            days=days,
            limit=limit,
            incremental=incremental,
        )

        # Update manifest
        manifest = storage.update_manifest()

        print(f"\nManifest: {manifest['summary']['total_servers']} servers, "
              f"{manifest['summary']['total_channels']} channels, "
              f"{manifest['summary']['total_messages']} messages")

    finally:
        await client.close()


async def sync_server(
    server_id: str,
    channel_id: Optional[str],
    days: int,
    incremental: bool,
    limit: Optional[int] = 200,
    fill_gaps: bool = False,
    since_date: Optional[date] = None,
    use_parallel: bool = True
) -> None:
    """Sync messages from a specific server.

    Args:
        server_id: Discord server ID to sync.
        channel_id: Optional specific channel ID to sync.
        days: Number of days of history to fetch.
        incremental: Whether to do incremental sync.
        limit: Max messages per channel (None for unlimited).
        fill_gaps: If True, fill missing date ranges.
        since_date: If set, fetch messages from this date onward.
        use_parallel: If True, use parallel channel syncing.
    """
    config = get_config()
    client = DiscordUserClient()
    storage = get_storage()

    try:
        # Get server info
        guilds = await client.list_guilds()
        server_info = next(
            (g for g in guilds if g["id"] == server_id),
            None
        )

        if not server_info:
            print(f"Error: Server {server_id} not found or not accessible")
            sys.exit(1)

        server_name = server_info["name"]
        print(f"Syncing from: {server_name} ({server_id})")

        # Save server metadata
        storage.save_server_metadata(
            server_id=server_id,
            server_name=server_name,
            icon=server_info.get("icon"),
            member_count=server_info.get("member_count", 0)
        )

        # Get channels to sync (with access check)
        all_channels = await client.list_channels(server_id, check_access=True)

        # Get sync limits from config
        max_channels = config.max_channels_per_server
        max_messages = config.max_messages_per_channel
        priority_channels = config.priority_channels

        if channel_id:
            # Sync specific channel
            channel_info = next(
                (c for c in all_channels if c["id"] == channel_id),
                None
            )
            if not channel_info:
                print(f"Error: Channel {channel_id} not found in server")
                sys.exit(1)

            # Check if accessible
            if not channel_info.get("accessible", True):
                print(f"Warning: Channel #{channel_info['name']} is not accessible (missing permissions)")

            channels_to_sync = [channel_info]
        else:
            # Filter out inaccessible channels first
            accessible_channels = [c for c in all_channels if c.get("accessible", True)]
            inaccessible_count = len(all_channels) - len(accessible_channels)

            if inaccessible_count > 0:
                print(f"Skipping {inaccessible_count} inaccessible channel(s)")

            # Channels with active discussions (prioritized)
            discussion_keywords = ["general", "chat", "discussion", "help", "lounge", "off-topic", "talk", "main"]
            # Channels that typically have static/read-only content (deprioritized)
            static_keywords = ["rules", "guidelines", "welcome", "verify", "readme", "announcements", "info", "faq"]

            # Sort channels: user priority first, then discussion channels, then by position
            def channel_sort_key(ch):
                name = ch.get("name", "").lower()
                # Remove common emoji/special char prefixes for matching
                clean_name = name.lstrip("0123456789-_|｜#🎉📢🔔📋📜👋✨")

                # User-configured priority channels get highest priority
                if clean_name in [p.lower() for p in priority_channels]:
                    return -2000 + [p.lower() for p in priority_channels].index(clean_name)

                # Discussion channels get second priority
                if any(kw in clean_name for kw in discussion_keywords):
                    # Prefer exact matches like "general" over partial like "general-offtopic"
                    if clean_name in discussion_keywords:
                        return -1000 + discussion_keywords.index(clean_name)
                    return -500 + ch.get("position", 999)

                # Static/read-only channels get lowest priority
                if any(kw in clean_name for kw in static_keywords):
                    return 2000 + ch.get("position", 999)

                # Everything else sorted by position
                return ch.get("position", 999)

            sorted_channels = sorted(accessible_channels, key=channel_sort_key)

            # Limit to max channels
            channels_to_sync = sorted_channels[:max_channels]

            if len(accessible_channels) > max_channels:
                print(f"Limiting to top {max_channels} channels (of {len(accessible_channels)} accessible)")
                print(f"  To sync more, set sync_limits.max_channels_per_server in config/server.yaml")

        # Determine effective limit
        effective_limit = limit if limit else max_messages
        mode_str = "Full" if not limit else ("Gap Fill" if fill_gaps else f"Limited ({limit}/channel)")
        print(f"{mode_str} sync: {len(channels_to_sync)} channel(s) (max {effective_limit} msgs each)...")

        # Use parallel sync if enabled and multiple channels
        if use_parallel and len(channels_to_sync) > 1:
            orchestrator = ParallelSyncOrchestrator(
                client=client,
                storage=storage,
                server_id=server_id,
                server_name=server_name,
                quick_mode=bool(limit),
                quick_limit=limit or 200,
                days=days,
                incremental=incremental,
                fill_gaps=fill_gaps,
                since_date=since_date,
            )

            summary = await orchestrator.sync_all_channels(
                channels=channels_to_sync,
                max_messages_per_channel=effective_limit,
            )

            # Update manifest
            manifest = storage.update_manifest()

            # Print formatted summary
            is_first = not storage.has_any_sync(server_id)
            print(format_summary(summary, is_first_sync=is_first))

        else:
            # Sequential sync (single channel or parallel disabled)
            total_messages = 0
            failed_channels = []
            for channel in channels_to_sync:
                print(f"\n#{channel['name']}:")
                try:
                    count = await sync_channel(
                        client=client,
                        storage=storage,
                        server_id=server_id,
                        server_name=server_name,
                        channel_id=channel["id"],
                        channel_name=channel["name"],
                        days=days,
                        incremental=incremental,
                        max_messages=effective_limit
                    )
                    total_messages += count
                except (DiscordClientError, discord.Forbidden, discord.HTTPException) as e:
                    print(f"  Error: {e}")
                    failed_channels.append(channel['name'])
                    continue

            # Report failed channels if any
            if failed_channels:
                print(f"\nWarning: {len(failed_channels)} channel(s) failed to sync:")
                for ch in failed_channels:
                    print(f"  - #{ch}")

            # Update manifest with all synced data
            manifest = storage.update_manifest()

            # Print summary
            data_dir = config.get_server_data_dir(server_id)

            print(f"\n{'='*50}")
            print(f"Sync complete!")
            print(f"Total messages: {total_messages}")
            print(f"Data location: {data_dir}")
            print(f"Manifest: {config.data_dir}/manifest.yaml")
            print(f"\nOverall: {manifest['summary']['total_servers']} servers, "
                  f"{manifest['summary']['total_channels']} channels, "
                  f"{manifest['summary']['total_messages']} messages")

    finally:
        await client.close()


def is_interactive() -> bool:
    """Check if running in an interactive terminal."""
    return sys.stdin.isatty()


def prompt_for_full_sync(estimated_time_seconds: float) -> bool:
    """Prompt user for full sync decision.

    Args:
        estimated_time_seconds: Estimated time for full sync.

    Returns:
        True if user wants full sync, False otherwise.
    """
    if not is_interactive():
        print("Non-interactive mode: skipping full sync prompt. Use --full to force.")
        return False

    try:
        time_str = format_duration(estimated_time_seconds)
        response = input(
            f"\nEstimated time for full sync: ~{time_str}\n"
            f"Would you like to fetch complete historical data? [y/N]: "
        ).strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return False


def format_summary(summary: SyncSummary, is_first_sync: bool = False) -> str:
    """Format a sync summary for display.

    Args:
        summary: SyncSummary object.
        is_first_sync: If this was the first sync (show full sync prompt hint).

    Returns:
        Formatted summary string.
    """
    lines = [
        "",
        "=" * 50,
        f"{'Quick Sync' if summary.sync_mode == SyncMode.QUICK else 'Sync'} Complete",
        "=" * 50,
        "",
        f"  Messages fetched: {summary.total_messages:,}",
        f"  Channels synced:  {summary.channels_processed}",
    ]

    if summary.channels_skipped > 0:
        lines.append(f"  Channels skipped: {summary.channels_skipped} (already synced)")

    lines.append(f"  Time elapsed:     {format_duration(summary.duration_seconds)}")

    if summary.channels_with_new_messages:
        lines.append("")
        lines.append("  Channels with new messages:")
        for ch in summary.channels_with_new_messages[:5]:
            lines.append(f"    - #{ch}")
        if len(summary.channels_with_new_messages) > 5:
            lines.append(f"    ... and {len(summary.channels_with_new_messages) - 5} more")

    if summary.errors:
        lines.append("")
        lines.append(f"  Errors: {len(summary.errors)}")
        for err in summary.errors[:3]:
            lines.append(f"    - {err}")

    lines.append("=" * 50)
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Sync Discord messages to local storage"
    )

    parser.add_argument(
        "--server",
        metavar="SERVER_ID",
        help="Server ID to sync (uses config default if not specified)"
    )
    parser.add_argument(
        "--channel",
        metavar="CHANNEL_ID",
        help="Specific channel ID to sync (syncs all channels if not specified)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days of history to fetch (default: 7)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full sync - fetch all messages (no limit per channel)"
    )
    parser.add_argument(
        "--fill-gaps",
        action="store_true",
        help="Fill missing date ranges without re-fetching existing data"
    )
    parser.add_argument(
        "--since",
        type=str,
        metavar="DATE",
        help="Fetch messages from this date (YYYY-MM-DD) to present"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max messages per channel (default: 200, use --full for unlimited)"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Use parallel channel syncing (default: True)"
    )

    args = parser.parse_args()

    # Parse --since date if provided
    since_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.since}'. Use YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)

    try:
        # Get server ID from args or config
        config = get_config()
        server_id = args.server or config.server_id

        if server_id:
            # Sync specific server
            asyncio.run(sync_server(
                server_id=server_id,
                channel_id=args.channel,
                days=args.days,
                incremental=not args.full,
                limit=None if args.full else args.limit,
                fill_gaps=args.fill_gaps,
                since_date=since_date,
                use_parallel=args.parallel
            ))
        else:
            # Sync ALL servers
            asyncio.run(sync_all_servers(
                days=args.days,
                incremental=not args.full,
                limit=None if args.full else args.limit,
                fill_gaps=args.fill_gaps,
                since_date=since_date,
                use_parallel=args.parallel
            ))

    except ConfigError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        print("\nMake sure you have created .env with DISCORD_USER_TOKEN")
        sys.exit(1)
    except AuthenticationError as e:
        print(f"Authentication Error: {e}", file=sys.stderr)
        sys.exit(1)
    except DiscordClientError as e:
        print(f"Discord Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nSync cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()

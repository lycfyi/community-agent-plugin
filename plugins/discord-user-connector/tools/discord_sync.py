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

Note:
    This tool uses the user token (DISCORD_USER_TOKEN) for all operations.
    For bot token sync with higher rate limits, use discord-bot-connector:discord-sync.
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
from lib.storage import get_storage, SyncMode, DM_DEFAULT_LIMIT
from lib.parallel_sync import ParallelSyncOrchestrator, SyncSummary
from lib.rate_limiter import format_duration


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


async def sync_dm(
    client: DiscordUserClient,
    storage,
    channel_id: str,
    user_id: str,
    username: str,
    display_name: str,
    avatar: Optional[str],
    days: int,
    incremental: bool,
    limit: int = DM_DEFAULT_LIMIT
) -> int:
    """Sync messages from a single DM.

    Args:
        client: Discord client
        storage: Storage instance
        channel_id: DM channel ID
        user_id: User ID
        username: Username
        display_name: Display name
        avatar: Avatar URL
        days: Days of history to fetch
        incremental: Whether to do incremental sync
        limit: Max messages to fetch

    Returns:
        Number of messages synced
    """
    # Get last message ID for incremental sync
    after_id = None
    if incremental:
        after_id = storage.get_dm_last_message_id(user_id)
        if after_id:
            print(f"  Incremental sync from message {after_id}")

    # Fetch messages
    messages = []
    async for msg in client.fetch_dm_messages(
        channel_id=channel_id,
        after_id=after_id,
        days=days,
        limit=limit
    ):
        messages.append(msg)
        if len(messages) % 25 == 0:
            print(f"  Fetched {len(messages)} messages...")
        if len(messages) >= limit:
            print(f"  Reached limit of {limit} messages")
            break

    if not messages:
        print(f"  No new messages to sync")
        return 0

    # Save user metadata
    storage.save_dm_metadata(
        user_id=user_id,
        username=username,
        display_name=display_name,
        avatar=avatar
    )

    # Save messages to storage
    storage.append_dm_messages(
        user_id=user_id,
        username=username,
        display_name=display_name,
        channel_id=channel_id,
        messages=messages
    )

    print(f"  Synced {len(messages)} messages")
    return len(messages)


async def sync_all_dms(
    client: DiscordUserClient,
    storage,
    days: int,
    incremental: bool,
    limit: int = DM_DEFAULT_LIMIT
) -> tuple[int, int]:
    """Sync all DM channels.

    Args:
        client: Discord client
        storage: Storage instance
        days: Days of history to fetch
        incremental: Whether to do incremental sync
        limit: Max messages per DM

    Returns:
        Tuple of (total_messages, dm_count)
    """
    print("Fetching DM channels...")
    dms = await client.list_dms()

    if not dms:
        print("No DMs found.")
        return 0, 0

    print(f"Found {len(dms)} DM(s). Syncing (max {limit} msgs each)...")

    total_messages = 0
    synced_count = 0

    for dm in dms:
        channel_id = dm["id"]
        user_id = dm["user_id"]
        username = dm.get("username", "unknown")
        display_name = dm.get("display_name", username)
        avatar = dm.get("avatar")

        print(f"\nDM with {display_name} (@{username}):")
        try:
            count = await sync_dm(
                client=client,
                storage=storage,
                channel_id=channel_id,
                user_id=user_id,
                username=username,
                display_name=display_name,
                avatar=avatar,
                days=days,
                incremental=incremental,
                limit=limit
            )
            total_messages += count
            if count > 0:
                synced_count += 1
        except DiscordClientError as e:
            print(f"  Error: {e}")
            continue

    return total_messages, synced_count


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

    # Get channels to sync
    all_channels = await client.list_channels(server_id)

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
        # Sort channels: priority channels first, then by position
        def channel_sort_key(ch):
            name = ch.get("name", "").lower()
            # Priority channels get negative index (come first)
            if name in [p.lower() for p in priority_channels]:
                priority_idx = -1000 + [p.lower() for p in priority_channels].index(name)
            else:
                priority_idx = ch.get("position", 999)
            return priority_idx

        sorted_channels = sorted(all_channels, key=channel_sort_key)

        # Limit to max channels
        channels_to_sync = sorted_channels[:max_channels]

        if len(all_channels) > max_channels:
            print(f"Limiting to top {max_channels} channels (of {len(all_channels)} total)")

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
        except discord.Forbidden as e:
            print(f"Access denied (403)")
            print(f"    Possible causes:")
            print(f"    - You don't have 'Read Message History' permission")
            print(f"    - This is a private channel you're not a member of")
            print(f"    - The channel requires specific roles to view")
            print(f"    Fix: Request access or remove from sync config")
            failed_channels.append({"name": channel['name'], "error": "access_denied"})
            continue
        except discord.HTTPException as e:
            if e.status == 429:
                print(f"Rate limited - retry after {getattr(e, 'retry_after', 'unknown')}s")
            else:
                print(f"HTTP error {e.status}: {e.text}")
            failed_channels.append({"name": channel['name'], "error": f"http_{e.status}"})
            continue
        except DiscordClientError as e:
            print(f"Error: {e}")
            failed_channels.append({"name": channel['name'], "error": str(e)})
            continue

    if failed_channels:
        print(f"  Warning: {len(failed_channels)} channel(s) failed")
        print(f"  Failed channels:")
        for fc in failed_channels:
            name = fc["name"] if isinstance(fc, dict) else fc
            print(f"    - #{name}")

    return total_messages


async def sync_all_servers(
    days: int,
    incremental: bool,
    quick_mode: bool = False,
    quick_limit: int = 200,
    fill_gaps: bool = False,
    since_date: Optional[date] = None,
    use_parallel: bool = True
) -> None:
    """Sync messages from ALL servers.

    Args:
        days: Number of days of history to fetch.
        incremental: Whether to do incremental sync.
        quick_mode: If True, limit messages for fast initial sync.
        quick_limit: Max messages per channel in quick mode.
        fill_gaps: If True, fill missing date ranges.
        since_date: If set, fetch messages from this date onward.
        use_parallel: If True, use parallel channel syncing.
    """
    config = get_config()
    storage = get_storage()
    client = DiscordUserClient()

    try:
        print("Fetching your Discord servers...")
        guilds = await client.list_guilds()

        if not guilds:
            print("No servers found in your Discord account.")
            sys.exit(1)

        mode_str = "Quick" if quick_mode else ("Gap Fill" if fill_gaps else "Standard")
        print(f"Found {len(guilds)} server(s). {mode_str} sync, last {days} day(s)...")

        grand_total = 0
        for server_info in guilds:
            server_id = server_info["id"]
            server_name = server_info["name"]
            print(f"\n{'='*50}")
            print(f"Syncing: {server_name} ({server_id})")

            try:
                # Save server metadata
                storage.save_server_metadata(
                    server_id=server_id,
                    server_name=server_name,
                    icon=server_info.get("icon"),
                    member_count=server_info.get("member_count", 0)
                )

                # Get channels to sync
                all_channels = await client.list_channels(server_id)
                max_channels = config.max_channels_per_server
                max_messages = config.max_messages_per_channel
                priority_channels = config.priority_channels

                # Sort channels: priority channels first, then by position
                def channel_sort_key(ch):
                    name = ch.get("name", "").lower()
                    if name in [p.lower() for p in priority_channels]:
                        priority_idx = -1000 + [p.lower() for p in priority_channels].index(name)
                    else:
                        priority_idx = ch.get("position", 999)
                    return priority_idx

                sorted_channels = sorted(all_channels, key=channel_sort_key)
                channels_to_sync = sorted_channels[:max_channels]

                if len(all_channels) > max_channels:
                    print(f"Limiting to top {max_channels} channels (of {len(all_channels)} total)")

                # Use parallel sync
                if use_parallel and len(channels_to_sync) > 1:
                    orchestrator = ParallelSyncOrchestrator(
                        client=client,
                        storage=storage,
                        server_id=server_id,
                        server_name=server_name,
                        quick_mode=quick_mode,
                        quick_limit=quick_limit,
                        days=days,
                        incremental=incremental,
                        fill_gaps=fill_gaps,
                        since_date=since_date,
                    )

                    summary = await orchestrator.sync_all_channels(
                        channels=channels_to_sync,
                        max_messages_per_channel=max_messages,
                    )
                    grand_total += summary.total_messages
                else:
                    # Sequential sync
                    count = await sync_single_server(
                        client=client,
                        storage=storage,
                        config=config,
                        server_info=server_info,
                        channel_id=None,
                        days=days,
                        incremental=incremental
                    )
                    grand_total += count

            except Exception as e:
                print(f"  Error syncing {server_info['name']}: {e}")
                continue

        # Update manifest
        manifest = storage.update_manifest()

        print(f"\n{'='*50}")
        print(f"SYNC COMPLETE!")
        print(f"Total: {grand_total} messages from {len(guilds)} servers")
        print(f"Data location: {config.data_dir}")
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
    quick_mode: bool = False,
    quick_limit: int = 200,
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
        quick_mode: If True, limit messages for fast initial sync.
        quick_limit: Max messages per channel in quick mode.
        fill_gaps: If True, fill missing date ranges.
        since_date: If set, fetch messages from this date onward.
        use_parallel: If True, use parallel channel syncing.
    """
    config = get_config()
    storage = get_storage()
    client = DiscordUserClient()

    try:
        # Get server info - support both ID and name lookup
        guilds = await client.list_guilds()

        # First try exact ID match
        server_info = next(
            (g for g in guilds if g["id"] == server_id),
            None
        )

        # If not found by ID, try name match (case-insensitive, partial)
        if not server_info:
            search_term = server_id.lower()
            matches = [
                g for g in guilds
                if search_term in g["name"].lower()
            ]
            if len(matches) == 1:
                server_info = matches[0]
                print(f"Matched server by name: {server_info['name']}")
            elif len(matches) > 1:
                print(f"Error: Multiple servers match '{server_id}':")
                for m in matches:
                    print(f"  - {m['name']} (ID: {m['id']})")
                print("Please specify the server ID instead.")
                sys.exit(1)

        if not server_info:
            print(f"Error: Server '{server_id}' not found or not accessible")
            print("Use 'discord-list --servers' to see available servers.")
            sys.exit(1)

        # Use resolved server ID and name
        server_id = server_info["id"]
        server_name = server_info["name"]
        print(f"Syncing from: {server_name} ({server_id})")

        # Save server metadata
        storage.save_server_metadata(
            server_id=server_id,
            server_name=server_name,
            icon=server_info.get("icon"),
            member_count=server_info.get("member_count", 0)
        )

        # Get channels to sync
        all_channels = await client.list_channels(server_id)

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

            channels_to_sync = [channel_info]
        else:
            # Sort channels: priority channels first, then by position
            def channel_sort_key(ch):
                name = ch.get("name", "").lower()
                # Priority channels get negative index (come first)
                if name in [p.lower() for p in priority_channels]:
                    priority_idx = -1000 + [p.lower() for p in priority_channels].index(name)
                else:
                    priority_idx = ch.get("position", 999)
                return priority_idx

            sorted_channels = sorted(all_channels, key=channel_sort_key)

            # Limit to max channels
            channels_to_sync = sorted_channels[:max_channels]

            if len(all_channels) > max_channels:
                print(f"Limiting to top {max_channels} channels (of {len(all_channels)} total)")
                print(f"  To sync more, set discord.sync_limits.max_channels_per_server in config/agents.yaml")

        # Determine effective limit
        effective_limit = quick_limit if quick_mode else max_messages
        mode_str = "Quick" if quick_mode else ("Gap Fill" if fill_gaps else "Standard")
        print(f"{mode_str} sync: {len(channels_to_sync)} channel(s) (max {effective_limit} msgs each)...")

        # Use parallel sync if enabled and multiple channels
        if use_parallel and len(channels_to_sync) > 1:
            orchestrator = ParallelSyncOrchestrator(
                client=client,
                storage=storage,
                server_id=server_id,
                server_name=server_name,
                quick_mode=quick_mode,
                quick_limit=quick_limit,
                days=days,
                incremental=incremental,
                fill_gaps=fill_gaps,
                since_date=since_date,
            )

            summary = await orchestrator.sync_all_channels(
                channels=channels_to_sync,
                max_messages_per_channel=max_messages,
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
                except discord.Forbidden as e:
                    print(f"  Access denied (403)")
                    print(f"    - You may not have 'Read Message History' permission")
                    print(f"    - Request access or remove this channel from config")
                    failed_channels.append({"name": channel['name'], "error": "access_denied"})
                    continue
                except discord.HTTPException as e:
                    if e.status == 429:
                        print(f"  Rate limited - retry after {getattr(e, 'retry_after', 'unknown')}s")
                    else:
                        print(f"  HTTP error {e.status}: {e.text}")
                    failed_channels.append({"name": channel['name'], "error": f"http_{e.status}"})
                    continue
                except DiscordClientError as e:
                    print(f"  Error: {e}")
                    failed_channels.append({"name": channel['name'], "error": str(e)})
                    continue

            # Report failed channels if any
            if failed_channels:
                print(f"\nWarning: {len(failed_channels)} channel(s) failed to sync:")
                for fc in failed_channels:
                    name = fc["name"] if isinstance(fc, dict) else fc
                    error = fc.get("error", "unknown") if isinstance(fc, dict) else "unknown"
                    print(f"  - #{name} ({error})")

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


async def sync_specific_dm(
    dm_channel_id: str,
    days: int,
    incremental: bool,
    limit: int = DM_DEFAULT_LIMIT
) -> None:
    """Sync a specific DM by channel ID.

    Args:
        dm_channel_id: DM channel ID to sync
        days: Days of history to fetch
        incremental: Whether to do incremental sync
        limit: Max messages to fetch
    """
    client = DiscordUserClient()
    storage = get_storage()

    try:
        print(f"Syncing DM channel {dm_channel_id}...")

        # Find the DM info
        dms = await client.list_dms()
        dm_info = next((d for d in dms if d["id"] == dm_channel_id), None)

        if not dm_info:
            print(f"Error: DM channel {dm_channel_id} not found")
            print("Use 'discord-list --dms' to see available DM channels")
            sys.exit(1)

        user_id = dm_info["user_id"]
        username = dm_info.get("username", "unknown")
        display_name = dm_info.get("display_name", username)
        avatar = dm_info.get("avatar")

        print(f"DM with {display_name} (@{username}):")

        count = await sync_dm(
            client=client,
            storage=storage,
            channel_id=dm_channel_id,
            user_id=user_id,
            username=username,
            display_name=display_name,
            avatar=avatar,
            days=days,
            incremental=incremental,
            limit=limit
        )

        # Update DM manifest
        dm_manifest = storage.update_dm_manifest()

        print(f"\n{'='*50}")
        print(f"DM Sync Complete!")
        print(f"Total messages: {count}")
        print(f"DM manifest: {dm_manifest['summary']['total_users']} users, "
              f"{dm_manifest['summary']['total_messages']} messages")

    finally:
        await client.close()


async def sync_dms_standalone(
    days: int,
    incremental: bool,
    limit: int = DM_DEFAULT_LIMIT
) -> None:
    """Sync all DMs as a standalone operation.

    Args:
        days: Days of history to fetch
        incremental: Whether to do incremental sync
        limit: Max messages per DM
    """
    client = DiscordUserClient()
    storage = get_storage()

    try:
        print(f"\n{'='*50}")
        print("Syncing DMs (using user token)...")

        total_messages, dm_count = await sync_all_dms(
            client=client,
            storage=storage,
            days=days,
            incremental=incremental,
            limit=limit
        )

        # Update DM manifest
        dm_manifest = storage.update_dm_manifest()

        print(f"\n{'='*50}")
        print(f"DM Sync Complete!")
        print(f"Total: {total_messages} messages from {dm_count} DM(s)")
        print(f"DM manifest: {dm_manifest['summary']['total_users']} users, "
              f"{dm_manifest['summary']['total_messages']} messages")

    finally:
        await client.close()


def _run_analysis_after_sync(server_id: str, days: int) -> None:
    """Run health analysis after sync completes.

    Args:
        server_id: Server ID to analyze.
        days: Number of days to analyze.
    """
    try:
        from lib.analytics.report import generate_health_report, save_health_report
        from lib.analytics.benchmarks import load_custom_benchmarks

        config = get_config()
        storage = get_storage()

        # Find server directory
        server_dir = None
        for d in storage._base_dir.iterdir():
            if d.is_dir() and d.name.startswith(server_id):
                server_dir = d
                break

        if not server_dir:
            print(f"\nWarning: Could not find server directory for analysis")
            return

        # Get server name
        sync_state = storage.get_sync_state(server_id)
        server_name = sync_state.get("server_name", f"Server {server_id}")

        print(f"\nGenerating health report...")

        # Load custom benchmarks
        custom_benchmarks = None
        try:
            community_config = config._community_config._config
            custom_benchmarks = load_custom_benchmarks(community_config)
        except Exception:
            pass

        # Generate report
        report = generate_health_report(
            server_dir=server_dir,
            server_id=server_id,
            server_name=server_name,
            days=days,
            custom_benchmarks=custom_benchmarks,
            verbose=True,
        )

        # Save report
        md_path, _ = save_health_report(report, server_dir)

        # Print summary
        print("")
        print("=" * 50)
        print("✅ Health report generated!")
        print("")
        print(f"Overall Score: {report.health_scores.overall}/100", end="")
        if report.health_scores.overall >= 60:
            print(" (Healthy)")
        elif report.health_scores.overall >= 40:
            print(" (Warning)")
        else:
            print(" (Critical)")
        print("")
        print(f"Report saved to: {md_path}")

    except ImportError:
        print(f"\nWarning: Analytics module not available. Skipping analysis.")
    except Exception as e:
        print(f"\nWarning: Analysis failed: {e}")


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
        help="Full sync (ignore last message ID, fetch all messages)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick start mode: fetch only recent messages (~200 per channel)"
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
        help="Max messages per channel in quick mode (default: 200)"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Use parallel channel syncing (default: True)"
    )

    # DM-specific arguments
    parser.add_argument(
        "--dm",
        metavar="CHANNEL_ID",
        dest="dm_channel_id",
        help="Sync a specific DM by channel ID (use discord-list --dms to find IDs)"
    )
    parser.add_argument(
        "--no-dms",
        action="store_true",
        dest="no_dms",
        help="Exclude DMs from sync (servers only)"
    )
    parser.add_argument(
        "--dm-limit",
        type=int,
        default=DM_DEFAULT_LIMIT,
        dest="dm_limit",
        help=f"Max messages per DM (default: {DM_DEFAULT_LIMIT})"
    )

    # Analytics integration
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Generate health report after sync completes"
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

        # Check for storage migration (v1 -> v2 unified structure)
        storage = get_storage()
        if storage.needs_migration():
            print("Detected legacy storage structure. Migrating to unified structure...")
            report = storage.migrate_to_v2()
            if report.get("errors"):
                print(f"Migration completed with {len(report['errors'])} errors:")
                for err in report["errors"]:
                    print(f"  - {err}")
            else:
                servers = len(report.get("servers_migrated", []))
                dms = len(report.get("dms_migrated", []))
                print(f"Migration complete: {servers} servers, {dms} DMs moved to data/discord/")

        # Mode 1: Sync specific DM only
        if args.dm_channel_id:
            asyncio.run(sync_specific_dm(
                dm_channel_id=args.dm_channel_id,
                days=args.days,
                incremental=not args.full,
                limit=args.dm_limit
            ))
        # Mode 2: Sync specific server (with optional DMs)
        elif server_id:
            # Sync specific server
            asyncio.run(sync_server(
                server_id=server_id,
                channel_id=args.channel,
                days=args.days,
                incremental=not args.full,
                quick_mode=args.quick,
                quick_limit=args.limit,
                fill_gaps=args.fill_gaps,
                since_date=since_date,
                use_parallel=args.parallel
            ))
            # Also sync DMs unless --no-dms
            if not args.no_dms:
                asyncio.run(sync_dms_standalone(
                    days=args.days,
                    incremental=not args.full,
                    limit=args.dm_limit
                ))
        # Mode 3: Sync ALL servers + DMs
        else:
            # Sync ALL servers
            asyncio.run(sync_all_servers(
                days=args.days,
                incremental=not args.full,
                quick_mode=args.quick,
                quick_limit=args.limit,
                fill_gaps=args.fill_gaps,
                since_date=since_date,
                use_parallel=args.parallel
            ))
            # Also sync DMs unless --no-dms
            if not args.no_dms:
                asyncio.run(sync_dms_standalone(
                    days=args.days,
                    incremental=not args.full,
                    limit=args.dm_limit
                ))

        # Run analysis if --analyze flag is set
        if args.analyze and server_id:
            _run_analysis_after_sync(server_id, args.days)

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

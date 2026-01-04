#!/usr/bin/env python3
"""Discord sync tool - Sync messages from Discord to local storage.

Usage:
    python tools/discord_sync.py
    python tools/discord_sync.py --server SERVER_ID
    python tools/discord_sync.py --channel CHANNEL_ID --days 7
"""

import argparse
import asyncio
import sys
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
from lib.storage import get_storage


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
        except (DiscordClientError, discord.Forbidden, discord.HTTPException) as e:
            print(f"Error: {e}")
            failed_channels.append(channel['name'])
            continue

    if failed_channels:
        print(f"  Warning: {len(failed_channels)} channel(s) failed")

    return total_messages


async def sync_all_servers(
    days: int,
    incremental: bool
) -> None:
    """Sync messages from ALL servers."""
    config = get_config()
    client = DiscordUserClient()
    storage = get_storage()

    try:
        print("Fetching your Discord servers...")
        guilds = await client.list_guilds()

        if not guilds:
            print("No servers found in your Discord account.")
            sys.exit(1)

        print(f"Found {len(guilds)} server(s). Syncing last {days} day(s)...")

        grand_total = 0
        for server_info in guilds:
            try:
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
    incremental: bool
) -> None:
    """Sync messages from a specific server."""
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
                print(f"  To sync more, set sync_limits.max_channels_per_server in config/server.yaml")

        print(f"Syncing {len(channels_to_sync)} channel(s) (max {max_messages} messages each)...")

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
                    max_messages=max_messages
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
        config = get_config()
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
        default=1,
        help="Days of history to fetch (default: 1)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full sync (ignore last message ID, fetch all messages)"
    )

    args = parser.parse_args()

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
                incremental=not args.full
            ))
        else:
            # Sync ALL servers
            asyncio.run(sync_all_servers(
                days=args.days,
                incremental=not args.full
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

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
    incremental: bool
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

    # Fetch messages
    messages = []
    async for msg in client.fetch_messages(
        server_id=server_id,
        channel_id=channel_id,
        after_id=after_id,
        days=days
    ):
        messages.append(msg)
        if len(messages) % 50 == 0:
            print(f"  Fetched {len(messages)} messages...")

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
        channel_name=channel_name
    )

    print(f"  Synced {len(messages)} messages")
    return len(messages)


async def sync_server(
    server_id: str,
    channel_id: Optional[str],
    days: int,
    incremental: bool
) -> None:
    """Sync messages from a server."""
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
            # Sync all text channels
            channels_to_sync = all_channels

        print(f"Syncing {len(channels_to_sync)} channel(s)...")

        total_messages = 0
        for channel in channels_to_sync:
            print(f"\n#{channel['name']}:")
            count = await sync_channel(
                client=client,
                storage=storage,
                server_id=server_id,
                server_name=server_name,
                channel_id=channel["id"],
                channel_name=channel["name"],
                days=days,
                incremental=incremental
            )
            total_messages += count

        # Print summary
        config = get_config()
        data_dir = config.get_server_data_dir(server_id)

        print(f"\n{'='*50}")
        print(f"Sync complete!")
        print(f"Total messages: {total_messages}")
        print(f"Data location: {data_dir}")

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
        default=30,
        help="Days of history to fetch (default: 30)"
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

        asyncio.run(sync_server(
            server_id=server_id,
            channel_id=args.channel,
            days=args.days,
            incremental=not args.full
        ))

    except ConfigError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        print("\nMake sure you have:")
        print("  1. Created .env with DISCORD_USER_TOKEN")
        print("  2. Set server_id in config/server.yaml")
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

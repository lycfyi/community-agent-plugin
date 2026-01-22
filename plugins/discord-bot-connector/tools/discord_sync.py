#!/usr/bin/env python3
"""Discord bot sync tool - Sync server messages using bot token.

Uses Discord Bot API for higher rate limits and official API compliance.
Cannot sync DMs (bots cannot access user DMs).

Usage:
    python tools/discord_sync.py --server SERVER_ID
    python tools/discord_sync.py --server SERVER_ID --days 7
    python tools/discord_sync.py --server SERVER_ID --quick
    python tools/discord_sync.py --server SERVER_ID --full
"""

import argparse
import asyncio
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.bot_http_client import BotHttpClient, BotHttpClientError, BotAuthenticationError
from lib.storage import Storage, SyncMode


async def sync_channel(
    client: BotHttpClient,
    storage: Storage,
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


async def sync_server(
    server_id: str,
    channel_id: Optional[str] = None,
    days: int = 7,
    incremental: bool = True,
    quick_mode: bool = False,
    quick_limit: int = 200,
    max_messages: int = 1000,
    max_channels: int = 20,
) -> None:
    """Sync messages from a server using bot token.

    Args:
        server_id: Discord server ID to sync.
        channel_id: Optional specific channel ID to sync.
        days: Number of days of history to fetch.
        incremental: Whether to do incremental sync.
        quick_mode: If True, limit messages for fast initial sync.
        quick_limit: Max messages per channel in quick mode.
        max_messages: Max messages per channel in full mode.
        max_channels: Max channels to sync per server.
    """
    config = get_config()
    client = BotHttpClient()
    storage = Storage()

    try:
        print("Using bot token for sync (higher rate limits)")
        print(f"Fetching server info for {server_id}...")

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
            print(f"Error: Server '{server_id}' not found.")
            print("Make sure the bot is added to the server.")
            print("Use '--list-servers' to see available servers.")
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
            # Limit to max channels
            channels_to_sync = all_channels[:max_channels]

            if len(all_channels) > max_channels:
                print(f"Limiting to {max_channels} channels (of {len(all_channels)} total)")

        # Determine effective limit
        effective_limit = quick_limit if quick_mode else max_messages
        mode_str = "Quick" if quick_mode else "Standard"
        print(f"{mode_str} sync: {len(channels_to_sync)} channel(s) (max {effective_limit} msgs each)...")

        # Sync channels
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
            except BotHttpClientError as e:
                print(f"  Error: {e}")
                failed_channels.append({"name": channel['name'], "error": str(e)})
                continue

        # Report failed channels if any
        if failed_channels:
            print(f"\nWarning: {len(failed_channels)} channel(s) failed to sync:")
            for fc in failed_channels:
                print(f"  - #{fc['name']}: {fc['error']}")

        # Update manifest
        manifest = storage.update_manifest()

        # Print summary
        print(f"\n{'='*50}")
        print(f"Sync complete!")
        print(f"Total messages: {total_messages}")
        print(f"Manifest: {manifest['summary']['total_servers']} servers, "
              f"{manifest['summary']['total_channels']} channels, "
              f"{manifest['summary']['total_messages']} messages")

    finally:
        await client.close()


async def list_servers() -> None:
    """List all servers the bot is in."""
    client = BotHttpClient()

    try:
        print("Fetching servers...")
        guilds = await client.list_guilds()

        if not guilds:
            print("Bot is not in any servers.")
            return

        print(f"\nBot is in {len(guilds)} server(s):\n")
        for guild in guilds:
            print(f"  {guild['name']}")
            print(f"    ID: {guild['id']}")
            print(f"    Members: {guild['member_count']}")
            print()

    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Sync Discord server messages using bot token"
    )

    parser.add_argument(
        "--server",
        metavar="SERVER_ID",
        help="Server ID to sync"
    )
    parser.add_argument(
        "--channel",
        metavar="CHANNEL_ID",
        help="Specific channel ID to sync"
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
        help="Full sync (ignore last message ID)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: limit messages (~200 per channel)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max messages per channel in quick mode (default: 200)"
    )
    parser.add_argument(
        "--list-servers",
        action="store_true",
        dest="list_servers",
        help="List all servers the bot is in"
    )

    args = parser.parse_args()

    try:
        if args.list_servers:
            asyncio.run(list_servers())
        elif args.server:
            asyncio.run(sync_server(
                server_id=args.server,
                channel_id=args.channel,
                days=args.days,
                incremental=not args.full,
                quick_mode=args.quick,
                quick_limit=args.limit,
            ))
        else:
            print("Error: --server SERVER_ID is required")
            print("Use --list-servers to see available servers")
            sys.exit(1)

    except ConfigError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        print("\nMake sure you have created .env with DISCORD_BOT_TOKEN")
        sys.exit(1)
    except BotAuthenticationError as e:
        print(f"Authentication Error: {e}", file=sys.stderr)
        sys.exit(1)
    except BotHttpClientError as e:
        print(f"Discord Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nSync cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()

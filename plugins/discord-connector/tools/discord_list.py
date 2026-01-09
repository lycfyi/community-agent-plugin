#!/usr/bin/env python3
"""Discord list tool - List accessible servers and channels.

Usage:
    python tools/discord_list.py --servers
    python tools/discord_list.py --channels SERVER_ID
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.discord_client import DiscordUserClient, DiscordClientError, AuthenticationError


async def list_servers() -> None:
    """List all accessible servers."""
    client = DiscordUserClient()
    try:
        guilds = await client.list_guilds()

        if not guilds:
            print("No servers found. Make sure your account has joined some servers.")
            return

        print(f"Found {len(guilds)} server(s):\n")
        print(f"{'ID':<20} {'Name':<30} {'Members':<10}")
        print("-" * 60)

        for guild in guilds:
            print(f"{guild['id']:<20} {guild['name']:<30} {guild['member_count']:<10}")

        print("\nTo list channels in a server:")
        print("  python tools/discord_list.py --channels SERVER_ID")

    finally:
        await client.close()


async def list_channels(server_id: str) -> None:
    """List channels in a server."""
    client = DiscordUserClient()
    try:
        channels = await client.list_channels(server_id)

        if not channels:
            print(f"No text channels found in server {server_id}.")
            return

        print(f"Found {len(channels)} text channel(s) in server {server_id}:\n")
        print(f"{'ID':<20} {'Name':<25} {'Category':<20}")
        print("-" * 65)

        current_category = None
        for channel in channels:
            category = channel.get('category') or '(no category)'
            if category != current_category:
                current_category = category
                print(f"\n[{category}]")

            print(f"  {channel['id']:<20} #{channel['name']:<24}")

        print("\nTo sync messages from a channel:")
        print("  python tools/discord_sync.py --channel CHANNEL_ID")

    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(
        description="List Discord servers and channels"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--servers",
        action="store_true",
        help="List all accessible servers"
    )
    group.add_argument(
        "--channels",
        metavar="SERVER_ID",
        help="List channels in a specific server"
    )

    args = parser.parse_args()

    try:
        if args.servers:
            asyncio.run(list_servers())
        elif args.channels:
            asyncio.run(list_channels(args.channels))

    except AuthenticationError as e:
        print(f"Authentication Error: {e}", file=sys.stderr)
        sys.exit(1)
    except DiscordClientError as e:
        print(f"Discord Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()

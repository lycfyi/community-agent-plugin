#!/usr/bin/env python3
"""Discord list tool - List accessible servers, channels, and DMs.

Usage:
    python tools/discord_list.py --servers
    python tools/discord_list.py --servers --no-dms
    python tools/discord_list.py --channels SERVER_ID
    python tools/discord_list.py --dms
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.discord_client import DiscordUserClient, DiscordClientError, AuthenticationError


async def list_servers(include_dms: bool = True) -> None:
    """List all accessible servers and optionally DMs."""
    client = DiscordUserClient()
    try:
        guilds = await client.list_guilds()

        if not guilds:
            print("No servers found. Make sure your account has joined some servers.")
        else:
            print(f"Found {len(guilds)} server(s):\n")
            print(f"{'ID':<20} {'Name':<30} {'Members':<10}")
            print("-" * 60)

            for guild in guilds:
                print(f"{guild['id']:<20} {guild['name']:<30} {guild['member_count']:<10}")

            print("\nTo list channels in a server:")
            print("  python tools/discord_list.py --channels SERVER_ID")

        # List DMs if requested
        if include_dms:
            dms = await client.list_dms()
            if dms:
                print(f"\n\nFound {len(dms)} DM(s):\n")
                print(f"{'Channel ID':<20} {'User ID':<20} {'Username':<20} {'Display Name':<20}")
                print("-" * 80)

                for dm in dms:
                    channel_id = dm['id']
                    user_id = dm['user_id']
                    username = dm.get('username', '-')
                    display_name = dm.get('display_name', '-')[:20]
                    print(f"{channel_id:<20} {user_id:<20} {username:<20} {display_name:<20}")

                print("\nTo sync DMs:")
                print("  python tools/discord_sync.py --dm CHANNEL_ID")
            elif guilds:
                print("\n(No DMs found. Use --no-dms to skip this check)")

    finally:
        await client.close()


async def list_dms() -> None:
    """List all DM channels."""
    client = DiscordUserClient()
    try:
        dms = await client.list_dms()

        if not dms:
            print("No DMs found.")
            return

        print(f"Found {len(dms)} DM(s):\n")
        print(f"{'Channel ID':<20} {'User ID':<20} {'Username':<20} {'Display Name':<20}")
        print("-" * 80)

        for dm in dms:
            channel_id = dm['id']
            user_id = dm['user_id']
            username = dm.get('username', '-')
            display_name = dm.get('display_name', '-')[:20]
            print(f"{channel_id:<20} {user_id:<20} {username:<20} {display_name:<20}")

        print("\nTo sync a specific DM:")
        print("  python tools/discord_sync.py --dm CHANNEL_ID")

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
        description="List Discord servers, channels, and DMs"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--servers",
        action="store_true",
        help="List all accessible servers (includes DMs by default)"
    )
    group.add_argument(
        "--channels",
        metavar="SERVER_ID",
        help="List channels in a specific server"
    )
    group.add_argument(
        "--dms",
        action="store_true",
        help="List DM channels only"
    )

    parser.add_argument(
        "--no-dms",
        action="store_true",
        dest="no_dms",
        help="Exclude DMs when listing servers"
    )

    args = parser.parse_args()

    try:
        if args.servers:
            include_dms = not args.no_dms
            asyncio.run(list_servers(include_dms=include_dms))
        elif args.channels:
            asyncio.run(list_channels(args.channels))
        elif args.dms:
            asyncio.run(list_dms())

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

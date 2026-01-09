#!/usr/bin/env python3
"""Discord init tool - Initialize configuration from Discord account.

Usage:
    python discord_init.py
    python discord_init.py --server SERVER_ID

Options:
    --server SERVER_ID    Select specific server to configure as default

Output:
    - Updates config/agents.yaml with Discord settings
    - Prints available servers to stdout

Exit Codes:
    0 - Success
    1 - Authentication error
    2 - Configuration error

WARNING: Using a user token may violate Discord's Terms of Service.
This is for personal archival and analysis only.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.discord_client import DiscordUserClient, DiscordClientError, AuthenticationError


async def main(args: argparse.Namespace) -> int:
    """Main entry point.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    # Print warning
    print("=" * 60)
    print("WARNING: Using a user token may violate Discord's ToS.")
    print("This is for personal archival and analysis only.")
    print("=" * 60)
    print()

    try:
        # Load config (validates environment variables)
        config = get_config()
        print(f"Token: {'*' * 20}...{config.discord_token[-10:]}")
        print()

    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print()
        print("Make sure your .env file contains:", file=sys.stderr)
        print("  DISCORD_USER_TOKEN=your_token", file=sys.stderr)
        print()
        print("To get your token:", file=sys.stderr)
        print("  1. Open Discord in browser", file=sys.stderr)
        print("  2. Press F12 → Network tab", file=sys.stderr)
        print("  3. Do any action in Discord", file=sys.stderr)
        print("  4. Find request to discord.com/api", file=sys.stderr)
        print("  5. Copy 'Authorization' header value", file=sys.stderr)
        return 2

    # Connect to Discord
    print("Connecting to Discord...")
    client = DiscordUserClient()

    try:
        guilds = await client.list_guilds()

        if not guilds:
            print("No servers found. Make sure your Discord account has joined some servers.")
            return 1

        print(f"Found {len(guilds)} server(s):")
        print()

        # Print server list
        print(f"{'ID':<20} {'Name'}")
        print("-" * 60)

        for guild in guilds:
            print(f"{guild['id']:<20} {guild['name'][:40]}")

        print()

        # Select server
        selected = None

        if args.server:
            # Use specified server
            selected = next((g for g in guilds if g["id"] == args.server), None)
            if not selected:
                print(f"Error: Server {args.server} not found in your account.", file=sys.stderr)
                return 2

        elif len(guilds) == 1:
            # Auto-select if only one server
            selected = guilds[0]
            print(f"Auto-selected only server: {selected['name']}")

        else:
            print("Tip: Run with --server SERVER_ID to set a default server")
            print("Example: python discord_init.py --server 1234567890")
            # Select first by default
            selected = guilds[0]
            print(f"\nSelecting first server by default: {selected['name']}")

        # Save to unified config
        config.set_default_server(selected["id"], selected["name"])

        print()
        print(f"✓ Configuration saved to config/agents.yaml")
        print(f"  Server: {selected['name']} ({selected['id']})")
        print()
        print("Next steps:")
        print("  1. Sync messages: python tools/discord_sync.py")
        print("  2. Or ask Claude: 'Sync my Discord messages'")
        print()
        print("To adjust limits, edit config/agents.yaml")

        return 0

    except AuthenticationError as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        return 1

    except DiscordClientError as e:
        print(f"Discord error: {e}", file=sys.stderr)
        return 1

    finally:
        await client.close()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Initialize Discord configuration from your account",
        epilog="WARNING: Using a user token may violate Discord's ToS."
    )
    parser.add_argument(
        "--server",
        metavar="SERVER_ID",
        help="Specific server ID to configure (lists available if not specified)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

#!/usr/bin/env python3
"""Initialize Telegram configuration.

Usage:
    python telegram_init.py [--group GROUP_ID]

Options:
    --group GROUP_ID    Select specific group to configure as default

Environment:
    TELEGRAM_API_ID      Required. API application ID
    TELEGRAM_API_HASH    Required. API application hash
    TELEGRAM_SESSION     Required. Pre-authenticated session string

Output:
    - Updates config/agents.yaml with Telegram settings
    - Prints available groups to stdout

Exit Codes:
    0 - Success
    1 - Authentication error
    2 - Configuration error

WARNING: Using a user token may violate Telegram's Terms of Service.
This is for personal archival and analysis only.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.telegram_client import (
    TelegramUserClient,
    AuthenticationError,
    TelegramClientError,
)


async def main(args: argparse.Namespace) -> int:
    """Main entry point.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    # Print warning
    print("=" * 60)
    print("WARNING: Using a user token may violate Telegram's ToS.")
    print("This is for personal archival and analysis only.")
    print("=" * 60)
    print()

    try:
        # Load config (validates environment variables)
        config = get_config()
        print(f"API ID: {config.api_id}")
        print(f"Session: {'*' * 20}...{config.session_string[-10:]}")
        print()

    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print()
        print("Make sure your .env file contains:", file=sys.stderr)
        print("  TELEGRAM_API_ID=your_api_id", file=sys.stderr)
        print("  TELEGRAM_API_HASH=your_api_hash", file=sys.stderr)
        print("  TELEGRAM_SESSION=your_session_string", file=sys.stderr)
        print()
        print("Get API credentials from: https://my.telegram.org/apps", file=sys.stderr)
        print("Generate session using: python scripts/generate_session.py", file=sys.stderr)
        return 2

    # Connect to Telegram
    print("Connecting to Telegram...")
    client = TelegramUserClient()

    try:
        await client.connect()

        # Get user info
        me = await client.get_me()
        print(f"Logged in as: {me.get('first_name', '')} (@{me.get('username', 'N/A')})")
        print(f"User ID: {me.get('id')}")
        print()

        # List groups
        print("Fetching groups...")
        groups = await client.list_dialogs()

        if not groups:
            print("No groups found.", file=sys.stderr)
            return 0

        # Filter out empty names
        groups = [g for g in groups if g.get("name")]

        print(f"Found {len(groups)} groups/channels:")
        print()

        # Print group list
        print(f"{'ID':<15} {'Type':<12} {'Members':<10} {'Name'}")
        print("-" * 60)

        for group in groups:
            group_id = group["id"]
            group_type = group["type"]
            member_count = group.get("member_count", 0)
            name = group["name"][:40]  # Truncate long names

            print(f"{group_id:<15} {group_type:<12} {member_count:<10} {name}")

        print()

        # If a specific group was requested, set it as default
        if args.group:
            target_group = None
            for group in groups:
                if str(group["id"]) == str(args.group):
                    target_group = group
                    break

            if not target_group:
                print(f"Group {args.group} not found.", file=sys.stderr)
                return 2

            config.set_default_group(target_group["id"], target_group["name"])
            print(f"Set default group: {target_group['name']} ({target_group['id']})")

        elif len(groups) == 1:
            # Auto-select if only one group
            config.set_default_group(groups[0]["id"], groups[0]["name"])
            print(f"Auto-selected default group: {groups[0]['name']}")

        else:
            print("Tip: Run with --group GROUP_ID to set a default group")
            print("Example: python telegram_init.py --group 1234567890")

        print()
        print("Initialization complete!")
        print()
        print("Next steps:")
        print("  1. Run 'telegram-sync' to sync messages")
        print("  2. Run 'telegram-list' to see groups and topics")
        print("  3. Run 'telegram-read' to view synced messages")

        return 0

    except AuthenticationError as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        print()
        print("Your session may have expired. Generate a new one:", file=sys.stderr)
        print("  python scripts/generate_session.py", file=sys.stderr)
        return 1

    except TelegramClientError as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return 1

    finally:
        await client.disconnect()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Initialize Telegram configuration",
        epilog="WARNING: Using a user token may violate Telegram's ToS."
    )
    parser.add_argument(
        "--group",
        type=str,
        help="Group ID to set as default"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

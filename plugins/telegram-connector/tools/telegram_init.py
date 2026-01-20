#!/usr/bin/env python3
"""Telegram init tool - Initialize configuration from Telegram account.

Usage:
    python telegram_init.py                     # Auto-detect mode (QuickStart for first-run)
    python telegram_init.py --mode quickstart   # Fast setup with defaults
    python telegram_init.py --mode advanced     # Full customization
    python telegram_init.py --group GROUP_ID    # Select specific group

Modes:
    quickstart  Auto-select first group, use defaults, minimal prompts
    advanced    Show all groups, allow selection, configure retention

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

NOTE: This tool only configures Telegram group connection.
      For bot persona setup, run 'community-init' first.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError, SetupError
from lib.telegram_client import (
    TelegramUserClient,
    AuthenticationError,
    TelegramClientError,
)


def print_welcome(is_first_run: bool, mode: str) -> None:
    """Print welcome message based on setup state."""
    print("=" * 60)
    if is_first_run:
        print("Telegram Setup Wizard")
        print(f"Mode: {mode.upper()}")
    else:
        print("Telegram Configuration Update")
    print("=" * 60)
    print()
    print("WARNING: Using a user token may violate Telegram's ToS.")
    print("This is for personal archival and analysis only.")
    print()


def prompt_returning_user(config) -> str:
    """Prompt returning user for action.

    Returns:
        Action to take: 'keep', 'update', or 'reset'
    """
    state = config.get_setup_state()

    print("Existing configuration detected:")
    print(f"  Group: {config.default_group_name or 'Not set'}")
    print(f"  Last run: {state.last_run_at.strftime('%Y-%m-%d %H:%M') if state.last_run_at else 'Never'}")
    print()
    print("Options:")
    print("  1. Keep current configuration")
    print("  2. Update group selection")
    print("  3. Reset and reconfigure")
    print()

    # For non-interactive CLI, default to 'update'
    return "update"


async def run_quickstart(config, client) -> int:
    """Run QuickStart mode - minimal prompts, sensible defaults."""
    print("QuickStart: Connecting to Telegram...")

    try:
        await client.connect()

        # Get user info
        me = await client.get_me()
        print(f"Logged in as: {me.get('first_name', '')} (@{me.get('username', 'N/A')})")
        print()

        # List groups
        groups = await client.list_dialogs()
        groups = [g for g in groups if g.get("name")]  # Filter empty names

        if not groups:
            raise SetupError(
                "No groups found",
                "Make sure you've joined some groups or channels in Telegram",
            )

        # Auto-select first group
        selected = groups[0]

        print(f"Found {len(groups)} group(s)")
        print(f"Auto-selected: {selected['name']}")
        print()

        # Save configuration
        config.set_default_group(selected["id"], selected["name"])
        config.mark_setup_complete(mode="quickstart")

        print("Configuration saved")
        print()
        print("Next: Run 'telegram-sync' to download messages")
        print()
        print("Tip: Run 'community-init' to configure bot persona")

        return 0

    except AuthenticationError as e:
        raise SetupError(
            "Authentication failed",
            "Your session may have expired. Generate a new session string.",
        ) from e


async def run_advanced(config, client, args) -> int:
    """Run Advanced mode - full customization."""
    print("Advanced: Connecting to Telegram...")

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
        groups = [g for g in groups if g.get("name")]  # Filter empty names

        if not groups:
            raise SetupError(
                "No groups found",
                "Make sure you've joined some groups or channels in Telegram",
            )

        print(f"Found {len(groups)} groups/channels:")
        print()

        # Print group list with index
        print(f"{'#':<4} {'ID':<15} {'Type':<12} {'Members':<10} {'Name'}")
        print("-" * 70)

        for i, group in enumerate(groups, 1):
            group_id = group["id"]
            group_type = group["type"]
            member_count = group.get("member_count", 0)
            name = group["name"][:30]

            print(f"{i:<4} {group_id:<15} {group_type:<12} {member_count:<10} {name}")

        print()

        # Select group
        selected = None

        if args.group:
            # Use specified group
            selected = next(
                (g for g in groups if str(g["id"]) == str(args.group)), None
            )
            if not selected:
                raise SetupError(
                    f"Group {args.group} not found",
                    "Check the group ID or run without --group to see available groups",
                )
            print(f"Selected: {selected['name']}")
        elif len(groups) == 1:
            # Auto-select if only one
            selected = groups[0]
            print(f"Auto-selected only group: {selected['name']}")
        else:
            # Default to first group in non-interactive mode
            selected = groups[0]
            print(f"Selecting first group: {selected['name']}")
            print()
            print("Tip: Run with --group GROUP_ID to select a different group")

        print()

        # Show current config values
        print("Configuration:")
        print(f"  Retention days: {config.retention_days}")
        print(f"  Max messages/group: {config.max_messages_per_group}")
        print(f"  Max groups: {config.max_groups}")
        print()
        print("To customize these values, edit config/agents.yaml")
        print()

        # Save configuration
        config.set_default_group(selected["id"], selected["name"])
        config.mark_setup_complete(mode="advanced")

        print("Configuration saved to config/agents.yaml")
        print(f"  Group: {selected['name']} ({selected['id']})")
        print()
        print("Next steps:")
        print("  1. Sync messages: Run 'telegram-sync'")
        print("  2. Read messages: Run 'telegram-read'")
        print("  3. Or ask Claude: 'Sync my Telegram messages'")
        print()
        print("Tip: Run 'community-init' to configure bot persona")

        return 0

    except AuthenticationError as e:
        raise SetupError(
            "Authentication failed",
            "Your session may have expired. Generate a new session string.",
        ) from e


async def main(args: argparse.Namespace) -> int:
    """Main entry point."""
    # Check for credentials before loading config
    missing = []
    if not os.getenv("TELEGRAM_API_ID"):
        missing.append("TELEGRAM_API_ID")
    if not os.getenv("TELEGRAM_API_HASH"):
        missing.append("TELEGRAM_API_HASH")
    if not os.getenv("TELEGRAM_SESSION"):
        missing.append("TELEGRAM_SESSION")

    if missing:
        print("Telegram credentials not found.", file=sys.stderr)
        print()
        print("Missing environment variables:", file=sys.stderr)
        for var in missing:
            print(f"  {var}", file=sys.stderr)
        print()
        print("To set up Telegram:", file=sys.stderr)
        print("  1. Get API credentials from: https://my.telegram.org/apps", file=sys.stderr)
        print("  2. Generate session: python scripts/generate_session.py", file=sys.stderr)
        print("  3. Add to .env file:", file=sys.stderr)
        print("     TELEGRAM_API_ID=your_api_id", file=sys.stderr)
        print("     TELEGRAM_API_HASH=your_api_hash", file=sys.stderr)
        print("     TELEGRAM_SESSION=your_session_string", file=sys.stderr)
        return 2

    try:
        config = get_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    # Determine mode
    is_first_run = config.is_first_run()
    state = config.get_setup_state()

    # Auto-detect mode if not specified
    if args.mode:
        mode = args.mode
    elif is_first_run:
        mode = "quickstart"  # Default to quickstart for new users
    else:
        mode = "advanced"  # Returning users get advanced mode

    print_welcome(is_first_run, mode)

    # Show credentials (masked)
    print(f"API ID: {config.api_id}")
    print(f"Session: {'*' * 20}...{config.session_string[-10:]}")
    print()

    # Handle returning user
    if not is_first_run and state.telegram_group_configured:
        action = prompt_returning_user(config)
        if action == "keep":
            print("Keeping current configuration.")
            return 0

    # Connect to Telegram
    client = TelegramUserClient()

    try:
        if mode == "quickstart":
            return await run_quickstart(config, client)
        else:
            return await run_advanced(config, client, args)

    except SetupError as e:
        print(f"Setup error: {e.message}", file=sys.stderr)
        print(f"Hint: {e.hint}", file=sys.stderr)
        if e.docs_url:
            print(f"Docs: {e.docs_url}", file=sys.stderr)
        return 1

    except TelegramClientError as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return 1

    finally:
        await client.disconnect()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Initialize Telegram configuration from your account",
        epilog="WARNING: Using a user token may violate Telegram's ToS. "
               "For bot persona setup, run 'community-init'."
    )
    parser.add_argument(
        "--mode",
        choices=["quickstart", "advanced"],
        help="Setup mode: quickstart (defaults) or advanced (customize)"
    )
    parser.add_argument(
        "--group",
        type=str,
        help="Specific group ID to configure"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

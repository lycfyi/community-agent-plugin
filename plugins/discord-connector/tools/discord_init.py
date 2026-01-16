#!/usr/bin/env python3
"""Discord init tool - Initialize configuration from Discord account.

Usage:
    python discord_init.py                     # Auto-detect mode (QuickStart for first-run)
    python discord_init.py --mode quickstart   # Fast setup with defaults
    python discord_init.py --mode advanced     # Full customization
    python discord_init.py --server SERVER_ID  # Select specific server

Modes:
    quickstart  Auto-select first server, use defaults, minimal prompts
    advanced    Show all servers, allow selection, configure retention

Output:
    - Updates config/agents.yaml with Discord settings
    - Prints available servers to stdout

Exit Codes:
    0 - Success
    1 - Authentication error
    2 - Configuration error

WARNING: Using a user token may violate Discord's Terms of Service.
This is for personal archival and analysis only.

NOTE: This tool only configures Discord server connection.
      For bot persona setup, run 'community-init' first.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError, SetupError
from lib.discord_client import DiscordUserClient, DiscordClientError, AuthenticationError
from lib.profile import ensure_profile


def print_welcome(is_first_run: bool, mode: str) -> None:
    """Print welcome message based on setup state."""
    print("=" * 60)
    if is_first_run:
        print("Discord Setup Wizard")
        print(f"Mode: {mode.upper()}")
    else:
        print("Discord Configuration Update")
    print("=" * 60)
    print()
    print("WARNING: Using a user token may violate Discord's ToS.")
    print("This is for personal archival and analysis only.")
    print()


def prompt_returning_user(config) -> str:
    """Prompt returning user for action.

    Returns:
        Action to take: 'keep', 'update', or 'reset'
    """
    state = config.get_setup_state()

    print("Existing configuration detected:")
    print(f"  Server: {config._community_config._config.get('discord', {}).get('default_server_name', 'Not set')}")
    print(f"  Last run: {state.last_run_at.strftime('%Y-%m-%d %H:%M') if state.last_run_at else 'Never'}")
    print()
    print("Options:")
    print("  1. Keep current configuration")
    print("  2. Update server selection")
    print("  3. Reset and reconfigure")
    print()

    # For non-interactive CLI, default to 'update'
    return "update"


async def run_quickstart(config, client) -> int:
    """Run QuickStart mode - minimal prompts, sensible defaults."""
    print("QuickStart: Connecting to Discord...")

    try:
        guilds = await client.list_guilds()

        if not guilds:
            raise SetupError(
                "No servers found",
                "Make sure your Discord account has joined some servers",
            )

        # Auto-select first server
        selected = guilds[0]

        print(f"Found {len(guilds)} server(s)")
        print(f"Auto-selected: {selected['name']}")
        print()

        # Save configuration
        config.set_default_server(selected["id"], selected["name"])
        config.mark_setup_complete(mode="quickstart")

        # Create profile template if it doesn't exist
        ensure_profile()

        print("Configuration saved")
        print()
        print("Next: Run 'discord-sync' to download messages")
        print()
        print("Tip: Run 'community-init' to configure bot persona")

        return 0

    except AuthenticationError as e:
        raise SetupError(
            "Authentication failed",
            "Your Discord token may be expired. Get a fresh token from DevTools.",
        ) from e


async def run_advanced(config, client, args) -> int:
    """Run Advanced mode - full customization."""
    print("Advanced: Connecting to Discord...")

    try:
        guilds = await client.list_guilds()

        if not guilds:
            raise SetupError(
                "No servers found",
                "Make sure your Discord account has joined some servers",
            )

        print(f"Found {len(guilds)} server(s):")
        print()

        # Print server list with index
        print(f"{'#':<4} {'ID':<20} {'Name'}")
        print("-" * 60)

        for i, guild in enumerate(guilds, 1):
            print(f"{i:<4} {guild['id']:<20} {guild['name'][:35]}")

        print()

        # Select server
        selected = None

        if args.server:
            # Use specified server
            selected = next((g for g in guilds if g["id"] == args.server), None)
            if not selected:
                raise SetupError(
                    f"Server {args.server} not found",
                    "Check the server ID or run without --server to see available servers",
                )
            print(f"Selected: {selected['name']}")
        elif len(guilds) == 1:
            # Auto-select if only one
            selected = guilds[0]
            print(f"Auto-selected only server: {selected['name']}")
        else:
            # Default to first server in non-interactive mode
            selected = guilds[0]
            print(f"Selecting first server: {selected['name']}")
            print()
            print("Tip: Run with --server SERVER_ID to select a different server")

        print()

        # Show current config values
        print("Configuration:")
        print(f"  Retention days: {config.retention_days}")
        print(f"  Max messages/channel: {config.max_messages_per_channel}")
        print(f"  Max channels/server: {config.max_channels_per_server}")
        print()
        print("To customize these values, edit config/agents.yaml")
        print()

        # Save configuration
        config.set_default_server(selected["id"], selected["name"])
        config.mark_setup_complete(mode="advanced")

        # Create profile template if it doesn't exist
        ensure_profile()

        print("Configuration saved to config/agents.yaml")
        print(f"  Server: {selected['name']} ({selected['id']})")
        print()
        print("Next steps:")
        print("  1. Sync messages: Run 'discord-sync'")
        print("  2. Read messages: Run 'discord-read'")
        print("  3. Or ask Claude: 'Sync my Discord messages'")
        print()
        print("Tip: Run 'community-init' to configure bot persona")

        return 0

    except AuthenticationError as e:
        raise SetupError(
            "Authentication failed",
            "Your Discord token may be expired. Get a fresh token from DevTools.",
        ) from e


async def main(args: argparse.Namespace) -> int:
    """Main entry point."""
    # Check for token before loading config
    import os
    if not os.getenv("DISCORD_USER_TOKEN"):
        print("Discord token not found.", file=sys.stderr)
        print()
        print("To set up your Discord token:", file=sys.stderr)
        print("  1. Open Discord in browser", file=sys.stderr)
        print("  2. Press F12 -> Network tab", file=sys.stderr)
        print("  3. Do any action in Discord", file=sys.stderr)
        print("  4. Find request to discord.com/api", file=sys.stderr)
        print("  5. Copy 'Authorization' header value", file=sys.stderr)
        print()
        print("Then add to .env file:", file=sys.stderr)
        print("  DISCORD_USER_TOKEN=your_token", file=sys.stderr)
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

    # Show token (masked)
    token = config.discord_token
    print(f"Token: {'*' * 20}...{token[-10:]}")
    print()

    # Handle returning user
    if not is_first_run and state.discord_server_configured:
        action = prompt_returning_user(config)
        if action == "keep":
            print("Keeping current configuration.")
            return 0

    # Connect to Discord
    client = DiscordUserClient()

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

    except DiscordClientError as e:
        print(f"Discord error: {e}", file=sys.stderr)
        return 1

    finally:
        await client.close()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Initialize Discord configuration from your account",
        epilog="WARNING: Using a user token may violate Discord's ToS. "
               "For bot persona setup, run 'community-init'."
    )
    parser.add_argument(
        "--mode",
        choices=["quickstart", "advanced"],
        help="Setup mode: quickstart (defaults) or advanced (customize)"
    )
    parser.add_argument(
        "--server",
        metavar="SERVER_ID",
        help="Specific server ID to configure"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

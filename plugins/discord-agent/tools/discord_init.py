#!/usr/bin/env python3
"""Discord init tool - Initialize configuration from Discord account.

Usage:
    python tools/discord_init.py
    python tools/discord_init.py --server SERVER_ID
"""

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.discord_client import DiscordUserClient, DiscordClientError, AuthenticationError


async def init_config(server_id: str = None) -> None:
    """Initialize config/server.yaml from Discord account.

    Args:
        server_id: Optional specific server ID to use
    """
    client = DiscordUserClient()
    # Config is stored in workspace root, not plugin directory
    config_path = Path.cwd() / "config" / "server.yaml"

    try:
        print("Connecting to Discord...")
        guilds = await client.list_guilds()

        if not guilds:
            print("No servers found. Make sure your Discord account has joined some servers.")
            sys.exit(1)

        # Select server
        selected = None

        if server_id:
            # Use specified server
            selected = next((g for g in guilds if g["id"] == server_id), None)
            if not selected:
                print(f"Error: Server {server_id} not found in your account.")
                print("\nAvailable servers:")
                for g in guilds:
                    print(f"  {g['id']} - {g['name']}")
                sys.exit(1)
        elif len(guilds) == 1:
            # Auto-select if only one server
            selected = guilds[0]
            print(f"Auto-selecting only server: {selected['name']}")
        else:
            # Show list and prompt
            print(f"\nFound {len(guilds)} server(s):\n")
            for i, g in enumerate(guilds, 1):
                print(f"  [{i}] {g['name']} ({g['id']})")

            print(f"\nTo select a server, run:")
            print(f"  python tools/discord_init.py --server SERVER_ID")
            print(f"\nOr selecting the first server by default...")
            selected = guilds[0]

        # Save to config with sync limits
        config = {
            "server_id": selected["id"],
            "server_name": selected["name"],
            "data_dir": "./data",
            "retention_days": 30,
            "sync_limits": {
                "max_messages_per_channel": 200,
                "max_channels_per_server": 5,
                "priority_channels": ["general", "announcements"]
            }
        }

        # Ensure config directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)

        print(f"\n✓ Configuration saved to {config_path}")
        print(f"  Server: {selected['name']} ({selected['id']})")
        print(f"  Sync limits: {config['sync_limits']['max_channels_per_server']} channels, "
              f"{config['sync_limits']['max_messages_per_channel']} messages/channel")
        print(f"\nNext steps:")
        print(f"  1. Sync messages: python tools/discord_sync.py")
        print(f"  2. Or ask Claude: 'Sync my Discord messages'")
        print(f"\nTo adjust limits, edit config/server.yaml")

    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Discord configuration from your account"
    )

    parser.add_argument(
        "--server",
        metavar="SERVER_ID",
        help="Specific server ID to configure (lists available if not specified)"
    )

    args = parser.parse_args()

    # Check for token first (in workspace root, not plugin directory)
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        print("Error: .env file not found in workspace root.")
        print("\nCreate .env with your Discord token:")
        print("  cp plugins/discord-agent/.env.example .env")
        print("  # Then edit .env and add your token")
        print("\nTo get your token:")
        print("  1. Open Discord in browser")
        print("  2. Press F12 → Network tab")
        print("  3. Do any action in Discord")
        print("  4. Find request to discord.com/api")
        print("  5. Copy 'Authorization' header value")
        sys.exit(1)

    try:
        asyncio.run(init_config(server_id=args.server))

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

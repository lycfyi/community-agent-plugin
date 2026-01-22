#!/usr/bin/env python3
"""
Discord bot member sync tool.

Syncs complete member list from Discord servers via Gateway API.
Uses discord.py (official) with bot token and Gateway Intents.
Supports servers with 100k+ members.

Usage:
    python member_sync.py --server SERVER_ID [--include-bots]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.gateway_client import GatewayMemberFetcher, GatewayClientError
from lib.member_storage import get_member_storage


async def sync_members(
    server_id: str,
    include_bots: bool = False,
    data_dir: str = ".",
) -> dict:
    """
    Sync members from a Discord server.

    Args:
        server_id: Discord server ID
        include_bots: Whether to include bot accounts
        data_dir: Base data directory

    Returns:
        Dict with sync results
    """
    config = get_config(data_dir)
    storage = get_member_storage(data_dir)

    # Validate bot token
    if not config.has_bot_token():
        print("Error: DISCORD_BOT_TOKEN not set in .env file")
        return {"success": False, "error": "No bot token"}

    fetcher = GatewayMemberFetcher(data_dir)

    try:
        print("Connecting to Discord...")

        # Get server info
        guild_info = await fetcher.get_guild_info(server_id)
        server_name = guild_info["name"]
        estimated_members = guild_info["member_count"]

        print(f"Syncing members from {server_name} ({server_id})...")
        print(f"Estimated members: {estimated_members:,}")
        print()

        # Progress tracking
        def progress_callback(current: int, total: int) -> None:
            pct = (current / total * 100) if total > 0 else 0
            bar_width = 40
            filled = int(bar_width * current / total) if total > 0 else 0
            bar = "=" * filled + " " * (bar_width - filled)
            print(f"\rSyncing... [{bar}] {current:,}/{total:,} ({pct:.1f}%)", end="", flush=True)

        # Fetch members
        import time
        start_time = time.time()

        members = await fetcher.fetch_all_members(
            server_id=server_id,
            include_bots=include_bots,
            progress_callback=progress_callback,
        )

        elapsed = time.time() - start_time
        print()
        print()

        # Count humans vs bots
        humans = sum(1 for m in members if not m.is_bot)
        bots = sum(1 for m in members if m.is_bot)

        # Save to storage
        save_path = storage.save_member_list(members, server_id, server_name)

        print(f"Sync complete in {elapsed:.1f} seconds")
        print(f"- Total members: {len(members):,} ({humans:,} humans, {bots:,} bots)")
        print()
        print(f"Data saved to: {save_path.parent}")

        return {
            "success": True,
            "server_id": server_id,
            "server_name": server_name,
            "total_members": len(members),
            "humans": humans,
            "bots": bots,
            "elapsed": elapsed,
            "save_path": str(save_path),
        }

    except GatewayClientError as e:
        print(f"\nError: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        await fetcher.close()


async def list_servers(data_dir: str = ".") -> list[dict]:
    """List all servers the bot has access to."""
    fetcher = GatewayMemberFetcher(data_dir)

    try:
        print("Connecting to Discord...")
        guilds = await fetcher.list_guilds()

        print(f"\nBot is in {len(guilds)} server(s):\n")
        for guild in guilds:
            print(f"  {guild['name']} ({guild['id']}) - {guild['member_count']:,} members")

        return guilds
    finally:
        await fetcher.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sync Discord server member list using bot token",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List servers the bot can access
    python member_sync.py --list

    # Sync members from a server
    python member_sync.py --server 1234567890

    # Include bot accounts
    python member_sync.py --server 1234567890 --include-bots
        """
    )

    parser.add_argument(
        "--server",
        help="Discord server ID to sync"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List servers the bot can access"
    )
    parser.add_argument(
        "--include-bots",
        action="store_true",
        help="Include bot accounts in the sync"
    )
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Base data directory (default: current directory)"
    )

    args = parser.parse_args()

    # Validate args
    if not args.list and not args.server:
        parser.error("Either --server or --list is required")

    # Run
    try:
        if args.list:
            asyncio.run(list_servers(args.data_dir))
        else:
            result = asyncio.run(sync_members(
                server_id=args.server,
                include_bots=args.include_bots,
                data_dir=args.data_dir,
            ))

            if not result.get("success"):
                sys.exit(1)

    except KeyboardInterrupt:
        print("\nSync cancelled.")
        sys.exit(130)
    except ConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

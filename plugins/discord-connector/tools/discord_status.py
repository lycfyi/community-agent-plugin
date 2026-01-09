#!/usr/bin/env python3
"""Discord status tool - Show connection status and sync health.

Usage:
    python tools/discord_status.py
    python tools/discord_status.py --json
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.storage import get_storage
from lib.discord_client import DiscordUserClient, AuthenticationError


def check_env_token() -> tuple[bool, str]:
    """Check if .env has DISCORD_USER_TOKEN.

    Returns:
        (has_token, message)
    """
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return False, "No .env file found"

    with open(env_path, "r") as f:
        content = f.read()

    if "DISCORD_USER_TOKEN" not in content:
        return False, "DISCORD_USER_TOKEN not in .env"

    # Check if it's set (not just present)
    for line in content.split("\n"):
        if line.startswith("DISCORD_USER_TOKEN="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value and not value.startswith("#"):
                return True, "Token configured"

    return False, "DISCORD_USER_TOKEN is empty"


async def verify_token() -> tuple[bool, str, str | None]:
    """Verify token by connecting to Discord.

    Returns:
        (is_valid, message, username)
    """
    try:
        client = DiscordUserClient()
        await client._ensure_connected()

        # Get current user info
        username = client._bot.user.name if client._bot and client._bot.user else None

        await client.close()
        return True, "Connected", username

    except AuthenticationError:
        return False, "Invalid or expired token", None
    except Exception as e:
        return False, f"Connection error: {str(e)[:50]}", None


def check_config() -> tuple[bool, str | None]:
    """Check if config/server.yaml exists and has server_id.

    Returns:
        (has_config, server_id)
    """
    config_path = Path.cwd() / "config" / "server.yaml"
    if not config_path.exists():
        return False, None

    import yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    server_id = config.get("server_id")
    return True, str(server_id) if server_id else None


def get_sync_status() -> dict:
    """Get sync status from manifest.

    Returns:
        Dict with servers, channels, messages counts and freshness
    """
    storage = get_storage()
    manifest = storage.get_manifest()

    if not manifest or not manifest.get("servers"):
        return {
            "has_data": False,
            "total_servers": 0,
            "total_channels": 0,
            "total_messages": 0,
            "servers": []
        }

    summary = manifest.get("summary", {})
    servers = []

    now = datetime.now(timezone.utc)

    for server in manifest.get("servers", []):
        last_sync_str = server.get("last_sync")
        if last_sync_str:
            try:
                last_sync = datetime.fromisoformat(last_sync_str.replace("Z", "+00:00"))
                hours_ago = (now - last_sync).total_seconds() / 3600

                if hours_ago < 24:
                    freshness = "Fresh"
                    freshness_display = f"{int(hours_ago)}h ago"
                elif hours_ago < 24 * 7:
                    freshness = "Stale"
                    freshness_display = f"{int(hours_ago / 24)}d ago"
                else:
                    freshness = "Old"
                    freshness_display = f"{int(hours_ago / 24)}d ago"
            except:
                freshness = "Unknown"
                freshness_display = "Unknown"
        else:
            freshness = "Never"
            freshness_display = "Never"

        servers.append({
            "name": server.get("name", "Unknown"),
            "id": server.get("id"),
            "messages": server.get("total_messages", 0),
            "channels": server.get("channel_count", 0),
            "freshness": freshness,
            "freshness_display": freshness_display
        })

    return {
        "has_data": True,
        "total_servers": summary.get("total_servers", 0),
        "total_channels": summary.get("total_channels", 0),
        "total_messages": summary.get("total_messages", 0),
        "servers": servers
    }


def format_status(
    token_status: tuple[bool, str],
    connection: tuple[bool, str, str | None],
    config_status: tuple[bool, str | None],
    sync_status: dict,
    as_json: bool = False
) -> str:
    """Format status output."""

    if as_json:
        return json.dumps({
            "token": {
                "configured": token_status[0],
                "message": token_status[1]
            },
            "connection": {
                "connected": connection[0],
                "message": connection[1],
                "username": connection[2]
            },
            "config": {
                "exists": config_status[0],
                "server_id": config_status[1]
            },
            "sync": sync_status
        }, indent=2)

    lines = []
    lines.append("Discord Status")
    lines.append("━" * 40)
    lines.append("")

    # Token status
    token_ok = token_status[0]
    if token_ok and connection[0]:
        username = connection[2] or "unknown"
        lines.append(f"Token:     ✓ Connected as @{username}")
    elif token_ok:
        lines.append(f"Token:     ✗ {connection[1]}")
    else:
        lines.append(f"Token:     ✗ {token_status[1]}")

    # Config status
    if config_status[0]:
        if config_status[1]:
            lines.append(f"Config:    ✓ Server configured ({config_status[1][:20]}...)")
        else:
            lines.append(f"Config:    ✓ Config exists (no default server)")
    else:
        lines.append(f"Config:    ○ Not configured (will auto-create)")

    # Sync status
    if sync_status["has_data"]:
        lines.append(
            f"Data:      ✓ {sync_status['total_servers']} servers, "
            f"{sync_status['total_channels']} channels, "
            f"{sync_status['total_messages']:,} messages"
        )
    else:
        lines.append(f"Data:      ✗ No messages synced yet")

    lines.append("")

    # Server details
    if sync_status["servers"]:
        lines.append("Sync Status:")

        # Calculate column widths
        max_name = max(len(s["name"][:25]) for s in sync_status["servers"])

        for server in sync_status["servers"][:5]:  # Show top 5
            name = server["name"][:25].ljust(max_name)
            freshness = server["freshness_display"].ljust(10)
            status = server["freshness"]
            lines.append(f"  {name}  {freshness}  {status}")

        if len(sync_status["servers"]) > 5:
            lines.append(f"  ... and {len(sync_status['servers']) - 5} more")

    lines.append("")

    # Next steps
    lines.append("Next Steps:")
    if not token_ok:
        lines.append("  1. Get token: https://discordhunt.com/articles/how-to-get-discord-user-token")
        lines.append("  2. Create .env with DISCORD_USER_TOKEN=your_token")
        lines.append("  3. Run /discord-list to see your servers")
    elif not sync_status["has_data"]:
        lines.append("  Run /discord-sync to pull messages")
    else:
        stale_count = sum(1 for s in sync_status["servers"] if s["freshness"] in ("Stale", "Old"))
        if stale_count > 0:
            lines.append(f"  Run /discord-sync to refresh {stale_count} stale server(s)")
        else:
            lines.append("  All data is fresh! Use /discord-chat-summary to analyze")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(
        description="Show Discord connection status and sync health"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    args = parser.parse_args()

    # Check token
    token_status = check_env_token()

    # Verify connection (only if token exists)
    if token_status[0]:
        connection = await verify_token()
    else:
        connection = (False, "No token", None)

    # Check config
    config_status = check_config()

    # Get sync status
    sync_status = get_sync_status()

    # Output
    print(format_status(
        token_status,
        connection,
        config_status,
        sync_status,
        as_json=args.json
    ))


if __name__ == "__main__":
    asyncio.run(main())

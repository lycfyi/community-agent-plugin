#!/usr/bin/env python3
"""Community Agent status tool - Show unified status across all platforms.

Usage:
    python community_status.py

Output:
    - Overview of all configured platforms (Discord, Telegram)
    - Setup state and last sync times
    - Paths to config and data files

Exit Codes:
    0 - Success
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, get_setup_state
from lib.profile import load_profile


def format_time_ago(dt: datetime | None) -> str:
    """Format datetime as relative time."""
    if dt is None:
        return "Never"

    now = datetime.now()
    delta = now - dt

    if delta.days > 0:
        return f"{delta.days} day(s) ago"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour(s) ago"
    elif delta.seconds >= 60:
        minutes = delta.seconds // 60
        return f"{minutes} minute(s) ago"
    else:
        return "Just now"


def check_discord_status(state) -> tuple[str, str]:
    """Check Discord configuration status.

    Returns:
        Tuple of (icon, status_message)
    """
    if not state.discord_token_set:
        return "✗", "Not configured (missing token)"

    if not state.discord_server_configured:
        return "○", "Token set, server not configured"

    # Get server name from config
    try:
        config = get_config()
        server_name = config._config.get("discord", {}).get("default_server_name", "Unknown")
        return "✓", f"Connected ({server_name})"
    except Exception:
        return "✓", "Connected"


def check_telegram_status(state) -> tuple[str, str]:
    """Check Telegram configuration status.

    Returns:
        Tuple of (icon, status_message)
    """
    if not state.telegram_credentials_set:
        return "✗", "Not configured (missing credentials)"

    if not state.telegram_group_configured:
        return "○", "Credentials set, group not configured"

    # Get group name from config
    try:
        config = get_config()
        group_name = config._config.get("telegram", {}).get("default_group_name", "Unknown")
        return "✓", f"Connected ({group_name})"
    except Exception:
        return "✓", "Connected"


def get_last_sync_time() -> str:
    """Get the most recent sync time from data directories."""
    local_dir = os.getenv("CLAUDE_LOCAL_DIR")
    base_dir = Path(local_dir) if local_dir else Path.cwd()
    data_dir = base_dir / "data"

    if not data_dir.exists():
        return "No data synced yet"

    # Look for any sync_state.yaml files
    latest_time = None

    for sync_file in data_dir.rglob("sync_state.yaml"):
        try:
            mtime = datetime.fromtimestamp(sync_file.stat().st_mtime)
            if latest_time is None or mtime > latest_time:
                latest_time = mtime
        except Exception:
            continue

    return format_time_ago(latest_time)


def count_messages() -> int:
    """Count total messages in all message files."""
    local_dir = os.getenv("CLAUDE_LOCAL_DIR")
    base_dir = Path(local_dir) if local_dir else Path.cwd()
    data_dir = base_dir / "data"

    if not data_dir.exists():
        return 0

    total = 0
    for msg_file in data_dir.rglob("messages.md"):
        try:
            content = msg_file.read_text()
            # Count message blocks (lines starting with ### that have time)
            total += content.count("\n### ")
        except Exception:
            continue

    return total


def main() -> int:
    """Main entry point."""
    # Get paths
    local_dir = os.getenv("CLAUDE_LOCAL_DIR")
    base_dir = Path(local_dir) if local_dir else Path.cwd()
    config_path = base_dir / "config" / "agents.yaml"
    profile_path = base_dir / "config" / "PROFILE.md"
    data_dir = base_dir / "data"

    # Get state
    state = get_setup_state()

    # Check platform status
    discord_icon, discord_status = check_discord_status(state)
    telegram_icon, telegram_status = check_telegram_status(state)

    # Get sync info
    last_sync = get_last_sync_time()
    message_count = count_messages()

    # Print header
    print("Community Agent Status")
    print("━" * 50)
    print()

    # Platform status
    print("Platforms:")
    print(f"  {discord_icon} Discord:  {discord_status}")
    print(f"  {telegram_icon} Telegram: {telegram_status}")
    print()

    # Sync info
    print("Sync:")
    print(f"  Last sync:     {last_sync}")
    if message_count > 0:
        print(f"  Messages:      {message_count:,}")
    print()

    # Files
    print("Files:")
    print(f"  Config:   {config_path}")
    if profile_path.exists():
        print(f"  Profile:  {profile_path}")
    else:
        print(f"  Profile:  (not created)")
    print(f"  Data:     {data_dir}")
    print()

    # Setup state
    if state.is_first_run:
        print("Setup: Not complete")
        print()
        print("Run 'discord-init' or 'telegram-init' to get started.")
    else:
        mode = state.setup_mode or "unknown"
        print(f"Setup: Complete ({mode} mode)")

    print()

    # Help
    if not state.discord_ready and not state.telegram_ready:
        print("Need help? Run 'discord-doctor' or 'telegram-doctor'")
    elif not state.discord_ready:
        print("Discord issues? Run 'discord-doctor'")
    elif not state.telegram_ready:
        print("Telegram issues? Run 'telegram-doctor'")

    return 0


if __name__ == "__main__":
    sys.exit(main())

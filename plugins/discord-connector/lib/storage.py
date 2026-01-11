"""Storage service for Markdown/YAML file I/O."""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .config import get_config
from .markdown_formatter import (
    format_channel_header,
    format_date_header,
    format_message,
    group_messages_by_date
)


class SyncMode(Enum):
    """Sync operation modes."""

    QUICK = "quick"  # Fast initial sync with limited messages
    FULL = "full"  # Complete historical sync
    INCREMENTAL = "incremental"  # Only new messages since last sync
    GAP_FILL = "gap_fill"  # Fill missing date ranges


# Default message limit for DMs (privacy-conscious)
DM_DEFAULT_LIMIT = 100


@dataclass
class SyncProgress:
    """Real-time progress tracking for sync operations."""

    total_channels: int
    completed_channels: int = 0
    current_channel: Optional[str] = None
    messages_fetched: int = 0
    start_time: Optional[datetime] = None
    channel_progress: Dict[str, int] = field(default_factory=dict)
    channel_status: Dict[str, str] = field(default_factory=dict)

    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_channels == 0:
            return 100.0
        return (self.completed_channels / self.total_channels) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()

    @property
    def eta_seconds(self) -> Optional[float]:
        """Estimate remaining time in seconds."""
        if self.completed_channels == 0 or self.elapsed_seconds == 0:
            return None
        rate = self.completed_channels / self.elapsed_seconds
        remaining = self.total_channels - self.completed_channels
        return remaining / rate if rate > 0 else None


class StorageError(Exception):
    """Storage error."""
    pass


class Storage:
    """Storage service for Discord sync data."""

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize storage.

        Args:
            base_dir: Base data directory. Uses config if not provided.
        """
        if base_dir is None:
            config = get_config()
            base_dir = config.data_dir
        self._base_dir = Path(base_dir)
        # DMs go to a separate root directory
        self._dm_base_dir = Path(base_dir).parent / "dms" / "discord"

    def _ensure_dir(self, path: Path):
        """Ensure a directory exists."""
        path.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use as directory/filename."""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")
        return name.lower().strip()

    def _slugify(self, name: str) -> str:
        """Convert a name to a URL-friendly slug."""
        import re
        # Remove special characters, keep alphanumeric and spaces
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        # Replace spaces with hyphens
        slug = re.sub(r'[\s_]+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        return slug

    def _get_server_dir(self, server_id: str, server_name: Optional[str] = None) -> Path:
        """Get server directory path with human-readable slug.

        Format: {server_id}-{slug}
        Example: 662267976984297473-midjourney

        Args:
            server_id: Discord server ID
            server_name: Optional server name for slug (looked up if not provided)

        Returns:
            Path to server directory
        """
        # Try to find existing directory first (may already have slug)
        for existing in self._base_dir.glob(f"{server_id}*"):
            if existing.is_dir():
                return existing

        # Build new directory name with slug
        if server_name:
            slug = self._slugify(server_name)
            return self._base_dir / f"{server_id}-{slug}"

        # Fallback to just server_id
        return self._base_dir / server_id

    # === Sync State ===

    def get_sync_state(self, server_id: str, server_name: Optional[str] = None) -> dict:
        """Get sync state for a server.

        Args:
            server_id: Discord server ID
            server_name: Optional server name for directory lookup

        Returns:
            Sync state dict, or empty dict if not found
        """
        server_dir = self._get_server_dir(server_id, server_name)
        state_file = server_dir / "sync_state.yaml"
        if not state_file.exists():
            return {}

        with open(state_file, "r") as f:
            return yaml.safe_load(f) or {}

    def save_sync_state(self, server_id: str, state: dict, server_name: Optional[str] = None):
        """Save sync state for a server.

        Args:
            server_id: Discord server ID
            state: Sync state dict
            server_name: Optional server name for directory slug
        """
        server_dir = self._get_server_dir(server_id, server_name or state.get("server_name"))
        self._ensure_dir(server_dir)

        state_file = server_dir / "sync_state.yaml"
        with open(state_file, "w") as f:
            yaml.safe_dump(state, f, default_flow_style=False)

    def get_channel_sync_state(
        self,
        server_id: str,
        channel_name: str
    ) -> dict:
        """Get sync state for a specific channel.

        Args:
            server_id: Discord server ID
            channel_name: Channel name

        Returns:
            Channel sync state dict, or empty dict if not found
        """
        state = self.get_sync_state(server_id)
        channels = state.get("channels", {})
        return channels.get(self._sanitize_name(channel_name), {})

    def update_channel_sync_state(
        self,
        server_id: str,
        server_name: str,
        channel_name: str,
        channel_id: str,
        last_message_id: str,
        message_count: int,
        sync_mode: Optional[SyncMode] = None,
        oldest_synced_date: Optional[date] = None,
        newest_synced_date: Optional[date] = None,
        oldest_message_id: Optional[str] = None
    ):
        """Update sync state for a channel.

        Args:
            server_id: Discord server ID
            server_name: Server display name
            channel_name: Channel name
            channel_id: Channel ID
            last_message_id: Last synced message ID
            message_count: Total message count for channel
            sync_mode: The mode used for this sync operation
            oldest_synced_date: Oldest date in synced range
            newest_synced_date: Newest date in synced range
            oldest_message_id: Oldest message ID synced
        """
        state = self.get_sync_state(server_id)

        # Update server info
        state["server_id"] = server_id
        state["server_name"] = server_name
        state["last_sync"] = datetime.now(timezone.utc).isoformat()

        # Update channel info
        if "channels" not in state:
            state["channels"] = {}

        safe_name = self._sanitize_name(channel_name)
        existing = state["channels"].get(safe_name, {})
        existing_count = existing.get("message_count", 0)

        # Preserve and extend date ranges
        existing_oldest = existing.get("oldest_synced_date")
        existing_newest = existing.get("newest_synced_date")

        if oldest_synced_date:
            if existing_oldest:
                existing_oldest_date = date.fromisoformat(existing_oldest)
                oldest_synced_date = min(existing_oldest_date, oldest_synced_date)
        elif existing_oldest:
            oldest_synced_date = date.fromisoformat(existing_oldest)

        if newest_synced_date:
            if existing_newest:
                existing_newest_date = date.fromisoformat(existing_newest)
                newest_synced_date = max(existing_newest_date, newest_synced_date)
        elif existing_newest:
            newest_synced_date = date.fromisoformat(existing_newest)

        state["channels"][safe_name] = {
            "id": channel_id,
            "name": channel_name,
            "message_count": existing_count + message_count,
            "last_message_id": last_message_id,
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "sync_mode": sync_mode.value if sync_mode else existing.get("sync_mode"),
            "oldest_synced_date": oldest_synced_date.isoformat() if oldest_synced_date else None,
            "newest_synced_date": newest_synced_date.isoformat() if newest_synced_date else None,
            "oldest_message_id": oldest_message_id or existing.get("oldest_message_id")
        }

        self.save_sync_state(server_id, state)

    def has_any_sync(self, server_id: str) -> bool:
        """Check if a server has any previous sync data.

        Args:
            server_id: Discord server ID

        Returns:
            True if any channels have been synced
        """
        state = self.get_sync_state(server_id)
        channels = state.get("channels", {})
        return len(channels) > 0 and any(
            ch.get("last_message_id") for ch in channels.values()
        )

    def is_channel_up_to_date(
        self,
        server_id: str,
        channel_name: str,
        target_date: Optional[date] = None
    ) -> bool:
        """Check if a channel is already synced up to the target date.

        Args:
            server_id: Discord server ID
            channel_name: Channel name
            target_date: Target date to check (defaults to today)

        Returns:
            True if channel is up to date
        """
        if target_date is None:
            target_date = date.today()

        channel_state = self.get_channel_sync_state(server_id, channel_name)
        newest = channel_state.get("newest_synced_date")
        if not newest:
            return False
        return date.fromisoformat(newest) >= target_date

    def get_last_message_id(
        self,
        server_id: str,
        channel_name: str
    ) -> Optional[str]:
        """Get the last synced message ID for a channel.

        Args:
            server_id: Discord server ID
            channel_name: Channel name

        Returns:
            Last message ID, or None if not synced
        """
        channel_state = self.get_channel_sync_state(server_id, channel_name)
        return channel_state.get("last_message_id")

    # === Messages ===

    def get_messages_file(
        self,
        server_id: str,
        channel_name: str,
        server_name: Optional[str] = None
    ) -> Path:
        """Get path to messages file for a channel.

        Args:
            server_id: Discord server ID
            channel_name: Channel name
            server_name: Optional server name for directory lookup

        Returns:
            Path to messages.md file
        """
        safe_name = self._sanitize_name(channel_name)
        server_dir = self._get_server_dir(server_id, server_name)
        channel_dir = server_dir / safe_name
        return channel_dir / "messages.md"

    def append_messages(
        self,
        server_id: str,
        server_name: str,
        channel_id: str,
        channel_name: str,
        messages: List[dict]
    ):
        """Append messages to a channel's messages file.

        Args:
            server_id: Discord server ID
            server_name: Server display name
            channel_id: Channel ID
            channel_name: Channel name
            messages: List of message dicts to append
        """
        if not messages:
            return

        safe_name = self._sanitize_name(channel_name)
        server_dir = self._get_server_dir(server_id, server_name)
        channel_dir = server_dir / safe_name
        self._ensure_dir(channel_dir)

        messages_file = channel_dir / "messages.md"

        # Group messages by date
        date_groups = group_messages_by_date(messages)

        # If file doesn't exist, create with header
        if not messages_file.exists():
            now = datetime.now(timezone.utc).isoformat()
            header = format_channel_header(
                channel_name=channel_name,
                channel_id=channel_id,
                server_name=server_name,
                server_id=server_id,
                last_sync=now
            )
            with open(messages_file, "w") as f:
                f.write(header)

        # Read existing content to find where to insert
        with open(messages_file, "r") as f:
            existing_content = f.read()

        # Build new content to append
        new_lines = []

        # Sort dates (oldest first for appending)
        sorted_dates = sorted(date_groups.keys())

        for date_str in sorted_dates:
            # Check if this date section already exists
            date_header = format_date_header(date_str)

            if date_header in existing_content:
                # Find the date section and append to it
                # For now, just append at the end of the file
                pass

            new_lines.append("")
            new_lines.append(date_header)
            new_lines.append("")

            # Sort messages by timestamp (oldest first)
            day_messages = sorted(
                date_groups[date_str],
                key=lambda m: m.get("timestamp", "")
            )

            for msg in day_messages:
                new_lines.append(format_message(msg))
                new_lines.append("")

        # Append to file
        with open(messages_file, "a") as f:
            f.write("\n".join(new_lines))

        # Update last_message_id tracking
        last_msg = messages[-1]
        self.update_channel_sync_state(
            server_id=server_id,
            server_name=server_name,
            channel_name=channel_name,
            channel_id=channel_id,
            last_message_id=last_msg["id"],
            message_count=len(messages)
        )

    def read_messages(
        self,
        server_id: str,
        channel_name: str,
        last_n: Optional[int] = None
    ) -> str:
        """Read messages from a channel's messages file.

        Args:
            server_id: Discord server ID
            channel_name: Channel name
            last_n: Only return last N messages (optional)

        Returns:
            Messages file content (or subset if last_n specified)
        """
        messages_file = self.get_messages_file(server_id, channel_name)

        if not messages_file.exists():
            raise StorageError(
                f"No messages found for channel '{channel_name}' "
                f"in server {server_id}. Run sync first."
            )

        with open(messages_file, "r") as f:
            content = f.read()

        if last_n is None:
            return content

        # Extract last N message blocks (### headers indicate messages)
        lines = content.split("\n")
        message_indices = []

        for i, line in enumerate(lines):
            if line.startswith("### "):
                message_indices.append(i)

        if not message_indices:
            return content

        # Get starting index for last N messages
        start_idx = message_indices[-last_n] if len(message_indices) >= last_n else 0

        # Keep header (everything before first message)
        if message_indices:
            header_end = message_indices[0]
            header = "\n".join(lines[:header_end])
            messages = "\n".join(lines[start_idx:])
            return header + "\n" + messages

        return content

    def search_messages(
        self,
        server_id: str,
        channel_name: str,
        keyword: str
    ) -> List[str]:
        """Search messages for a keyword.

        Args:
            server_id: Discord server ID
            channel_name: Channel name
            keyword: Search keyword

        Returns:
            List of matching message blocks
        """
        content = self.read_messages(server_id, channel_name)

        # Split into message blocks
        lines = content.split("\n")
        current_block = []
        blocks = []
        in_message = False

        for line in lines:
            if line.startswith("### "):
                if current_block and in_message:
                    blocks.append("\n".join(current_block))
                current_block = [line]
                in_message = True
            elif line.startswith("## ") or line.startswith("# "):
                if current_block and in_message:
                    blocks.append("\n".join(current_block))
                current_block = []
                in_message = False
            elif in_message:
                current_block.append(line)

        if current_block and in_message:
            blocks.append("\n".join(current_block))

        # Filter by keyword
        keyword_lower = keyword.lower()
        matches = [
            block for block in blocks
            if keyword_lower in block.lower()
        ]

        return matches

    # === Server Metadata ===

    def save_server_metadata(
        self,
        server_id: str,
        server_name: str,
        icon: Optional[str] = None,
        member_count: int = 0
    ):
        """Save server metadata YAML file.

        Args:
            server_id: Discord server ID
            server_name: Server display name
            icon: Icon URL
            member_count: Member count
        """
        server_dir = self._get_server_dir(server_id, server_name)
        self._ensure_dir(server_dir)

        metadata = {
            "id": server_id,
            "name": server_name,
            "icon": icon,
            "member_count": member_count,
            "synced_at": datetime.now(timezone.utc).isoformat()
        }

        with open(server_dir / "server.yaml", "w") as f:
            yaml.safe_dump(metadata, f, default_flow_style=False)

    def save_channel_metadata(
        self,
        server_id: str,
        channel_id: str,
        channel_name: str,
        category: Optional[str] = None,
        server_name: Optional[str] = None
    ):
        """Save channel metadata YAML file.

        Args:
            server_id: Discord server ID
            channel_id: Channel ID
            channel_name: Channel name
            category: Category name
            server_name: Optional server name for directory lookup
        """
        safe_name = self._sanitize_name(channel_name)
        server_dir = self._get_server_dir(server_id, server_name)
        channel_dir = server_dir / safe_name
        self._ensure_dir(channel_dir)

        metadata = {
            "id": channel_id,
            "name": channel_name,
            "category": category,
            "synced_at": datetime.now(timezone.utc).isoformat()
        }

        with open(channel_dir / "channel.yaml", "w") as f:
            yaml.safe_dump(metadata, f, default_flow_style=False)


    # === Manifest (All-in-One Overview) ===

    def update_manifest(self):
        """Update the manifest.yaml with overview of all synced data.

        Creates/updates data/manifest.yaml with:
        - All synced servers and their channels
        - Message counts and last sync times
        - Quick access paths
        """
        self._ensure_dir(self._base_dir)
        manifest_path = self._base_dir / "manifest.yaml"

        # Scan all server directories
        servers = []
        total_messages = 0
        total_channels = 0

        for server_dir in self._base_dir.iterdir():
            if not server_dir.is_dir():
                continue

            # Skip hidden directories
            if server_dir.name.startswith('.'):
                continue

            # Read sync state
            sync_state_file = server_dir / "sync_state.yaml"
            if not sync_state_file.exists():
                continue

            with open(sync_state_file, "r") as f:
                sync_state = yaml.safe_load(f) or {}

            # Read server metadata if available
            server_yaml = server_dir / "server.yaml"
            server_meta = {}
            if server_yaml.exists():
                with open(server_yaml, "r") as f:
                    server_meta = yaml.safe_load(f) or {}

            # Build channel list
            channels_data = sync_state.get("channels", {})
            channels = []
            server_message_count = 0

            # Track server-wide date range
            server_oldest_date = None
            server_newest_date = None

            for channel_key, channel_info in channels_data.items():
                msg_count = channel_info.get("message_count", 0)
                server_message_count += msg_count

                # Get channel date range
                ch_oldest = channel_info.get("oldest_synced_date")
                ch_newest = channel_info.get("newest_synced_date")

                channel_entry = {
                    "name": channel_info.get("name", channel_key),
                    "id": channel_info.get("id"),
                    "message_count": msg_count,
                    "last_sync": channel_info.get("last_sync_at"),
                    "path": f"{server_dir.name}/{channel_key}/messages.md"
                }

                # Add date range if available
                if ch_oldest or ch_newest:
                    channel_entry["date_range"] = {
                        "first_message": ch_oldest,
                        "last_message": ch_newest
                    }

                    # Update server-wide date range
                    if ch_oldest:
                        ch_oldest_date = date.fromisoformat(ch_oldest)
                        if server_oldest_date is None or ch_oldest_date < server_oldest_date:
                            server_oldest_date = ch_oldest_date
                    if ch_newest:
                        ch_newest_date = date.fromisoformat(ch_newest)
                        if server_newest_date is None or ch_newest_date > server_newest_date:
                            server_newest_date = ch_newest_date

                channels.append(channel_entry)

            total_messages += server_message_count
            total_channels += len(channels)

            # Sort channels by message count (most active first)
            channels.sort(key=lambda c: c.get("message_count", 0), reverse=True)

            server_entry = {
                "name": sync_state.get("server_name") or server_meta.get("name"),
                "id": sync_state.get("server_id") or server_meta.get("id"),
                "directory": server_dir.name,
                "member_count": server_meta.get("member_count"),
                "icon": server_meta.get("icon"),
                "last_sync": sync_state.get("last_sync"),
                "total_messages": server_message_count,
                "channel_count": len(channels),
                "channels": channels
            }

            # Add server-wide date range if available
            if server_oldest_date or server_newest_date:
                days_covered = 0
                if server_oldest_date and server_newest_date:
                    days_covered = (server_newest_date - server_oldest_date).days + 1

                server_entry["date_range"] = {
                    "first_message": server_oldest_date.isoformat() if server_oldest_date else None,
                    "last_message": server_newest_date.isoformat() if server_newest_date else None,
                    "days_covered": days_covered
                }

            servers.append(server_entry)

        # Sort servers by total messages (most active first)
        servers.sort(key=lambda s: s.get("total_messages", 0), reverse=True)

        # Calculate overall date coverage across all servers
        overall_oldest = None
        overall_newest = None
        for s in servers:
            dr = s.get("date_range", {})
            if dr.get("first_message"):
                s_oldest = date.fromisoformat(dr["first_message"])
                if overall_oldest is None or s_oldest < overall_oldest:
                    overall_oldest = s_oldest
            if dr.get("last_message"):
                s_newest = date.fromisoformat(dr["last_message"])
                if overall_newest is None or s_newest > overall_newest:
                    overall_newest = s_newest

        overall_days = 0
        if overall_oldest and overall_newest:
            overall_days = (overall_newest - overall_oldest).days + 1

        # Build manifest
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_servers": len(servers),
                "total_channels": total_channels,
                "total_messages": total_messages,
                "date_coverage": {
                    "oldest_message": overall_oldest.isoformat() if overall_oldest else None,
                    "newest_message": overall_newest.isoformat() if overall_newest else None,
                    "total_days": overall_days
                }
            },
            "servers": servers
        }

        # Write manifest
        with open(manifest_path, "w") as f:
            yaml.safe_dump(manifest, f, default_flow_style=False, sort_keys=False)

        return manifest

    def get_manifest(self) -> dict:
        """Get the current manifest data.

        Returns:
            Manifest dict, or empty dict if not found
        """
        manifest_path = self._base_dir / "manifest.yaml"
        if not manifest_path.exists():
            return self.update_manifest()

        with open(manifest_path, "r") as f:
            return yaml.safe_load(f) or {}

    # === DM Storage ===

    def _get_dm_dir(self, user_id: str, username: Optional[str] = None) -> Path:
        """Get DM directory path with human-readable slug.

        Format: {user_id}-{slug}
        Example: 123456789-alice

        Args:
            user_id: Discord user ID
            username: Optional username for slug

        Returns:
            Path to DM directory
        """
        # Try to find existing directory first
        for existing in self._dm_base_dir.glob(f"{user_id}*"):
            if existing.is_dir():
                return existing

        # Build new directory name with slug
        if username:
            slug = self._slugify(username)
            return self._dm_base_dir / f"{user_id}-{slug}"

        # Fallback to just user_id
        return self._dm_base_dir / str(user_id)

    def save_dm_metadata(
        self,
        user_id: str,
        username: str,
        display_name: str,
        avatar: Optional[str] = None
    ) -> None:
        """Save DM user metadata YAML file.

        Args:
            user_id: Discord user ID
            username: Username
            display_name: Display name
            avatar: Avatar URL
        """
        dm_dir = self._get_dm_dir(user_id, username)
        self._ensure_dir(dm_dir)

        metadata = {
            "id": user_id,
            "username": username,
            "display_name": display_name,
            "avatar": avatar,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(dm_dir / "user.yaml", "w") as f:
            yaml.safe_dump(metadata, f, default_flow_style=False)

    def get_dm_sync_state(self, user_id: str, username: Optional[str] = None) -> dict:
        """Get sync state for a DM.

        Args:
            user_id: Discord user ID
            username: Optional username for directory lookup

        Returns:
            Sync state dict, or empty dict if not found
        """
        dm_dir = self._get_dm_dir(user_id, username)
        state_file = dm_dir / "sync_state.yaml"
        if not state_file.exists():
            return {}

        with open(state_file, "r") as f:
            return yaml.safe_load(f) or {}

    def save_dm_sync_state(self, user_id: str, state: dict, username: Optional[str] = None) -> None:
        """Save sync state for a DM.

        Args:
            user_id: Discord user ID
            state: Sync state dict
            username: Optional username for directory slug
        """
        dm_dir = self._get_dm_dir(user_id, username or state.get("username"))
        self._ensure_dir(dm_dir)

        state_file = dm_dir / "sync_state.yaml"
        with open(state_file, "w") as f:
            yaml.safe_dump(state, f, default_flow_style=False)

    def get_dm_last_message_id(self, user_id: str) -> Optional[str]:
        """Get last synced message ID for DM incremental sync.

        Args:
            user_id: Discord user ID

        Returns:
            Last message ID, or None if never synced
        """
        state = self.get_dm_sync_state(user_id)
        return state.get("last_message_id")

    def append_dm_messages(
        self,
        user_id: str,
        username: str,
        display_name: str,
        channel_id: str,
        messages: List[dict]
    ) -> None:
        """Append DM messages to storage.

        Args:
            user_id: Discord user ID
            username: Username
            display_name: Display name
            channel_id: DM channel ID
            messages: List of message dicts to append
        """
        if not messages:
            return

        dm_dir = self._get_dm_dir(user_id, username)
        self._ensure_dir(dm_dir)

        messages_file = dm_dir / "messages.md"

        # Group messages by date
        date_groups = group_messages_by_date(messages)

        # If file doesn't exist, create with header
        if not messages_file.exists():
            now = datetime.now(timezone.utc).isoformat()

            header = f"""---
user_id: {user_id}
username: {username}
display_name: {display_name}
channel_id: {channel_id}
type: dm
platform: discord
last_sync: {now}
---

# DM with {display_name}

"""
            with open(messages_file, "w") as f:
                f.write(header)

        # Build new content to append
        new_lines = []

        # Sort dates (oldest first for appending)
        sorted_dates = sorted(date_groups.keys())

        for date_str in sorted_dates:
            new_lines.append("")
            new_lines.append(format_date_header(date_str))
            new_lines.append("")

            # Sort messages by timestamp (oldest first)
            day_messages = sorted(
                date_groups[date_str],
                key=lambda m: m.get("timestamp", "")
            )

            for msg in day_messages:
                new_lines.append(format_message(msg))
                new_lines.append("")

        # Append to file
        with open(messages_file, "a") as f:
            f.write("\n".join(new_lines))

        # Update sync state
        last_msg = messages[-1]
        state = self.get_dm_sync_state(user_id, username)
        state["user_id"] = user_id
        state["username"] = username
        state["display_name"] = display_name
        state["channel_id"] = channel_id
        state["last_message_id"] = last_msg["id"]
        state["message_count"] = state.get("message_count", 0) + len(messages)
        state["last_sync"] = datetime.now(timezone.utc).isoformat()
        self.save_dm_sync_state(user_id, state, username)

    def update_dm_manifest(self) -> dict:
        """Update DM manifest.yaml with overview of all synced DMs.

        Returns:
            Generated manifest dict
        """
        self._ensure_dir(self._dm_base_dir)
        manifest_path = self._dm_base_dir / "manifest.yaml"

        # Scan all DM directories
        dms = []
        total_messages = 0

        for dm_dir in self._dm_base_dir.iterdir():
            if not dm_dir.is_dir():
                continue

            # Skip hidden directories
            if dm_dir.name.startswith('.'):
                continue

            # Read sync state
            sync_state_file = dm_dir / "sync_state.yaml"
            if not sync_state_file.exists():
                continue

            with open(sync_state_file, "r") as f:
                sync_state = yaml.safe_load(f) or {}

            # Read user metadata if available
            user_yaml = dm_dir / "user.yaml"
            user_meta = {}
            if user_yaml.exists():
                with open(user_yaml, "r") as f:
                    user_meta = yaml.safe_load(f) or {}

            message_count = sync_state.get("message_count", 0)
            total_messages += message_count

            dms.append({
                "user_id": sync_state.get("user_id") or user_meta.get("id"),
                "username": sync_state.get("username") or user_meta.get("username"),
                "display_name": sync_state.get("display_name") or user_meta.get("display_name"),
                "directory": dm_dir.name,
                "last_sync": sync_state.get("last_sync"),
                "message_count": message_count,
            })

        # Sort DMs by message count (most active first)
        dms.sort(key=lambda d: d.get("message_count", 0), reverse=True)

        # Build manifest
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_users": len(dms),
                "total_messages": total_messages,
                "platform": "discord",
            },
            "users": dms,
        }

        # Write manifest
        with open(manifest_path, "w") as f:
            yaml.safe_dump(manifest, f, default_flow_style=False, sort_keys=False)

        return manifest


# Global storage instance
_storage: Optional[Storage] = None


def get_storage() -> Storage:
    """Get global storage instance."""
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage

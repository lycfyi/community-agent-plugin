"""Storage service for Telegram messages in Markdown/YAML format.

Implements IStorage contract from specs/003-telegram-integrate/contracts/storage.py
Compatible with discord-agent storage format for cross-platform support.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .config import get_config
from .markdown_formatter import (
    format_group_header,
    format_date_header,
    format_message,
    group_messages_by_date,
)


class StorageError(Exception):
    """Storage operation failed."""
    pass


class Storage:
    """Storage service for Telegram sync data."""

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize storage.

        Args:
            base_dir: Base data directory. Uses config if not provided.
        """
        if base_dir is None:
            config = get_config()
            base_dir = config.data_dir
        self._base_dir = Path(base_dir)

    def _ensure_dir(self, path: Path) -> None:
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
        # Remove special characters, keep alphanumeric and spaces
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        # Replace spaces with hyphens
        slug = re.sub(r'[\s_]+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        return slug[:50]  # Limit length

    def _get_group_dir(self, group_id: int, group_name: Optional[str] = None) -> Path:
        """Get group directory path with human-readable slug.

        Format: {group_id}-{slug}
        Example: 1234567890-my-group

        Args:
            group_id: Telegram group ID
            group_name: Optional group name for slug

        Returns:
            Path to group directory
        """
        # Try to find existing directory first
        for existing in self._base_dir.glob(f"{group_id}*"):
            if existing.is_dir():
                return existing

        # Build new directory name with slug
        if group_name:
            slug = self._slugify(group_name)
            return self._base_dir / f"{group_id}-{slug}"

        # Fallback to just group_id
        return self._base_dir / str(group_id)

    # === Sync State ===

    def get_sync_state(self, group_id: int, group_name: Optional[str] = None) -> dict:
        """Get sync state for a group.

        Args:
            group_id: Telegram group ID
            group_name: Optional group name for directory lookup

        Returns:
            Sync state dict, or empty dict if not found
        """
        group_dir = self._get_group_dir(group_id, group_name)
        state_file = group_dir / "sync_state.yaml"
        if not state_file.exists():
            return {}

        with open(state_file, "r") as f:
            return yaml.safe_load(f) or {}

    def save_sync_state(self, group_id: int, state: dict, group_name: Optional[str] = None) -> None:
        """Save sync state for a group.

        Args:
            group_id: Telegram group ID
            state: Sync state dict
            group_name: Optional group name for directory slug
        """
        group_dir = self._get_group_dir(group_id, group_name or state.get("group_name"))
        self._ensure_dir(group_dir)

        state_file = group_dir / "sync_state.yaml"
        with open(state_file, "w") as f:
            yaml.safe_dump(state, f, default_flow_style=False)

    def get_last_message_id(self, group_id: int, topic_name: str = "general") -> Optional[int]:
        """Get last synced message ID for incremental sync.

        Args:
            group_id: Telegram group ID
            topic_name: Topic name (default "general" for non-forum groups)

        Returns:
            Last message ID, or None if never synced
        """
        state = self.get_sync_state(group_id)
        channels = state.get("channels", {})
        channel_state = channels.get(self._sanitize_name(topic_name), {})
        last_id = channel_state.get("last_message_id")
        return int(last_id) if last_id else None

    def update_channel_sync_state(
        self,
        group_id: int,
        group_name: str,
        topic_name: str,
        topic_id: Optional[int],
        last_message_id: int,
        message_count: int
    ) -> None:
        """Update sync state after syncing a topic/channel.

        Args:
            group_id: Telegram group ID
            group_name: Group display name
            topic_name: Topic name ("general" for whole group)
            topic_id: Topic ID (None for non-forum groups)
            last_message_id: Last synced message ID
            message_count: Number of new messages synced
        """
        state = self.get_sync_state(group_id)

        # Update group info
        state["group_id"] = group_id
        state["group_name"] = group_name
        state["last_sync"] = datetime.now(timezone.utc).isoformat()

        # Update channel/topic info
        if "channels" not in state:
            state["channels"] = {}

        safe_name = self._sanitize_name(topic_name)
        existing = state["channels"].get(safe_name, {})
        existing_count = existing.get("message_count", 0)

        state["channels"][safe_name] = {
            "topic_id": topic_id,
            "name": topic_name,
            "last_message_id": last_message_id,
            "message_count": existing_count + message_count,
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
        }

        self.save_sync_state(group_id, state, group_name)

    # === Messages ===

    def get_messages_file(
        self,
        group_id: int,
        topic_name: str = "general",
        group_name: Optional[str] = None
    ) -> Path:
        """Get path to messages file.

        Args:
            group_id: Telegram group ID
            topic_name: Topic name ("general" for whole group)
            group_name: Optional group name for directory lookup

        Returns:
            Path to messages.md file (may not exist yet)
        """
        group_dir = self._get_group_dir(group_id, group_name)

        # For non-topic groups, use messages.md directly
        if topic_name == "general":
            return group_dir / "messages.md"

        # For topic groups, use topic subdirectory
        safe_name = self._sanitize_name(topic_name)
        return group_dir / safe_name / "messages.md"

    def append_messages(
        self,
        group_id: int,
        group_name: str,
        topic_id: Optional[int],
        topic_name: str,
        messages: List[dict]
    ) -> None:
        """Append messages to storage.

        Args:
            group_id: Telegram group ID
            group_name: Group display name
            topic_id: Topic ID (None for non-forum groups)
            topic_name: Topic name ("general" for whole group)
            messages: List of MessageInfo dicts to append
        """
        if not messages:
            return

        group_dir = self._get_group_dir(group_id, group_name)
        self._ensure_dir(group_dir)

        # Get messages file path
        if topic_name == "general":
            messages_file = group_dir / "messages.md"
        else:
            safe_name = self._sanitize_name(topic_name)
            topic_dir = group_dir / safe_name
            self._ensure_dir(topic_dir)
            messages_file = topic_dir / "messages.md"

        # Group messages by date
        date_groups = group_messages_by_date(messages)

        # If file doesn't exist, create with header
        if not messages_file.exists():
            now = datetime.now(timezone.utc).isoformat()

            # Determine group type from messages or default
            group_type = "group"  # Default, could be determined from API

            header = format_group_header(
                group_name=group_name,
                group_id=group_id,
                group_type=group_type,
                topic_name=topic_name if topic_name != "general" else None,
                topic_id=topic_id,
                last_sync=now
            )
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
        self.update_channel_sync_state(
            group_id=group_id,
            group_name=group_name,
            topic_name=topic_name,
            topic_id=topic_id,
            last_message_id=last_msg["id"],
            message_count=len(messages)
        )

    def read_messages(
        self,
        group_id: int,
        topic_name: str = "general",
        last_n: Optional[int] = None
    ) -> str:
        """Read messages from storage.

        Args:
            group_id: Telegram group ID
            topic_name: Topic name
            last_n: Only return last N messages

        Returns:
            Markdown content

        Raises:
            StorageError: If no synced data found
        """
        messages_file = self.get_messages_file(group_id, topic_name)

        if not messages_file.exists():
            raise StorageError(
                f"No messages found for group {group_id}. Run sync first."
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
            messages_content = "\n".join(lines[start_idx:])
            return header + "\n" + messages_content

        return content

    def search_messages(
        self,
        group_id: int,
        topic_name: str,
        keyword: str
    ) -> List[str]:
        """Search messages for keyword.

        Args:
            group_id: Telegram group ID
            topic_name: Topic name
            keyword: Search keyword

        Returns:
            List of matching message blocks (Markdown)
        """
        try:
            content = self.read_messages(group_id, topic_name)
        except StorageError:
            return []

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

    # === Metadata ===

    def save_group_metadata(
        self,
        group_id: int,
        group_name: str,
        group_type: str,
        username: Optional[str] = None,
        member_count: int = 0,
        has_topics: bool = False
    ) -> None:
        """Save group metadata YAML file.

        Args:
            group_id: Telegram group ID
            group_name: Group display name
            group_type: Group type (group/supergroup/channel)
            username: Public @username
            member_count: Participant count
            has_topics: Whether forum topics enabled
        """
        group_dir = self._get_group_dir(group_id, group_name)
        self._ensure_dir(group_dir)

        metadata = {
            "id": group_id,
            "name": group_name,
            "type": group_type,
            "username": username,
            "member_count": member_count,
            "has_topics": has_topics,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(group_dir / "group.yaml", "w") as f:
            yaml.safe_dump(metadata, f, default_flow_style=False)

    # === Manifest ===

    def update_manifest(self) -> dict:
        """Update manifest.yaml with overview of all synced data.

        Returns:
            Generated manifest dict
        """
        self._ensure_dir(self._base_dir)
        manifest_path = self._base_dir / "manifest.yaml"

        # Scan all group directories
        groups = []
        total_messages = 0

        for group_dir in self._base_dir.iterdir():
            if not group_dir.is_dir():
                continue

            # Skip hidden directories
            if group_dir.name.startswith('.'):
                continue

            # Read sync state
            sync_state_file = group_dir / "sync_state.yaml"
            if not sync_state_file.exists():
                continue

            with open(sync_state_file, "r") as f:
                sync_state = yaml.safe_load(f) or {}

            # Read group metadata if available
            group_yaml = group_dir / "group.yaml"
            group_meta = {}
            if group_yaml.exists():
                with open(group_yaml, "r") as f:
                    group_meta = yaml.safe_load(f) or {}

            # Calculate total messages
            channels_data = sync_state.get("channels", {})
            group_message_count = sum(
                ch.get("message_count", 0) for ch in channels_data.values()
            )
            total_messages += group_message_count

            groups.append({
                "name": sync_state.get("group_name") or group_meta.get("name"),
                "id": sync_state.get("group_id") or group_meta.get("id"),
                "directory": group_dir.name,
                "type": group_meta.get("type", "group"),
                "member_count": group_meta.get("member_count", 0),
                "last_sync": sync_state.get("last_sync"),
                "total_messages": group_message_count,
            })

        # Sort groups by total messages (most active first)
        groups.sort(key=lambda g: g.get("total_messages", 0), reverse=True)

        # Build manifest
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_groups": len(groups),
                "total_messages": total_messages,
                "platform": "telegram",
            },
            "groups": groups,
        }

        # Write manifest
        with open(manifest_path, "w") as f:
            yaml.safe_dump(manifest, f, default_flow_style=False, sort_keys=False)

        return manifest

    def get_manifest(self) -> dict:
        """Get current manifest.

        Returns:
            Manifest dict, or generates new if not found
        """
        manifest_path = self._base_dir / "manifest.yaml"
        if not manifest_path.exists():
            return self.update_manifest()

        with open(manifest_path, "r") as f:
            return yaml.safe_load(f) or {}


# Global storage instance
_storage: Optional[Storage] = None


def get_storage() -> Storage:
    """Get global storage instance."""
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage

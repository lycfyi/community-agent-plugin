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

    # Default message limit for DMs (privacy-conscious)
    DM_DEFAULT_LIMIT = 100

    # Storage structure version
    # v1: Legacy - data/{group_id}/, dms/telegram/{user_id}/
    # v2: Unified - data/telegram/groups/{group_id}/, data/telegram/dms/{user_id}/
    STORAGE_VERSION = 2

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize storage.

        Args:
            base_dir: Base data directory. Uses config if not provided.
        """
        if base_dir is None:
            config = get_config()
            base_dir = config.data_dir
        self._base_dir = Path(base_dir)

        # Detect storage structure version and set paths accordingly
        self._storage_version = self._detect_storage_version()

        if self._storage_version >= 2:
            # New unified structure: data/telegram/groups/, data/telegram/dms/
            self._groups_dir = self._base_dir / "telegram" / "groups"
            self._dm_base_dir = self._base_dir / "telegram" / "dms"
        else:
            # Legacy structure: data/{group_id}/, dms/telegram/{user_id}/
            self._groups_dir = self._base_dir
            self._dm_base_dir = self._base_dir.parent / "dms" / "telegram"

    def _detect_storage_version(self) -> int:
        """Detect current storage structure version.

        Returns:
            1 = Legacy structure (data/{group_id}/, dms/telegram/)
            2 = Unified structure (data/telegram/groups/, data/telegram/dms/)
        """
        # Check for new unified structure
        new_structure = self._base_dir / "telegram" / "groups"
        if new_structure.exists():
            return 2

        # Check for legacy DM path
        legacy_dm = self._base_dir.parent / "dms" / "telegram"
        if legacy_dm.exists():
            return 1

        # Check for any group directories in legacy location
        if self._base_dir.exists():
            for item in self._base_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.') and item.name not in ("discord", "telegram"):
                    # Check if this looks like a group dir (has sync_state.yaml)
                    if (item / "sync_state.yaml").exists() or (item / "group.yaml").exists():
                        return 1

        # Fresh install - use new structure
        return 2

    def needs_migration(self) -> bool:
        """Check if migration to v2 structure is needed.

        Returns:
            True if legacy data exists that should be migrated
        """
        return self._storage_version < 2

    def migrate_to_v2(self, dry_run: bool = False) -> dict:
        """Migrate from legacy structure to unified v2 structure.

        Args:
            dry_run: If True, only report what would be migrated

        Returns:
            Migration report dict with groups_migrated, dms_migrated, errors
        """
        import shutil

        report = {
            "groups_migrated": [],
            "dms_migrated": [],
            "errors": [],
            "dry_run": dry_run,
        }

        if self._storage_version >= 2:
            return {"status": "already_migrated", **report}

        # Target directories for v2 structure
        new_groups_dir = self._base_dir / "telegram" / "groups"
        new_dm_dir = self._base_dir / "telegram" / "dms"

        # Ensure target directories exist
        if not dry_run:
            new_groups_dir.mkdir(parents=True, exist_ok=True)
            new_dm_dir.mkdir(parents=True, exist_ok=True)

        # Migrate groups from data/{group_id}/ to data/telegram/groups/{group_id}/
        legacy_groups_dir = self._base_dir
        if legacy_groups_dir.exists():
            for item in legacy_groups_dir.iterdir():
                if not item.is_dir() or item.name.startswith('.') or item.name in ("discord", "telegram"):
                    continue
                # Check if this looks like a group dir (with sync_state.yaml or group.yaml)
                if (item / "sync_state.yaml").exists() or (item / "group.yaml").exists():
                    new_path = new_groups_dir / item.name
                    report["groups_migrated"].append({
                        "old": str(item),
                        "new": str(new_path)
                    })
                    if not dry_run:
                        try:
                            shutil.move(str(item), str(new_path))
                        except Exception as e:
                            report["errors"].append(f"Failed to move group {item.name}: {e}")

        # Migrate DMs from dms/telegram/{user_id}/ to data/telegram/dms/{user_id}/
        legacy_dm_dir = self._base_dir.parent / "dms" / "telegram"
        if legacy_dm_dir.exists():
            for item in legacy_dm_dir.iterdir():
                if not item.is_dir() or item.name.startswith('.'):
                    continue
                new_path = new_dm_dir / item.name
                report["dms_migrated"].append({
                    "old": str(item),
                    "new": str(new_path)
                })
                if not dry_run:
                    try:
                        shutil.move(str(item), str(new_path))
                    except Exception as e:
                        report["errors"].append(f"Failed to move DM {item.name}: {e}")

            # Clean up legacy dms/telegram/ and dms/ if empty
            if not dry_run:
                try:
                    # Remove legacy DM manifest if present
                    legacy_manifest = legacy_dm_dir / "manifest.yaml"
                    if legacy_manifest.exists():
                        legacy_manifest.unlink()

                    # Try to remove empty directories
                    if not any(legacy_dm_dir.iterdir()):
                        legacy_dm_dir.rmdir()
                        dms_parent = legacy_dm_dir.parent
                        if not any(dms_parent.iterdir()):
                            dms_parent.rmdir()
                except Exception:
                    pass  # Non-critical cleanup failure

        # Update internal state after migration
        if not dry_run and not report["errors"]:
            self._storage_version = 2
            self._groups_dir = new_groups_dir
            self._dm_base_dir = new_dm_dir
            # Regenerate manifests at new locations
            self.update_manifest()
            self.update_dm_manifest()

        return {"status": "completed" if not dry_run else "dry_run", **report}

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
        if self._groups_dir.exists():
            for existing in self._groups_dir.glob(f"{group_id}*"):
                if existing.is_dir():
                    return existing

        # Build new directory name with slug
        if group_name:
            slug = self._slugify(group_name)
            return self._groups_dir / f"{group_id}-{slug}"

        # Fallback to just group_id
        return self._groups_dir / str(group_id)

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

        # Scan all group directories (from _groups_dir, not _base_dir)
        groups = []
        total_messages = 0

        # Ensure groups dir exists before iterating
        if not self._groups_dir.exists():
            self._ensure_dir(self._groups_dir)

        for group_dir in self._groups_dir.iterdir():
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
                "directory": f"telegram/groups/{group_dir.name}",
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

    # === DM Storage ===

    def _get_dm_dir(self, user_id: int, username: Optional[str] = None) -> Path:
        """Get DM directory path with human-readable slug.

        Format: {user_id}-{slug}
        Example: 1234567890-alice

        Args:
            user_id: Telegram user ID
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
        user_id: int,
        username: Optional[str],
        display_name: str,
    ) -> None:
        """Save DM user metadata YAML file.

        Args:
            user_id: Telegram user ID
            username: Public @username
            display_name: Display name (first + last name)
        """
        dm_dir = self._get_dm_dir(user_id, username)
        self._ensure_dir(dm_dir)

        metadata = {
            "id": user_id,
            "username": username,
            "display_name": display_name,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(dm_dir / "user.yaml", "w") as f:
            yaml.safe_dump(metadata, f, default_flow_style=False)

    def get_dm_sync_state(self, user_id: int, username: Optional[str] = None) -> dict:
        """Get sync state for a DM.

        Args:
            user_id: Telegram user ID
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

    def save_dm_sync_state(self, user_id: int, state: dict, username: Optional[str] = None) -> None:
        """Save sync state for a DM.

        Args:
            user_id: Telegram user ID
            state: Sync state dict
            username: Optional username for directory slug
        """
        dm_dir = self._get_dm_dir(user_id, username or state.get("username"))
        self._ensure_dir(dm_dir)

        state_file = dm_dir / "sync_state.yaml"
        with open(state_file, "w") as f:
            yaml.safe_dump(state, f, default_flow_style=False)

    def get_dm_last_message_id(self, user_id: int) -> Optional[int]:
        """Get last synced message ID for DM incremental sync.

        Args:
            user_id: Telegram user ID

        Returns:
            Last message ID, or None if never synced
        """
        state = self.get_dm_sync_state(user_id)
        last_id = state.get("last_message_id")
        return int(last_id) if last_id else None

    def append_dm_messages(
        self,
        user_id: int,
        username: Optional[str],
        display_name: str,
        messages: List[dict]
    ) -> None:
        """Append DM messages to storage.

        Args:
            user_id: Telegram user ID
            username: Public @username
            display_name: Display name (first + last name)
            messages: List of MessageInfo dicts to append
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
username: {username or "N/A"}
display_name: {display_name}
type: dm
platform: telegram
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
                "platform": "telegram",
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

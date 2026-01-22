"""
Member storage for Discord Bot plugin.

Self-contained storage - no dependencies on other plugins.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .config import get_config
from .member_models import MemberBasic, MemberList


class MemberStorage:
    """Storage for member data."""

    def __init__(self, data_dir: str = "."):
        """Initialize storage."""
        self._config = get_config(data_dir)

    def _ensure_dir(self, path: Path) -> Path:
        """Ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_members_dir(self, server_id: str, server_name: str) -> Path:
        """Get members directory for a server."""
        server_dir = self._config.get_server_data_dir(server_id, server_name)
        return self._ensure_dir(server_dir / "members")

    def save_member_list(
        self,
        members: list[MemberBasic],
        server_id: str,
        server_name: str,
    ) -> Path:
        """
        Save member list to storage.

        Args:
            members: List of members
            server_id: Discord server ID
            server_name: Server name

        Returns:
            Path to saved file
        """
        members_dir = self.get_members_dir(server_id, server_name)
        now = datetime.utcnow()

        # Create member list
        member_list = MemberList(
            server_id=server_id,
            server_name=server_name,
            synced_at=now,
            member_count=len(members),
            members=members,
        )

        # Save current.yaml
        current_path = members_dir / "current.yaml"
        with open(current_path, "w") as f:
            yaml.dump(member_list.to_dict(), f, default_flow_style=False, allow_unicode=True)

        # Save snapshot
        snapshots_dir = self._ensure_dir(members_dir / "snapshots")
        snapshot_name = now.strftime("%Y%m%d_%H%M%S") + ".yaml"
        snapshot_path = snapshots_dir / snapshot_name
        with open(snapshot_path, "w") as f:
            yaml.dump(member_list.to_dict(), f, default_flow_style=False, allow_unicode=True)

        # Update sync history
        self._update_sync_history(members_dir, now, len(members))

        return current_path

    def _update_sync_history(self, members_dir: Path, synced_at: datetime, count: int) -> None:
        """Update sync history file."""
        history_path = members_dir / "sync_history.yaml"

        history = []
        if history_path.exists():
            with open(history_path) as f:
                history = yaml.safe_load(f) or []

        history.append({
            "synced_at": synced_at.isoformat(),
            "member_count": count,
        })

        # Keep last 100 entries
        history = history[-100:]

        with open(history_path, "w") as f:
            yaml.dump(history, f, default_flow_style=False)

    def load_member_list(self, server_id: str, server_name: str = "server") -> Optional[MemberList]:
        """
        Load current member list from storage.

        Args:
            server_id: Discord server ID
            server_name: Server name (for directory lookup)

        Returns:
            MemberList or None if not found
        """
        members_dir = self.get_members_dir(server_id, server_name)
        current_path = members_dir / "current.yaml"

        if not current_path.exists():
            return None

        with open(current_path) as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        return MemberList.from_dict(data)


# Global storage instance
_storage: Optional[MemberStorage] = None


def get_member_storage(data_dir: str = ".") -> MemberStorage:
    """Get or create the global storage instance."""
    global _storage
    if _storage is None:
        _storage = MemberStorage(data_dir)
    return _storage

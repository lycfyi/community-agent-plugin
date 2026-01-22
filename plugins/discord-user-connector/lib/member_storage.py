"""
Member storage utilities for reading/writing member data to YAML files.

Handles directory management and file I/O for member lists, snapshots, and churned records.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .slugify import make_hybrid_name
from .member_models import (
    MemberSnapshot,
    CurrentMemberList,
    ChurnedMember,
    SyncOperation,
    ServerMetadata,
)


class MemberStorageError(Exception):
    """Raised when storage operations fail."""
    pass


class MemberStorage:
    """
    Handles all member data storage operations.

    Directory structure:
    data/discord/{server_id}_{slug}/
    ├── server.yaml                   # Server metadata
    ├── members/
    │   ├── current.yaml              # Latest member list
    │   ├── snapshots/
    │   │   └── {sync_id}.yaml        # Historical snapshots
    │   ├── churned/
    │   │   └── {user_id}_{slug}.yaml # Churned member records
    │   └── sync_history.yaml         # Sync operation history
    """

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize member storage.

        Args:
            data_dir: Base data directory (default: ./data)
        """
        self.data_dir = Path(data_dir)
        self.discord_dir = self.data_dir / "discord"

    def _get_server_dir(self, server_id: str, server_name: Optional[str] = None) -> Path:
        """
        Get server directory path, creating if needed.

        Args:
            server_id: Discord server ID
            server_name: Server display name for slug generation

        Returns:
            Path to server directory
        """
        # Look for existing directory with this server_id
        if self.discord_dir.exists():
            for entry in self.discord_dir.iterdir():
                if entry.is_dir() and entry.name.startswith(f"{server_id}_"):
                    return entry

        # Create new directory with hybrid name
        if server_name:
            dir_name = make_hybrid_name(server_id, server_name)
        else:
            dir_name = f"{server_id}_server"

        return self.discord_dir / dir_name

    def _get_members_dir(self, server_id: str, server_name: Optional[str] = None) -> Path:
        """Get members subdirectory for a server."""
        server_dir = self._get_server_dir(server_id, server_name)
        return server_dir / "members"

    def _get_snapshots_dir(self, server_id: str, server_name: Optional[str] = None) -> Path:
        """Get snapshots subdirectory for a server."""
        return self._get_members_dir(server_id, server_name) / "snapshots"

    def _get_churned_dir(self, server_id: str, server_name: Optional[str] = None) -> Path:
        """Get churned subdirectory for a server."""
        return self._get_members_dir(server_id, server_name) / "churned"

    def ensure_directories(self, server_id: str, server_name: Optional[str] = None) -> None:
        """Create all required directories for a server."""
        server_dir = self._get_server_dir(server_id, server_name)
        members_dir = self._get_members_dir(server_id, server_name)
        snapshots_dir = self._get_snapshots_dir(server_id, server_name)
        churned_dir = self._get_churned_dir(server_id, server_name)

        for dir_path in [server_dir, members_dir, snapshots_dir, churned_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # ==================== Server Metadata ====================

    def save_server_metadata(self, metadata: ServerMetadata) -> None:
        """Save server metadata to server.yaml."""
        server_dir = self._get_server_dir(metadata.server_id, metadata.name)
        server_dir.mkdir(parents=True, exist_ok=True)

        file_path = server_dir / "server.yaml"
        with open(file_path, 'w') as f:
            yaml.safe_dump(metadata.to_dict(), f, default_flow_style=False, allow_unicode=True)

    def load_server_metadata(self, server_id: str) -> Optional[ServerMetadata]:
        """Load server metadata from server.yaml."""
        server_dir = self._get_server_dir(server_id)
        file_path = server_dir / "server.yaml"

        if not file_path.exists():
            return None

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        if data:
            return ServerMetadata.from_dict(data)
        return None

    def update_server_metadata_on_sync(
        self,
        server_id: str,
        server_name: str,
        icon_url: Optional[str] = None
    ) -> ServerMetadata:
        """
        Update server metadata after a sync operation.

        Creates new metadata if none exists, updates name history if name changed.
        """
        from .slugify import slugify

        existing = self.load_server_metadata(server_id)
        now = datetime.now()

        if existing:
            # Check if name changed
            if existing.name != server_name:
                # Add to history
                existing.name_history.append({
                    "name": existing.name,
                    "slug": existing.slug,
                    "until": now.isoformat(),
                })
                existing.name = server_name
                existing.slug = slugify(server_name)

            existing.last_synced_at = now
            existing.sync_count += 1
            if icon_url:
                existing.icon_url = icon_url

            self.save_server_metadata(existing)
            return existing
        else:
            # Create new
            metadata = ServerMetadata(
                server_id=server_id,
                name=server_name,
                slug=slugify(server_name),
                icon_url=icon_url,
                first_synced_at=now,
                last_synced_at=now,
                sync_count=1,
                name_history=[{
                    "name": server_name,
                    "slug": slugify(server_name),
                    "since": now.isoformat(),
                }],
            )
            self.save_server_metadata(metadata)
            return metadata

    # ==================== Current Member List ====================

    def save_current_members(self, member_list: CurrentMemberList) -> None:
        """Save current member list to current.yaml."""
        self.ensure_directories(member_list.server_id, member_list.server_name)
        members_dir = self._get_members_dir(member_list.server_id, member_list.server_name)

        file_path = members_dir / "current.yaml"
        with open(file_path, 'w') as f:
            yaml.safe_dump(member_list.to_dict(), f, default_flow_style=False, allow_unicode=True)

    def load_current_members(self, server_id: str) -> Optional[CurrentMemberList]:
        """Load current member list from current.yaml."""
        members_dir = self._get_members_dir(server_id)
        file_path = members_dir / "current.yaml"

        if not file_path.exists():
            return None

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        if data:
            return CurrentMemberList.from_dict(data)
        return None

    # ==================== Snapshots ====================

    def save_snapshot(self, snapshot: MemberSnapshot, server_name: Optional[str] = None) -> None:
        """Save a member snapshot."""
        self.ensure_directories(snapshot.server_id, server_name)
        snapshots_dir = self._get_snapshots_dir(snapshot.server_id, server_name)

        file_path = snapshots_dir / f"{snapshot.sync_id}.yaml"
        with open(file_path, 'w') as f:
            yaml.safe_dump(snapshot.to_dict(), f, default_flow_style=False, allow_unicode=True)

    def load_snapshot(self, server_id: str, sync_id: str) -> Optional[MemberSnapshot]:
        """Load a specific snapshot by sync_id."""
        snapshots_dir = self._get_snapshots_dir(server_id)
        file_path = snapshots_dir / f"{sync_id}.yaml"

        if not file_path.exists():
            return None

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        if data:
            return MemberSnapshot.from_dict(data)
        return None

    def list_snapshots(self, server_id: str) -> list[str]:
        """List all snapshot sync_ids for a server, sorted by timestamp (newest first)."""
        snapshots_dir = self._get_snapshots_dir(server_id)

        if not snapshots_dir.exists():
            return []

        snapshots = []
        for file_path in snapshots_dir.glob("*.yaml"):
            sync_id = file_path.stem
            snapshots.append(sync_id)

        # Sort by sync_id (which is timestamp-based: YYYYMMDD_HHMMSS)
        return sorted(snapshots, reverse=True)

    def get_latest_snapshot(self, server_id: str) -> Optional[MemberSnapshot]:
        """Get the most recent snapshot for a server."""
        snapshots = self.list_snapshots(server_id)
        if not snapshots:
            return None

        return self.load_snapshot(server_id, snapshots[0])

    def get_previous_snapshot(self, server_id: str) -> Optional[MemberSnapshot]:
        """Get the second-most-recent snapshot for churn detection."""
        snapshots = self.list_snapshots(server_id)
        if len(snapshots) < 2:
            return None

        return self.load_snapshot(server_id, snapshots[1])

    # ==================== Churned Members ====================

    def save_churned_member(
        self,
        churned: ChurnedMember,
        server_id: str,
        server_name: Optional[str] = None
    ) -> None:
        """Save a churned member record."""
        self.ensure_directories(server_id, server_name)
        churned_dir = self._get_churned_dir(server_id, server_name)

        filename = make_hybrid_name(churned.user_id, churned.username) + ".yaml"
        file_path = churned_dir / filename

        with open(file_path, 'w') as f:
            yaml.safe_dump(churned.to_dict(), f, default_flow_style=False, allow_unicode=True)

    def load_churned_member(self, server_id: str, user_id: str) -> Optional[ChurnedMember]:
        """Load a churned member record by user_id."""
        churned_dir = self._get_churned_dir(server_id)

        if not churned_dir.exists():
            return None

        # Find file matching user_id
        for file_path in churned_dir.glob(f"{user_id}_*.yaml"):
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            if data:
                return ChurnedMember.from_dict(data)

        return None

    def list_churned_members(self, server_id: str) -> list[ChurnedMember]:
        """List all churned members for a server."""
        churned_dir = self._get_churned_dir(server_id)

        if not churned_dir.exists():
            return []

        churned = []
        for file_path in churned_dir.glob("*.yaml"):
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            if data:
                churned.append(ChurnedMember.from_dict(data))

        # Sort by departure date (newest first)
        return sorted(
            churned,
            key=lambda c: c.departure_detected_at or datetime.min,
            reverse=True
        )

    # ==================== Sync History ====================

    def save_sync_operation(self, operation: SyncOperation, server_name: Optional[str] = None) -> None:
        """Append a sync operation to sync_history.yaml."""
        self.ensure_directories(operation.server_id, server_name)
        members_dir = self._get_members_dir(operation.server_id, server_name)

        file_path = members_dir / "sync_history.yaml"

        # Load existing history
        history = {"syncs": []}
        if file_path.exists():
            with open(file_path, 'r') as f:
                history = yaml.safe_load(f) or {"syncs": []}

        # Append new operation
        history["syncs"].append(operation.to_dict())

        # Keep only last 100 operations
        history["syncs"] = history["syncs"][-100:]

        with open(file_path, 'w') as f:
            yaml.safe_dump(history, f, default_flow_style=False, allow_unicode=True)

    def load_sync_history(self, server_id: str) -> list[SyncOperation]:
        """Load sync history for a server."""
        members_dir = self._get_members_dir(server_id)
        file_path = members_dir / "sync_history.yaml"

        if not file_path.exists():
            return []

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        if not data or "syncs" not in data:
            return []

        return [SyncOperation.from_dict(s) for s in data["syncs"]]

    def get_last_sync(self, server_id: str) -> Optional[SyncOperation]:
        """Get the most recent sync operation."""
        history = self.load_sync_history(server_id)
        if not history:
            return None
        return history[-1]

    # ==================== Utility Methods ====================

    def generate_sync_id(self) -> str:
        """Generate a sync_id based on current timestamp."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def get_member_ids_from_current(self, server_id: str) -> set[str]:
        """Get set of all member IDs from current member list."""
        current = self.load_current_members(server_id)
        if not current:
            return set()
        return {m.user_id for m in current.members}

    def get_member_ids_from_snapshot(self, server_id: str, sync_id: str) -> set[str]:
        """Get set of all member IDs from a snapshot."""
        snapshot = self.load_snapshot(server_id, sync_id)
        if not snapshot:
            return set()
        return set(snapshot.member_ids)

    def find_server_by_name(self, name: str) -> Optional[tuple[str, str]]:
        """
        Find a server by name (fuzzy match).

        Returns:
            Tuple of (server_id, server_name) if found, None otherwise
        """
        if not self.discord_dir.exists():
            return None

        name_lower = name.lower()
        for entry in self.discord_dir.iterdir():
            if entry.is_dir():
                metadata_file = entry / "server.yaml"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        data = yaml.safe_load(f)
                    if data and data.get("name", "").lower() == name_lower:
                        return (data["server_id"], data["name"])

        return None

    def list_servers(self) -> list[dict]:
        """List all synced servers with their metadata."""
        if not self.discord_dir.exists():
            return []

        servers = []
        for entry in self.discord_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith('.'):
                metadata_file = entry / "server.yaml"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        data = yaml.safe_load(f)
                    if data:
                        servers.append(data)

        return servers


# Singleton instance
_storage: Optional[MemberStorage] = None


def get_member_storage(data_dir: str = "./data") -> MemberStorage:
    """Get or create the MemberStorage singleton."""
    global _storage
    if _storage is None:
        _storage = MemberStorage(data_dir)
    return _storage

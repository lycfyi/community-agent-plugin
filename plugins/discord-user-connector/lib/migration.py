"""
Data migration from legacy to unified structure.

Migrates Discord data from legacy connector-specific locations to a unified
structure under `data/discord/{server_id}/` with `messages/` and `members/`
subdirectories.

Legacy locations:
- User connector: data/discord/servers/{server_id}-{slug}/
- Bot connector: data/discord-bot/{server_id}_{slug}/

Unified location:
- data/discord/{server_id}/
  ├── server.yaml          # Server metadata
  ├── sync_state.yaml      # Sync tracking
  ├── .migration.yaml      # Migration tracking
  ├── messages/            # From user connector
  │   └── {channel_name}/
  │       └── messages.md
  └── members/             # From bot connector
      ├── current.yaml
      └── snapshots/
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import shutil

import yaml


class DiscordMigration:
    """Handle migration from legacy to unified data structure."""

    def __init__(self, data_root: Path):
        """
        Initialize migration handler.

        Args:
            data_root: Root data directory (typically 'data/')
        """
        self.data_root = Path(data_root)
        self.legacy_user = self.data_root / "discord" / "servers"
        self.legacy_bot = self.data_root / "discord-bot"
        self.unified = self.data_root / "discord"

    def detect_legacy_data(self) -> List[Dict[str, Any]]:
        """
        Find all servers with legacy data.

        Returns:
            List of dicts with server_id, user_path, bot_path for each server
        """
        servers: List[Dict[str, Any]] = []

        # Check user connector legacy data
        if self.legacy_user.exists():
            for server_dir in self.legacy_user.iterdir():
                if server_dir.is_dir():
                    # Parse server_id from directory name
                    # Format: {server_id}-{slug}
                    parts = server_dir.name.split("-", 1)
                    if len(parts) >= 1 and parts[0].isdigit():
                        servers.append({
                            "server_id": parts[0],
                            "user_path": server_dir,
                            "bot_path": None
                        })

        # Check bot connector legacy data
        if self.legacy_bot.exists():
            for server_dir in self.legacy_bot.iterdir():
                if server_dir.is_dir():
                    # Parse server_id from directory name
                    # Format: {server_id}_{slug}
                    parts = server_dir.name.split("_", 1)
                    if len(parts) >= 1 and parts[0].isdigit():
                        server_id = parts[0]
                        # Find or create entry
                        existing = next(
                            (s for s in servers if s["server_id"] == server_id),
                            None
                        )
                        if existing:
                            existing["bot_path"] = server_dir
                        else:
                            servers.append({
                                "server_id": server_id,
                                "user_path": None,
                                "bot_path": server_dir
                            })

        return servers

    def migrate_server(
        self,
        server: Dict[str, Any],
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Migrate a single server to unified structure.

        Args:
            server: Dict with server_id, user_path, bot_path
            dry_run: If True, don't actually move files

        Returns:
            Dict with migration result (success, messages_moved, members_moved, errors)
        """
        server_id = server["server_id"]
        target = self.unified / server_id

        result = {
            "server_id": server_id,
            "success": True,
            "messages_moved": 0,
            "members_moved": 0,
            "errors": []
        }

        if dry_run:
            return result

        # Check if already migrated
        migration_marker = target / ".migration.yaml"
        if migration_marker.exists():
            result["errors"].append("Already migrated (marker file exists)")
            return result

        # Create target structure
        target.mkdir(parents=True, exist_ok=True)
        (target / "messages").mkdir(exist_ok=True)
        (target / "members").mkdir(exist_ok=True)

        # Migrate user connector data (messages)
        if server["user_path"] and server["user_path"].exists():
            try:
                self._migrate_messages(server["user_path"], target)
                result["messages_moved"] = 1
            except Exception as e:
                result["errors"].append(f"Message migration: {e}")

        # Migrate bot connector data (members)
        if server["bot_path"] and server["bot_path"].exists():
            try:
                self._migrate_members(server["bot_path"], target)
                result["members_moved"] = 1
            except Exception as e:
                result["errors"].append(f"Member migration: {e}")

        # Write migration marker
        self._write_migration_marker(target, server)

        # Leave breadcrumb in legacy locations
        self._leave_breadcrumb(server, target)

        result["success"] = len(result["errors"]) == 0
        return result

    def _migrate_messages(self, source: Path, target: Path) -> None:
        """
        Move message files to unified location.

        Args:
            source: Legacy user connector directory
            target: Unified server directory
        """
        messages_target = target / "messages"

        for item in source.iterdir():
            if item.is_dir() and item.name not in [".", ".."]:
                # This is a channel directory
                dest = messages_target / item.name
                if not dest.exists():
                    shutil.copytree(item, dest)

        # Copy sync_state.yaml
        sync_state = source / "sync_state.yaml"
        if sync_state.exists():
            shutil.copy2(sync_state, target / "sync_state.yaml")

        # Copy server.yaml
        server_yaml = source / "server.yaml"
        if server_yaml.exists():
            shutil.copy2(server_yaml, target / "server.yaml")

    def _migrate_members(self, source: Path, target: Path) -> None:
        """
        Move member files to unified location.

        Args:
            source: Legacy bot connector directory
            target: Unified server directory
        """
        members_source = source / "members"
        members_target = target / "members"

        if members_source.exists():
            for item in members_source.iterdir():
                dest = members_target / item.name
                if item.is_file():
                    shutil.copy2(item, dest)
                elif item.is_dir():
                    if not dest.exists():
                        shutil.copytree(item, dest)

    def _write_migration_marker(
        self,
        target: Path,
        server: Dict[str, Any]
    ) -> None:
        """
        Write .migration.yaml to track migration.

        Args:
            target: Unified server directory
            server: Server info dict
        """
        marker = {
            "migrated_at": datetime.now(tz=None).isoformat(),
            "source_paths": [],
            "messages_migrated": server["user_path"] is not None,
            "members_migrated": server["bot_path"] is not None,
            "version": "1.0"
        }

        if server["user_path"]:
            marker["source_paths"].append(str(server["user_path"]))
        if server["bot_path"]:
            marker["source_paths"].append(str(server["bot_path"]))

        with open(target / ".migration.yaml", "w") as f:
            yaml.dump(marker, f, default_flow_style=False)

    def _leave_breadcrumb(
        self,
        server: Dict[str, Any],
        target: Path
    ) -> None:
        """
        Leave .migrated_to file in legacy locations.

        Args:
            server: Server info dict
            target: Unified server directory
        """
        content = f"""This data has been migrated to the unified structure.
New location: {target}
Migrated at: {datetime.now(tz=None).isoformat()}
"""

        for path in [server["user_path"], server["bot_path"]]:
            if path and path.exists():
                with open(path / ".migrated_to", "w") as f:
                    f.write(content)


def check_and_migrate(data_root: Optional[Path] = None) -> Optional[str]:
    """
    Check for legacy data and migrate if needed.

    Args:
        data_root: Root data directory (defaults to 'data')

    Returns:
        Summary message if migration occurred, None otherwise
    """
    if data_root is None:
        data_root = Path("data")

    migration = DiscordMigration(data_root)
    servers = migration.detect_legacy_data()

    if not servers:
        return None  # No migration needed

    results = []
    for server in servers:
        result = migration.migrate_server(server)
        if result["success"]:
            results.append(f"✓ Migrated server {server['server_id']}")
        else:
            errors = ", ".join(result["errors"])
            results.append(f"✗ Server {server['server_id']}: {errors}")

    return f"Migration complete:\n" + "\n".join(results)


def needs_migration(data_root: Optional[Path] = None) -> bool:
    """
    Quick check if migration is needed.

    Args:
        data_root: Root data directory (defaults to 'data')

    Returns:
        True if there is legacy data to migrate
    """
    if data_root is None:
        data_root = Path("data")

    migration = DiscordMigration(data_root)
    servers = migration.detect_legacy_data()
    return len(servers) > 0

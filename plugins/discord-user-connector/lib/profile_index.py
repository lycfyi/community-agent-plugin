"""
Profile index management for unified member profiles.

Handles fast lookups, profile CRUD operations, and index maintenance.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .slugify import make_hybrid_name
from .profile_models import UnifiedMemberProfile, ProfileIndex


class ProfileIndexError(Exception):
    """Raised when profile index operations fail."""
    pass


class ProfileManager:
    """
    Manages unified member profiles and their index.

    Directory structure:
    profiles/discord/
    ├── index.yaml                    # Profile index for fast lookup
    └── {user_id}_{slug}.yaml         # Individual profile files
    """

    def __init__(self, data_dir: str = "."):
        """
        Initialize profile manager.

        Args:
            data_dir: Base data directory (default: current directory)
        """
        self.data_dir = Path(data_dir)
        self.profiles_dir = self.data_dir / "profiles" / "discord"
        self._index: Optional[ProfileIndex] = None

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _get_index_path(self) -> Path:
        """Get path to index.yaml."""
        return self.profiles_dir / "index.yaml"

    def _get_profile_path(self, user_id: str, username: str) -> Path:
        """Get path to a profile file."""
        filename = make_hybrid_name(user_id, username) + ".yaml"
        return self.profiles_dir / filename

    # ==================== Index Operations ====================

    def load_index(self, force_reload: bool = False) -> ProfileIndex:
        """
        Load the profile index from disk.

        Args:
            force_reload: Force reload from disk even if cached

        Returns:
            ProfileIndex instance
        """
        if self._index is not None and not force_reload:
            return self._index

        index_path = self._get_index_path()

        if not index_path.exists():
            self._index = ProfileIndex()
            return self._index

        with open(index_path, 'r') as f:
            data = yaml.safe_load(f)

        if data:
            self._index = ProfileIndex.from_dict(data)
        else:
            self._index = ProfileIndex()

        return self._index

    def save_index(self) -> None:
        """Save the profile index to disk."""
        self.ensure_directories()

        if self._index is None:
            self._index = ProfileIndex()

        self._index.updated_at = datetime.now()

        index_path = self._get_index_path()
        with open(index_path, 'w') as f:
            yaml.safe_dump(self._index.to_dict(), f, default_flow_style=False, allow_unicode=True)

    def get_profile_filename(self, user_id: str) -> Optional[str]:
        """
        Get the filename for a user's profile from the index.

        Args:
            user_id: Discord user ID

        Returns:
            Filename if found, None otherwise
        """
        index = self.load_index()
        return index.get_filename(user_id)

    # ==================== Profile CRUD ====================

    def save_profile(self, profile: UnifiedMemberProfile) -> None:
        """
        Save a profile to disk and update the index.

        Args:
            profile: The profile to save
        """
        self.ensure_directories()

        # Update timestamps
        now = datetime.now()
        if profile.created_at is None:
            profile.created_at = now
        profile.updated_at = now

        # Generate filename and save
        filename = make_hybrid_name(profile.user_id, profile.username) + ".yaml"
        file_path = self.profiles_dir / filename

        with open(file_path, 'w') as f:
            yaml.safe_dump(profile.to_dict(), f, default_flow_style=False, allow_unicode=True)

        # Update index
        index = self.load_index()
        index.add_profile(profile.user_id, filename)
        self.save_index()

    def load_profile(self, user_id: str) -> Optional[UnifiedMemberProfile]:
        """
        Load a profile by user ID.

        Args:
            user_id: Discord user ID

        Returns:
            UnifiedMemberProfile if found, None otherwise
        """
        index = self.load_index()
        filename = index.get_filename(user_id)

        if not filename:
            return None

        file_path = self.profiles_dir / filename
        if not file_path.exists():
            # Index is stale, clean it up
            index.remove_profile(user_id)
            self.save_index()
            return None

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        if data:
            return UnifiedMemberProfile.from_dict(data)
        return None

    def delete_profile(self, user_id: str) -> bool:
        """
        Delete a profile.

        Args:
            user_id: Discord user ID

        Returns:
            True if deleted, False if not found
        """
        index = self.load_index()
        filename = index.get_filename(user_id)

        if not filename:
            return False

        file_path = self.profiles_dir / filename

        if file_path.exists():
            file_path.unlink()

        index.remove_profile(user_id)
        self.save_index()
        return True

    def profile_exists(self, user_id: str) -> bool:
        """Check if a profile exists for a user."""
        index = self.load_index()
        return user_id in index.index

    # ==================== Batch Operations ====================

    def list_all_profiles(self) -> list[UnifiedMemberProfile]:
        """
        Load all profiles from disk.

        Warning: This can be memory-intensive for large profile sets.

        Returns:
            List of all profiles
        """
        index = self.load_index()
        profiles = []

        for user_id, filename in index.index.items():
            file_path = self.profiles_dir / filename
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
                if data:
                    profiles.append(UnifiedMemberProfile.from_dict(data))

        return profiles

    def list_profile_ids(self) -> list[str]:
        """Get list of all user IDs with profiles."""
        index = self.load_index()
        return list(index.index.keys())

    def get_profile_count(self) -> int:
        """Get total number of profiles."""
        index = self.load_index()
        return index.profile_count

    def batch_update_profiles(
        self,
        profiles: list[UnifiedMemberProfile],
        progress_callback: Optional[callable] = None
    ) -> dict:
        """
        Update multiple profiles in batch.

        Args:
            profiles: List of profiles to update
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Dict with counts: created, updated, failed
        """
        self.ensure_directories()
        index = self.load_index()

        stats = {"created": 0, "updated": 0, "failed": 0}
        total = len(profiles)

        for i, profile in enumerate(profiles):
            try:
                is_new = profile.user_id not in index.index

                # Update timestamps
                now = datetime.now()
                if profile.created_at is None:
                    profile.created_at = now
                profile.updated_at = now

                # Generate filename and save
                filename = make_hybrid_name(profile.user_id, profile.username) + ".yaml"
                file_path = self.profiles_dir / filename

                with open(file_path, 'w') as f:
                    yaml.safe_dump(profile.to_dict(), f, default_flow_style=False, allow_unicode=True)

                # Update index
                index.add_profile(profile.user_id, filename)

                if is_new:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1

                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception:
                stats["failed"] += 1

        # Save index once at the end
        self.save_index()
        return stats

    # ==================== Search ====================

    def search_profiles_by_keyword(self, keyword: str, limit: int = 100) -> list[UnifiedMemberProfile]:
        """
        Simple keyword search across profiles.

        Searches: username, display_name, keywords, bio

        Args:
            keyword: Search term
            limit: Maximum results

        Returns:
            List of matching profiles
        """
        keyword_lower = keyword.lower()
        results = []

        index = self.load_index()
        for user_id, filename in index.index.items():
            if len(results) >= limit:
                break

            file_path = self.profiles_dir / filename
            if not file_path.exists():
                continue

            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            # Check various fields
            matches = False

            if keyword_lower in data.get("username", "").lower():
                matches = True
            elif keyword_lower in data.get("display_name", "").lower():
                matches = True
            elif any(keyword_lower in kw.lower() for kw in data.get("behavioral_data", {}).get("keywords", [])):
                matches = True
            elif keyword_lower in (data.get("discord_data", {}).get("bio") or "").lower():
                matches = True

            if matches:
                results.append(UnifiedMemberProfile.from_dict(data))

        return results

    # ==================== Index Maintenance ====================

    def rebuild_index(self) -> ProfileIndex:
        """
        Rebuild the index by scanning all profile files.

        Use this if the index becomes corrupted or out of sync.

        Returns:
            New ProfileIndex
        """
        self.ensure_directories()

        new_index = ProfileIndex()

        for file_path in self.profiles_dir.glob("*.yaml"):
            if file_path.name == "index.yaml":
                continue

            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)

            if data and "user_id" in data:
                new_index.add_profile(data["user_id"], file_path.name)

        self._index = new_index
        self.save_index()
        return new_index

    def validate_index(self) -> dict:
        """
        Validate index integrity.

        Returns:
            Dict with: valid_count, missing_files, orphan_files
        """
        index = self.load_index()

        valid_count = 0
        missing_files = []
        orphan_files = []

        # Check index entries
        for user_id, filename in index.index.items():
            file_path = self.profiles_dir / filename
            if file_path.exists():
                valid_count += 1
            else:
                missing_files.append(filename)

        # Find orphan files (files not in index)
        indexed_files = set(index.index.values())
        for file_path in self.profiles_dir.glob("*.yaml"):
            if file_path.name == "index.yaml":
                continue
            if file_path.name not in indexed_files:
                orphan_files.append(file_path.name)

        return {
            "valid_count": valid_count,
            "missing_files": missing_files,
            "orphan_files": orphan_files,
        }


# Singleton instance
_manager: Optional[ProfileManager] = None


def get_profile_manager(data_dir: str = ".") -> ProfileManager:
    """Get or create the ProfileManager singleton."""
    global _manager
    if _manager is None:
        _manager = ProfileManager(data_dir)
    return _manager

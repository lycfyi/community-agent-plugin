"""Member profile storage and retrieval.

This module provides persistent storage for community member profiles,
enabling the community agent to build understanding of members over time.

Profiles are platform-scoped (one global profile per member per platform),
stored as YAML files with a rolling limit of 50 observations per profile.

Usage:
    from lib.member_profile import ProfileStore, create_profile

    store = ProfileStore()

    # Save a new profile
    profile = create_profile("discord", "123456789", "Alice", "New member, developer")
    store.save(profile)

    # Retrieve a profile
    profile = store.get("discord", "123456789")

    # Add observation
    store.add_observation("discord", "123456789", "Interested in Python")

    # Search profiles
    results = store.search("discord", "python developer")
"""

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# === Constants ===

MAX_OBSERVATIONS = 50
MAX_KEYWORDS = 10
MAX_DISPLAY_NAME_LENGTH = 100
MAX_OBSERVATION_LENGTH = 500
MAX_NOTES_LENGTH = 2000
SUPPORTED_PLATFORMS = ("discord", "telegram")
INDEX_VERSION = 1


# === Data Classes ===


@dataclass
class Observation:
    """A timestamped piece of information about a member."""

    timestamp: datetime
    text: str  # Max 500 chars

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Observation":
        """Create from dictionary."""
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(timestamp=timestamp, text=data["text"])


@dataclass
class MemberProfile:
    """A community member's profile."""

    member_id: str
    platform: str  # "discord" or "telegram"
    display_name: str  # Max 100 chars
    first_seen: datetime
    last_updated: datetime
    observations: List[Observation] = field(default_factory=list)  # Max 50
    notes: str = ""  # Max 2000 chars
    keywords: List[str] = field(default_factory=list)  # Max 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "member_id": self.member_id,
            "platform": self.platform,
            "display_name": self.display_name,
            "first_seen": self.first_seen.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "observations": [obs.to_dict() for obs in self.observations],
            "notes": self.notes,
            "keywords": self.keywords,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemberProfile":
        """Create from dictionary."""
        first_seen = data["first_seen"]
        if isinstance(first_seen, str):
            first_seen = datetime.fromisoformat(first_seen)

        last_updated = data["last_updated"]
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)

        observations = [
            Observation.from_dict(obs) for obs in data.get("observations", [])
        ]

        return cls(
            member_id=data["member_id"],
            platform=data["platform"],
            display_name=data["display_name"],
            first_seen=first_seen,
            last_updated=last_updated,
            observations=observations,
            notes=data.get("notes", ""),
            keywords=data.get("keywords", []),
        )


@dataclass
class ProfileSummary:
    """Lightweight summary for index."""

    member_id: str
    display_name: str
    first_seen: str  # ISO date (YYYY-MM-DD)
    last_updated: str  # ISO date (YYYY-MM-DD)
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "display_name": self.display_name,
            "first_seen": self.first_seen,
            "last_updated": self.last_updated,
            "keywords": self.keywords,
        }

    @classmethod
    def from_dict(cls, member_id: str, data: Dict[str, Any]) -> "ProfileSummary":
        """Create from dictionary."""
        return cls(
            member_id=member_id,
            display_name=data["display_name"],
            first_seen=data["first_seen"],
            last_updated=data["last_updated"],
            keywords=data.get("keywords", []),
        )


@dataclass
class SearchResult:
    """Result from a profile search."""

    profile: MemberProfile
    match_reason: str  # Why this profile matched


# === Validation ===


def validate_profile(profile: MemberProfile) -> None:
    """Validate profile against rules VR-001 through VR-007.

    Raises:
        ValueError: If validation fails
    """
    # VR-001: member_id must be non-empty
    if not profile.member_id or not profile.member_id.strip():
        raise ValueError("member_id must be non-empty (VR-001)")

    # VR-002: platform must be supported
    if profile.platform not in SUPPORTED_PLATFORMS:
        raise ValueError(
            f"platform must be one of {SUPPORTED_PLATFORMS}, got '{profile.platform}' (VR-002)"
        )

    # VR-003: display_name must be non-empty and max 100 chars
    if not profile.display_name or not profile.display_name.strip():
        raise ValueError("display_name must be non-empty (VR-003)")
    if len(profile.display_name) > MAX_DISPLAY_NAME_LENGTH:
        raise ValueError(
            f"display_name must be max {MAX_DISPLAY_NAME_LENGTH} chars (VR-003)"
        )

    # VR-004: observations max 50 items
    if len(profile.observations) > MAX_OBSERVATIONS:
        raise ValueError(
            f"observations must have max {MAX_OBSERVATIONS} items (VR-004)"
        )

    # VR-005: each observation.text must be non-empty and max 500 chars
    for i, obs in enumerate(profile.observations):
        if not obs.text or not obs.text.strip():
            raise ValueError(f"observation[{i}].text must be non-empty (VR-005)")
        if len(obs.text) > MAX_OBSERVATION_LENGTH:
            raise ValueError(
                f"observation[{i}].text must be max {MAX_OBSERVATION_LENGTH} chars (VR-005)"
            )

    # VR-006: keywords max 10 items
    if len(profile.keywords) > MAX_KEYWORDS:
        raise ValueError(f"keywords must have max {MAX_KEYWORDS} items (VR-006)")

    # VR-007: notes max 2000 chars
    if len(profile.notes) > MAX_NOTES_LENGTH:
        raise ValueError(f"notes must be max {MAX_NOTES_LENGTH} chars (VR-007)")


# === Factory Function ===


def create_profile(
    platform: str,
    member_id: str,
    display_name: str,
    initial_observation: Optional[str] = None,
) -> MemberProfile:
    """Factory function to create a new MemberProfile.

    Args:
        platform: Platform identifier ("discord" or "telegram")
        member_id: The member's platform-specific ID
        display_name: Display name
        initial_observation: Optional first observation

    Returns:
        New MemberProfile instance
    """
    now = datetime.now()
    observations = []
    if initial_observation:
        observations.append(Observation(timestamp=now, text=initial_observation))

    return MemberProfile(
        member_id=member_id,
        platform=platform,
        display_name=display_name,
        first_seen=now,
        last_updated=now,
        observations=observations,
    )


# === ProfileStore Implementation ===


class ProfileStore:
    """Storage system for member profiles.

    Stores profiles as YAML files with an index for fast lookup.

    Usage:
        store = ProfileStore(base_dir=Path("./profiles"))

        # Save or update a profile
        store.save(profile)

        # Retrieve by ID
        profile = store.get("discord", "123456789")

        # Search by keywords
        results = store.search("discord", "python developer")

        # List all profiles
        summaries = store.list_all("discord")
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """Initialize the profile store.

        Args:
            base_dir: Base directory for profile storage.
                      Defaults to ./profiles in current working directory or CLAUDE_LOCAL_DIR.
        """
        if base_dir is None:
            local_dir = os.getenv("CLAUDE_LOCAL_DIR")
            root = Path(local_dir) if local_dir else Path.cwd()
            base_dir = root / "profiles"

        self.base_dir = Path(base_dir)
        self._index_cache: Dict[str, Dict[str, ProfileSummary]] = {}

    def _ensure_platform_dir(self, platform: str) -> Path:
        """Create platform directory if it doesn't exist.

        Args:
            platform: Platform identifier

        Returns:
            Path to platform directory
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")

        platform_dir = self.base_dir / platform
        platform_dir.mkdir(parents=True, exist_ok=True)
        return platform_dir

    def _get_profile_path(self, platform: str, member_id: str) -> Path:
        """Get path to profile file.

        Args:
            platform: Platform identifier
            member_id: Member ID

        Returns:
            Path to profile YAML file
        """
        platform_dir = self._ensure_platform_dir(platform)
        return platform_dir / f"{member_id}.yaml"

    def _get_index_path(self, platform: str) -> Path:
        """Get path to index file.

        Args:
            platform: Platform identifier

        Returns:
            Path to index YAML file
        """
        platform_dir = self._ensure_platform_dir(platform)
        return platform_dir / "index.yaml"

    def _load_index(self, platform: str) -> Dict[str, ProfileSummary]:
        """Load index from file or cache.

        Args:
            platform: Platform identifier

        Returns:
            Dictionary mapping member_id to ProfileSummary
        """
        # Check cache first
        if platform in self._index_cache:
            return self._index_cache[platform]

        index_path = self._get_index_path(platform)

        if not index_path.exists():
            self._index_cache[platform] = {}
            return {}

        with open(index_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        members = data.get("members", {})
        index = {
            member_id: ProfileSummary.from_dict(member_id, summary)
            for member_id, summary in members.items()
        }

        self._index_cache[platform] = index
        return index

    def _save_index(self, platform: str, index: Dict[str, ProfileSummary]) -> None:
        """Save index to file with atomic write.

        Args:
            platform: Platform identifier
            index: Index to save
        """
        index_path = self._get_index_path(platform)

        data = {
            "version": INDEX_VERSION,
            "updated_at": datetime.now().isoformat(),
            "count": len(index),
            "members": {
                member_id: summary.to_dict() for member_id, summary in index.items()
            },
        }

        # Atomic write: write to temp file then rename
        platform_dir = self._ensure_platform_dir(platform)
        fd, temp_path = tempfile.mkstemp(dir=platform_dir, suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
            os.replace(temp_path, index_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        # Update cache
        self._index_cache[platform] = index

    def _trim_observations(self, profile: MemberProfile) -> None:
        """Trim observations to max limit (removes oldest).

        Args:
            profile: Profile to trim (modified in place)
        """
        if len(profile.observations) > MAX_OBSERVATIONS:
            # Sort by timestamp descending, keep newest
            profile.observations.sort(key=lambda o: o.timestamp, reverse=True)
            profile.observations = profile.observations[:MAX_OBSERVATIONS]

    def _extract_keywords(self, profile: MemberProfile) -> List[str]:
        """Extract keywords from profile for indexing.

        Args:
            profile: Profile to extract from

        Returns:
            List of keywords (max 10)
        """
        # Use existing keywords if set
        if profile.keywords:
            return profile.keywords[:MAX_KEYWORDS]

        # Otherwise extract from observations and notes
        words: Dict[str, int] = {}
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "dare",
            "ought",
            "used",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "and",
            "but",
            "or",
            "nor",
            "so",
            "yet",
            "both",
            "either",
            "neither",
            "not",
            "only",
            "own",
            "same",
            "than",
            "too",
            "very",
            "just",
            "i",
            "me",
            "my",
            "myself",
            "we",
            "our",
            "ours",
            "ourselves",
            "you",
            "your",
            "yours",
            "yourself",
            "yourselves",
            "he",
            "him",
            "his",
            "himself",
            "she",
            "her",
            "hers",
            "herself",
            "it",
            "its",
            "itself",
            "they",
            "them",
            "their",
            "theirs",
            "themselves",
            "what",
            "which",
            "who",
            "whom",
            "this",
            "that",
            "these",
            "those",
            "am",
        }

        # Collect text from observations and notes
        texts = [obs.text for obs in profile.observations]
        if profile.notes:
            texts.append(profile.notes)

        for text in texts:
            # Simple tokenization
            for word in text.lower().split():
                # Clean word
                word = "".join(c for c in word if c.isalnum())
                if word and len(word) > 2 and word not in stopwords:
                    words[word] = words.get(word, 0) + 1

        # Sort by frequency and return top keywords
        sorted_words = sorted(words.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:MAX_KEYWORDS]]

    # === Core Operations (FR-001, FR-002) ===

    def save(self, profile: MemberProfile) -> None:
        """Save or update a member profile.

        Creates a new profile if one doesn't exist for the member_id,
        or updates the existing profile. Automatically:
        - Updates last_updated timestamp
        - Trims observations to max 50 (removes oldest)
        - Updates the platform index

        Args:
            profile: The profile to save

        Raises:
            ValueError: If profile fails validation
            IOError: If write fails
        """
        # Validate
        validate_profile(profile)

        # Trim observations
        self._trim_observations(profile)

        # Update timestamp
        profile.last_updated = datetime.now()

        # Extract keywords if not set
        if not profile.keywords:
            profile.keywords = self._extract_keywords(profile)

        # Write profile file
        profile_path = self._get_profile_path(profile.platform, profile.member_id)
        platform_dir = self._ensure_platform_dir(profile.platform)

        # Atomic write
        fd, temp_path = tempfile.mkstemp(dir=platform_dir, suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    profile.to_dict(), f, default_flow_style=False, allow_unicode=True
                )
            os.replace(temp_path, profile_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        # Update index
        index = self._load_index(profile.platform)
        index[profile.member_id] = ProfileSummary(
            member_id=profile.member_id,
            display_name=profile.display_name,
            first_seen=profile.first_seen.strftime("%Y-%m-%d"),
            last_updated=profile.last_updated.strftime("%Y-%m-%d"),
            keywords=profile.keywords[:MAX_KEYWORDS],
        )
        self._save_index(profile.platform, index)

    def get(self, platform: str, member_id: str) -> Optional[MemberProfile]:
        """Retrieve a member's profile by ID.

        Args:
            platform: Platform identifier ("discord" or "telegram")
            member_id: The member's platform-specific ID

        Returns:
            MemberProfile if found, None if not exists
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")

        profile_path = self._get_profile_path(platform, member_id)

        if not profile_path.exists():
            return None

        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return MemberProfile.from_dict(data)

    def exists(self, platform: str, member_id: str) -> bool:
        """Check if a profile exists without loading it.

        Uses index for O(1) lookup.

        Args:
            platform: Platform identifier
            member_id: The member's ID

        Returns:
            True if profile exists
        """
        index = self._load_index(platform)
        return member_id in index

    # === Search Operations (FR-003) ===

    def search(
        self, platform: str, query: str, limit: int = 20
    ) -> List[SearchResult]:
        """Search profiles by keyword or attribute.

        Searches across:
        - display_name
        - keywords
        - observations (if query not found in index)
        - notes

        Args:
            platform: Platform identifier
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching profiles with match reasons
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")

        query_lower = query.lower()
        query_terms = set(query_lower.split())
        results: List[SearchResult] = []

        # First pass: search index (fast)
        index = self._load_index(platform)
        matched_ids = set()

        for member_id, summary in index.items():
            match_reasons = []

            # Check display name
            if query_lower in summary.display_name.lower():
                match_reasons.append(f"name contains '{query}'")

            # Check keywords
            matching_keywords = [
                kw for kw in summary.keywords if any(term in kw for term in query_terms)
            ]
            if matching_keywords:
                match_reasons.append(f"keywords: {', '.join(matching_keywords)}")

            if match_reasons:
                profile = self.get(platform, member_id)
                if profile:
                    results.append(
                        SearchResult(profile=profile, match_reason="; ".join(match_reasons))
                    )
                    matched_ids.add(member_id)

            if len(results) >= limit:
                break

        # Second pass: deep search observations/notes if needed
        if len(results) < limit:
            for member_id in index.keys():
                if member_id in matched_ids:
                    continue

                profile = self.get(platform, member_id)
                if not profile:
                    continue

                match_reasons = []

                # Check observations
                for obs in profile.observations:
                    if query_lower in obs.text.lower():
                        match_reasons.append(f"observation mentions '{query}'")
                        break

                # Check notes
                if profile.notes and query_lower in profile.notes.lower():
                    match_reasons.append(f"notes contain '{query}'")

                if match_reasons:
                    results.append(
                        SearchResult(profile=profile, match_reason="; ".join(match_reasons))
                    )

                if len(results) >= limit:
                    break

        return results

    # === List Operations (FR-004) ===

    def list_all(
        self, platform: str, offset: int = 0, limit: int = 50
    ) -> List[ProfileSummary]:
        """List all profiles with pagination.

        Args:
            platform: Platform identifier
            offset: Number of profiles to skip
            limit: Maximum profiles to return

        Returns:
            List of profile summaries (from index)
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")

        index = self._load_index(platform)

        # Sort by last_updated descending
        summaries = sorted(
            index.values(), key=lambda s: s.last_updated, reverse=True
        )

        return summaries[offset : offset + limit]

    def count(self, platform: str) -> int:
        """Get total number of profiles for a platform.

        Args:
            platform: Platform identifier

        Returns:
            Profile count
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")

        index = self._load_index(platform)
        return len(index)

    # === Observation Management (FR-007) ===

    def add_observation(
        self, platform: str, member_id: str, text: str, display_name: Optional[str] = None
    ) -> MemberProfile:
        """Add an observation to a member's profile.

        Creates the profile if it doesn't exist.
        Automatically trims to 50 observations.

        Args:
            platform: Platform identifier
            member_id: The member's ID
            text: Observation text (max 500 chars)
            display_name: Display name (required if creating new profile)

        Returns:
            Updated profile

        Raises:
            ValueError: If text exceeds 500 chars or display_name missing for new profile
        """
        if len(text) > MAX_OBSERVATION_LENGTH:
            raise ValueError(
                f"Observation text must be max {MAX_OBSERVATION_LENGTH} chars"
            )

        # Get existing or create new profile
        profile = self.get(platform, member_id)

        if profile is None:
            if not display_name:
                raise ValueError("display_name required when creating new profile")
            profile = create_profile(platform, member_id, display_name)

        # Add observation
        profile.observations.append(
            Observation(timestamp=datetime.now(), text=text)
        )

        # Save (handles trimming and index update)
        self.save(profile)

        return profile

    # === Index Operations (FR-010) ===

    def rebuild_index(self, platform: str) -> int:
        """Rebuild the platform index from profile files.

        Use if index becomes corrupted or out of sync.

        Args:
            platform: Platform identifier

        Returns:
            Number of profiles indexed
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")

        platform_dir = self._ensure_platform_dir(platform)
        index: Dict[str, ProfileSummary] = {}

        # Scan all YAML files (except index.yaml)
        for profile_path in platform_dir.glob("*.yaml"):
            if profile_path.name == "index.yaml":
                continue

            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                profile = MemberProfile.from_dict(data)
                index[profile.member_id] = ProfileSummary(
                    member_id=profile.member_id,
                    display_name=profile.display_name,
                    first_seen=profile.first_seen.strftime("%Y-%m-%d"),
                    last_updated=profile.last_updated.strftime("%Y-%m-%d"),
                    keywords=profile.keywords[:MAX_KEYWORDS],
                )
            except Exception as e:
                # Log but continue rebuilding
                print(f"Warning: Failed to index {profile_path}: {e}")

        self._save_index(platform, index)
        return len(index)

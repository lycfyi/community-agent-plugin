"""User profile loader and parser.

Reads config/PROFILE.md to get user preferences for server/group prioritization.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


PROFILE_TEMPLATE = """# User Profile

Configure your preferences for community message sync and analysis.

## Interests

List topics you're interested in (one per line, with `-` prefix):

- technology
- programming
- gaming

## Preferred Servers

Discord servers to prioritize (one per line, with `-` prefix):

- My Favorite Server
- Another Server

## Preferred Groups

Telegram groups to prioritize (one per line, with `-` prefix):

- My Telegram Group

## Summary Preferences

How should Claude summarize conversations?

- Length: brief
- Format: bullet

---

*Edit this file to customize your preferences.*
*These settings help prioritize which servers/groups to sync first.*
"""


@dataclass
class UserProfile:
    """Parsed user profile preferences."""

    interests: list[str] = field(default_factory=list)
    preferred_servers: list[str] = field(default_factory=list)
    preferred_groups: list[str] = field(default_factory=list)
    summary_length: str = "brief"  # brief | detailed
    summary_format: str = "bullet"  # bullet | prose

    def matches_interest(self, text: str) -> bool:
        """Check if text matches any user interest."""
        text_lower = text.lower()
        return any(
            interest.lower() in text_lower
            for interest in self.interests
        )

    def server_priority(self, server_name: str) -> int:
        """Get priority score for a server (lower = higher priority).

        Returns:
            0 if in preferred list, 100 otherwise
        """
        server_lower = server_name.lower()
        for i, preferred in enumerate(self.preferred_servers):
            if preferred.lower() in server_lower or server_lower in preferred.lower():
                return i  # Return index as priority
        return 100  # Not in preferred list

    def group_priority(self, group_name: str) -> int:
        """Get priority score for a group (lower = higher priority).

        Returns:
            0 if in preferred list, 100 otherwise
        """
        group_lower = group_name.lower()
        for i, preferred in enumerate(self.preferred_groups):
            if preferred.lower() in group_lower or group_lower in preferred.lower():
                return i  # Return index as priority
        return 100  # Not in preferred list


def parse_list_section(content: str, section_name: str) -> list[str]:
    """Parse a markdown list section.

    Args:
        content: Full markdown content
        section_name: Name of section to find (e.g., "Interests")

    Returns:
        List of items found in that section
    """
    items = []

    # Find the section
    pattern = rf"##\s+{re.escape(section_name)}\s*\n(.*?)(?=\n##|\n---|\Z)"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

    if match:
        section_content = match.group(1)
        # Find all list items
        for line in section_content.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                item = line[2:].strip()
                if item and not item.startswith("#"):  # Skip comments
                    items.append(item)

    return items


def parse_preference(content: str, key: str, default: str = "") -> str:
    """Parse a key: value preference line.

    Args:
        content: Full markdown content
        key: Key to find (e.g., "Length")
        default: Default value if not found

    Returns:
        Value found or default
    """
    pattern = rf"-\s+{re.escape(key)}:\s*(\w+)"
    match = re.search(pattern, content, re.IGNORECASE)
    return match.group(1) if match else default


def load_profile(config_dir: Optional[Path] = None) -> UserProfile:
    """Load user profile from config/PROFILE.md.

    Args:
        config_dir: Config directory path (default: auto-detect from CLAUDE_LOCAL_DIR or cwd)

    Returns:
        Parsed UserProfile dataclass
    """
    if config_dir is None:
        local_dir = os.getenv("CLAUDE_LOCAL_DIR")
        base_dir = Path(local_dir) if local_dir else Path.cwd()
        config_dir = base_dir / "config"

    profile_path = config_dir / "PROFILE.md"

    if not profile_path.exists():
        # Return default profile if file doesn't exist
        return UserProfile()

    content = profile_path.read_text()

    return UserProfile(
        interests=parse_list_section(content, "Interests"),
        preferred_servers=parse_list_section(content, "Preferred Servers"),
        preferred_groups=parse_list_section(content, "Preferred Groups"),
        summary_length=parse_preference(content, "Length", "brief"),
        summary_format=parse_preference(content, "Format", "bullet"),
    )


def ensure_profile(config_dir: Optional[Path] = None) -> Path:
    """Ensure PROFILE.md exists, creating from template if needed.

    Args:
        config_dir: Config directory path (default: auto-detect)

    Returns:
        Path to the profile file
    """
    if config_dir is None:
        local_dir = os.getenv("CLAUDE_LOCAL_DIR")
        base_dir = Path(local_dir) if local_dir else Path.cwd()
        config_dir = base_dir / "config"

    profile_path = config_dir / "PROFILE.md"

    if not profile_path.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(PROFILE_TEMPLATE)
        print(f"Created profile template at {profile_path}")

    return profile_path


# Module-level convenience function
def get_profile() -> UserProfile:
    """Get user profile (convenience function)."""
    return load_profile()

"""User profile manager for Discord agent.

Manages a profile.md file with YAML frontmatter containing user preferences,
interests, engagement patterns, and activity history.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ProfileData:
    """Structured profile data."""

    # Identity
    name: str = ""
    role: str = ""

    # Interests and keywords
    interests: list[str] = field(default_factory=list)
    watch_keywords: list[str] = field(default_factory=list)

    # Communication preferences
    summary_style: str = "actionable"  # brief, detailed, actionable
    detail_level: str = "concise"  # concise, detailed, comprehensive
    timezone: str = "UTC"

    # Engagement patterns
    engagement: dict[str, dict[str, int]] = field(default_factory=dict)
    # Structure: {"server_name": {"channel_name": score}}

    frequent_topics: list[str] = field(default_factory=list)

    # Activity history (last 30 entries)
    activity: list[dict] = field(default_factory=list)

    # Learned preferences
    learned: list[str] = field(default_factory=list)

    # Metadata
    last_updated: str = ""
    version: int = 1


class ProfileManager:
    """Manages user profile stored in profile.md."""

    DEFAULT_PROFILE_PATH = Path("config/profile.md")
    MAX_ACTIVITY_ENTRIES = 30
    MAX_INTERESTS = 50
    MAX_FREQUENT_TOPICS = 20

    def __init__(self, profile_path: Optional[Path] = None):
        """Initialize profile manager.

        Args:
            profile_path: Path to profile.md. Defaults to config/profile.md
        """
        self._path = profile_path or (Path.cwd() / self.DEFAULT_PROFILE_PATH)
        self._data: Optional[ProfileData] = None

    @property
    def path(self) -> Path:
        """Get profile file path."""
        return self._path

    def exists(self) -> bool:
        """Check if profile file exists."""
        return self._path.exists()

    def load(self) -> ProfileData:
        """Load profile from file.

        Returns:
            ProfileData with loaded values, or defaults if file doesn't exist
        """
        if self._data is not None:
            return self._data

        if not self._path.exists():
            self._data = ProfileData()
            return self._data

        content = self._path.read_text()
        self._data = self._parse_profile(content)
        return self._data

    def save(self) -> None:
        """Save profile to file."""
        if self._data is None:
            self._data = ProfileData()

        self._data.last_updated = datetime.now(timezone.utc).isoformat()

        content = self._render_profile(self._data)

        # Ensure directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(content)

    def create_default(self) -> None:
        """Create a new profile with default values."""
        self._data = ProfileData(
            last_updated=datetime.now(timezone.utc).isoformat()
        )
        self.save()

    # === Read methods ===

    def get_interests(self) -> list[str]:
        """Get user interests."""
        return self.load().interests.copy()

    def get_watch_keywords(self) -> list[str]:
        """Get watch keywords."""
        return self.load().watch_keywords.copy()

    def get_preferences(self) -> dict:
        """Get communication preferences."""
        data = self.load()
        return {
            "summary_style": data.summary_style,
            "detail_level": data.detail_level,
            "timezone": data.timezone
        }

    def get_engagement_scores(self) -> dict[str, int]:
        """Get flattened engagement scores.

        Returns:
            Dict mapping "server/channel" to score
        """
        data = self.load()
        scores = {}
        for server, channels in data.engagement.items():
            for channel, score in channels.items():
                scores[f"{server}/{channel}"] = score
        return scores

    def get_top_servers(self, limit: int = 5) -> list[tuple[str, int]]:
        """Get top servers by engagement.

        Returns:
            List of (server_name, total_score) tuples
        """
        data = self.load()
        server_scores = {}
        for server, channels in data.engagement.items():
            server_scores[server] = sum(channels.values())

        sorted_servers = sorted(
            server_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_servers[:limit]

    def get_activity(self, limit: int = 10) -> list[dict]:
        """Get recent activity entries."""
        return self.load().activity[:limit]

    # === Write methods ===

    def add_interest(self, topic: str, score: int = 1) -> None:
        """Add or boost an interest topic.

        Args:
            topic: Interest topic to add
            score: Score to add (for future weighted interests)
        """
        data = self.load()
        topic = topic.strip().lower()

        if not topic:
            return

        if topic not in data.interests:
            data.interests.append(topic)
            # Keep within limit, remove oldest
            if len(data.interests) > self.MAX_INTERESTS:
                data.interests = data.interests[-self.MAX_INTERESTS:]

        self.save()

    def add_watch_keyword(self, keyword: str) -> None:
        """Add a watch keyword."""
        data = self.load()
        keyword = keyword.strip().lower()

        if keyword and keyword not in data.watch_keywords:
            data.watch_keywords.append(keyword)

        self.save()

    def add_activity(self, action: str, context: str) -> None:
        """Log an activity entry.

        Args:
            action: Action type (e.g., "summary", "sync", "read")
            context: Context description (e.g., "Claude Developers, last 7 days")
        """
        data = self.load()

        entry = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "action": action,
            "context": context
        }

        data.activity.insert(0, entry)

        # Keep within limit
        if len(data.activity) > self.MAX_ACTIVITY_ENTRIES:
            data.activity = data.activity[:self.MAX_ACTIVITY_ENTRIES]

        self.save()

    def update_engagement(self, server: str, channel: str, delta: int = 1) -> None:
        """Update engagement score for a server/channel.

        Args:
            server: Server name
            channel: Channel name
            delta: Score change (positive or negative)
        """
        data = self.load()

        if server not in data.engagement:
            data.engagement[server] = {}

        current = data.engagement[server].get(channel, 0)
        data.engagement[server][channel] = max(0, current + delta)

        self.save()

    def update_preference(self, key: str, value: str) -> None:
        """Update a communication preference.

        Args:
            key: Preference key (summary_style, detail_level, timezone)
            value: New value
        """
        data = self.load()

        if key == "summary_style":
            data.summary_style = value
        elif key == "detail_level":
            data.detail_level = value
        elif key == "timezone":
            data.timezone = value

        self.save()

    def add_learned_preference(self, preference: str) -> None:
        """Add a learned preference observation."""
        data = self.load()

        if preference not in data.learned:
            data.learned.append(preference)
            # Keep reasonable limit
            if len(data.learned) > 10:
                data.learned = data.learned[-10:]

        self.save()

    def add_frequent_topic(self, topic: str) -> None:
        """Add a frequently asked topic."""
        data = self.load()
        topic = topic.strip()

        if topic and topic not in data.frequent_topics:
            data.frequent_topics.append(topic)
            if len(data.frequent_topics) > self.MAX_FREQUENT_TOPICS:
                data.frequent_topics = data.frequent_topics[-self.MAX_FREQUENT_TOPICS:]

        self.save()

    # === Learning methods ===

    def learn_from_summary(
        self,
        servers: list[str],
        channels: list[str],
        topics: list[str]
    ) -> None:
        """Update profile based on a summary request.

        Args:
            servers: Servers that were summarized
            channels: Channels that were summarized
            topics: Key topics extracted from the summary
        """
        data = self.load()

        # Update engagement for each server/channel
        for server in servers:
            for channel in channels:
                self.update_engagement(server, channel, delta=5)

        # Add topics as interests
        for topic in topics[:5]:  # Limit to top 5 topics
            self.add_interest(topic)

        # Log activity
        servers_str = ", ".join(servers[:2])
        if len(servers) > 2:
            servers_str += f" +{len(servers) - 2} more"
        self.add_activity("summary", servers_str)

    def learn_from_query(self, query: str) -> None:
        """Extract and learn from user query.

        Args:
            query: User's natural language query
        """
        # Simple topic extraction - could be enhanced with NLP
        query_lower = query.lower()

        # Extract potential topics (words > 3 chars, not common words)
        common_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
            'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has',
            'what', 'when', 'where', 'which', 'how', 'from', 'this',
            'that', 'with', 'have', 'been', 'will', 'would', 'could',
            'should', 'about', 'there', 'their', 'some', 'them',
            'discord', 'messages', 'channel', 'server', 'summarize',
            'summary', 'show', 'help', 'please', 'want', 'need'
        }

        words = re.findall(r'\b[a-z]{4,}\b', query_lower)
        potential_topics = [w for w in words if w not in common_words]

        # Add unique topics
        for topic in potential_topics[:3]:
            self.add_frequent_topic(topic)

    def reset(self) -> None:
        """Reset profile to defaults."""
        self._data = ProfileData(
            last_updated=datetime.now(timezone.utc).isoformat()
        )
        self.save()

    # === Private methods ===

    def _parse_profile(self, content: str) -> ProfileData:
        """Parse profile.md content into ProfileData."""
        data = ProfileData()

        # Extract YAML frontmatter
        frontmatter_match = re.match(
            r'^---\s*\n(.*?)\n---\s*\n',
            content,
            re.DOTALL
        )

        if frontmatter_match:
            try:
                meta = yaml.safe_load(frontmatter_match.group(1)) or {}
                data.last_updated = meta.get("last_updated", "")
                data.version = meta.get("version", 1)
            except yaml.YAMLError:
                pass

        # Parse markdown sections
        sections = self._extract_sections(content)

        # Identity
        if "Identity" in sections:
            identity = self._parse_key_values(sections["Identity"])
            data.name = identity.get("Name", "")
            data.role = identity.get("Role", "")

        # Interests
        if "Interests" in sections:
            data.interests = self._parse_list(sections["Interests"])

        # Watch Keywords
        if "Watch Keywords" in sections:
            data.watch_keywords = self._parse_list(sections["Watch Keywords"])

        # Communication Preferences
        if "Communication Preferences" in sections:
            prefs = self._parse_key_values(sections["Communication Preferences"])
            data.summary_style = prefs.get("Summary style", "actionable")
            data.detail_level = prefs.get("Detail level", "concise")
            data.timezone = prefs.get("Timezone", "UTC")

        # Engagement Patterns
        if "Engagement Patterns" in sections:
            data.engagement = self._parse_engagement_table(
                sections["Engagement Patterns"]
            )
            data.frequent_topics = self._parse_subsection_list(
                sections["Engagement Patterns"],
                "Topics you ask about frequently"
            )

        # Activity History
        if "Activity History" in sections:
            data.activity = self._parse_activity_table(
                sections["Activity History"]
            )

        # Learned Preferences
        if "Learned Preferences" in sections:
            data.learned = self._parse_list(sections["Learned Preferences"])

        return data

    def _extract_sections(self, content: str) -> dict[str, str]:
        """Extract markdown sections by ## headers."""
        sections = {}
        current_section = None
        current_content = []

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(current_content)
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content)

        return sections

    def _parse_key_values(self, content: str) -> dict[str, str]:
        """Parse key-value pairs from markdown list."""
        result = {}
        for line in content.split("\n"):
            match = re.match(r'^-\s*\*\*(.+?)\*\*:\s*(.*)$', line)
            if match:
                result[match.group(1)] = match.group(2).strip()
        return result

    def _parse_list(self, content: str) -> list[str]:
        """Parse simple markdown list."""
        items = []
        for line in content.split("\n"):
            match = re.match(r'^-\s+(.+)$', line)
            if match:
                item = match.group(1).strip()
                # Skip items that are key-value pairs
                if not item.startswith("**"):
                    items.append(item)
        return items

    def _parse_subsection_list(self, content: str, header: str) -> list[str]:
        """Parse list items under a specific text header."""
        items = []
        in_section = False

        for line in content.split("\n"):
            if header in line:
                in_section = True
                continue
            if in_section:
                if line.startswith("## ") or line.startswith("| "):
                    break
                match = re.match(r'^-\s+(.+)$', line)
                if match:
                    items.append(match.group(1).strip())

        return items

    def _parse_engagement_table(self, content: str) -> dict[str, dict[str, int]]:
        """Parse engagement table into nested dict."""
        engagement = {}

        for line in content.split("\n"):
            # Skip header and separator rows
            if not line.startswith("|") or "---" in line or "Server" in line:
                continue

            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                server = parts[0]
                channel = parts[1].lstrip("#")
                try:
                    score = int(parts[2])
                except ValueError:
                    continue

                if server not in engagement:
                    engagement[server] = {}
                engagement[server][channel] = score

        return engagement

    def _parse_activity_table(self, content: str) -> list[dict]:
        """Parse activity table into list of dicts."""
        activity = []

        for line in content.split("\n"):
            if not line.startswith("|") or "---" in line or "Date" in line:
                continue

            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                activity.append({
                    "date": parts[0],
                    "action": parts[1],
                    "context": parts[2]
                })

        return activity

    def _render_profile(self, data: ProfileData) -> str:
        """Render ProfileData to markdown string."""
        lines = []

        # Frontmatter
        lines.append("---")
        lines.append("# User Profile - Auto-updated by discord-agent")
        lines.append(f"last_updated: \"{data.last_updated}\"")
        lines.append(f"version: {data.version}")
        lines.append("---")
        lines.append("")
        lines.append("# User Profile")
        lines.append("")

        # Identity
        lines.append("## Identity")
        lines.append(f"- **Name**: {data.name}")
        lines.append(f"- **Role**: {data.role}")
        lines.append("")

        # Interests
        lines.append("## Interests")
        lines.append("Topics extracted from your Discord engagement and queries:")
        if data.interests:
            for interest in data.interests:
                lines.append(f"- {interest}")
        else:
            lines.append("- (none yet)")
        lines.append("")

        # Watch Keywords
        lines.append("## Watch Keywords")
        lines.append("Keywords to highlight in messages:")
        if data.watch_keywords:
            for keyword in data.watch_keywords:
                lines.append(f"- {keyword}")
        else:
            lines.append("- (none yet)")
        lines.append("")

        # Communication Preferences
        lines.append("## Communication Preferences")
        lines.append(f"- **Summary style**: {data.summary_style}")
        lines.append(f"- **Detail level**: {data.detail_level}")
        lines.append(f"- **Timezone**: {data.timezone}")
        lines.append("")

        # Engagement Patterns
        lines.append("## Engagement Patterns")
        lines.append("Servers and channels you focus on most:")
        lines.append("")
        lines.append("| Server | Channel | Engagement Score |")
        lines.append("|--------|---------|------------------|")

        if data.engagement:
            # Flatten and sort by score
            flat = []
            for server, channels in data.engagement.items():
                for channel, score in channels.items():
                    flat.append((server, channel, score))
            flat.sort(key=lambda x: x[2], reverse=True)

            for server, channel, score in flat[:10]:  # Top 10
                lines.append(f"| {server} | #{channel} | {score} |")
        else:
            lines.append("| (none yet) | - | 0 |")

        lines.append("")
        lines.append("Topics you ask about frequently:")
        if data.frequent_topics:
            for topic in data.frequent_topics:
                lines.append(f"- {topic}")
        else:
            lines.append("- (none yet)")
        lines.append("")

        # Activity History
        lines.append("## Activity History")
        lines.append("Recent actions (last 30 days):")
        lines.append("")
        lines.append("| Date | Action | Context |")
        lines.append("|------|--------|---------|")

        if data.activity:
            for entry in data.activity[:self.MAX_ACTIVITY_ENTRIES]:
                lines.append(
                    f"| {entry['date']} | {entry['action']} | {entry['context']} |"
                )
        else:
            lines.append("| - | - | (no activity yet) |")

        lines.append("")

        # Learned Preferences
        lines.append("## Learned Preferences")
        lines.append("Inferred from your interactions:")
        if data.learned:
            for pref in data.learned:
                lines.append(f"- {pref}")
        else:
            lines.append("- (learning in progress)")
        lines.append("")

        return "\n".join(lines)


# Convenience functions

_profile_manager: Optional[ProfileManager] = None


def get_profile() -> ProfileManager:
    """Get global profile manager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager


def reload_profile() -> ProfileManager:
    """Reload profile from disk."""
    global _profile_manager
    _profile_manager = ProfileManager()
    return _profile_manager

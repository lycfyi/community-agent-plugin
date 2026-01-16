"""Profile extraction from synced Discord/Telegram messages.

This module provides automated extraction of member profiles from synced
chat messages. It classifies messages, aggregates activity per member,
and generates observations for the ProfileStore.

Usage:
    from lib.profile_extractor import ProfileExtractor
    from lib.member_profile import ProfileStore

    store = ProfileStore()
    extractor = ProfileExtractor(store)

    # Extract profiles from a server
    result = extractor.extract_from_server("discord", "1092630146143506494")
    print(f"Created {result.profiles_created}, updated {result.profiles_updated}")

    # Check extraction state
    state = ExtractionState.load("discord", "1092630146143506494")
    print(f"Last extraction: {state.last_extraction}")
"""

import os
import re
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

# Add discord-connector path for MessageParser
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "discord-connector"
        / "lib"
        / "analytics"
    ),
)

try:
    from parser import MessageParser, ParsedMessage
except ImportError:
    # Fallback for when running from different contexts
    discord_analytics_path = (
        Path(__file__).parent.parent.parent
        / "discord-connector"
        / "lib"
        / "analytics"
    )
    if discord_analytics_path.exists():
        sys.path.insert(0, str(discord_analytics_path))
        from parser import MessageParser, ParsedMessage
    else:
        raise ImportError(
            "Could not import MessageParser from discord-connector. "
            "Ensure discord-connector plugin is installed."
        )

from .member_profile import ProfileStore, create_profile


# === Constants ===

MIN_MESSAGES_FOR_PROFILE = 3  # Minimum messages to create a profile
MIN_MESSAGES_FOR_ACTIVITY = 5  # Minimum messages to generate activity summary
HIGH_ENGAGEMENT_THRESHOLD = 5  # Reactions needed for "high engagement" observation
MAX_OBSERVATIONS_PER_EXTRACTION = 10  # Max observations to add per member per extraction
STATE_FILENAME = ".extraction_state.yaml"


# === Enums ===


class MessageType(Enum):
    """Classification of message types for profile extraction."""

    GENERAL = "general"
    QUESTION = "question"
    ISSUE_REPORT = "issue_report"
    EXPERTISE = "expertise"
    INTRODUCTION = "introduction"
    HIGH_ENGAGEMENT = "high_engagement"
    FEEDBACK = "feedback"
    FEATURE_REQUEST = "feature_request"


# === Data Classes ===


@dataclass
class ClassifiedMessage:
    """A message with its classification."""

    message: ParsedMessage
    msg_type: MessageType
    keywords: List[str] = field(default_factory=list)


@dataclass
class MemberActivity:
    """Aggregated activity for a single member."""

    member_id: str
    display_name: str
    message_count: int = 0
    channels: Dict[str, int] = field(default_factory=dict)  # channel -> count
    questions: List[ClassifiedMessage] = field(default_factory=list)
    issues: List[ClassifiedMessage] = field(default_factory=list)
    expertise: List[ClassifiedMessage] = field(default_factory=list)
    introductions: List[ClassifiedMessage] = field(default_factory=list)
    high_engagement: List[ClassifiedMessage] = field(default_factory=list)
    feedback: List[ClassifiedMessage] = field(default_factory=list)
    feature_requests: List[ClassifiedMessage] = field(default_factory=list)
    all_keywords: List[str] = field(default_factory=list)
    first_message: Optional[datetime] = None
    last_message: Optional[datetime] = None


@dataclass
class ChannelState:
    """Extraction state for a single channel."""

    last_processed_date: str  # YYYY-MM-DD
    message_count: int = 0


@dataclass
class ExtractionStateData:
    """Extraction state for a server."""

    last_extraction: Optional[str] = None  # ISO datetime
    channels: Dict[str, ChannelState] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of a profile extraction run."""

    server_id: str
    platform: str
    profiles_created: int = 0
    profiles_updated: int = 0
    messages_processed: int = 0
    members_found: int = 0
    skipped_insufficient_messages: int = 0
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False


# === Extraction State Management ===


class ExtractionState:
    """Manages extraction state for incremental processing."""

    @staticmethod
    def _get_state_path(platform: str, server_id: str) -> Path:
        """Get path to extraction state file."""
        local_dir = os.getenv("CLAUDE_LOCAL_DIR")
        root = Path(local_dir) if local_dir else Path.cwd()
        return root / "profiles" / platform / f".extraction_state_{server_id}.yaml"

    @classmethod
    def load(cls, platform: str, server_id: str) -> ExtractionStateData:
        """Load extraction state for a server.

        Args:
            platform: Platform identifier
            server_id: Server ID

        Returns:
            ExtractionStateData object
        """
        state_path = cls._get_state_path(platform, server_id)

        if not state_path.exists():
            return ExtractionStateData()

        with open(state_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        channels = {}
        for ch_name, ch_data in data.get("channels", {}).items():
            channels[ch_name] = ChannelState(
                last_processed_date=ch_data.get("last_processed_date", ""),
                message_count=ch_data.get("message_count", 0),
            )

        return ExtractionStateData(
            last_extraction=data.get("last_extraction"),
            channels=channels,
        )

    @classmethod
    def save(cls, platform: str, server_id: str, state: ExtractionStateData) -> None:
        """Save extraction state for a server.

        Args:
            platform: Platform identifier
            server_id: Server ID
            state: State to save
        """
        state_path = cls._get_state_path(platform, server_id)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "last_extraction": state.last_extraction,
            "channels": {
                ch_name: {
                    "last_processed_date": ch_state.last_processed_date,
                    "message_count": ch_state.message_count,
                }
                for ch_name, ch_state in state.channels.items()
            },
        }

        # Atomic write
        fd, temp_path = tempfile.mkstemp(dir=state_path.parent, suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
            os.replace(temp_path, state_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    @classmethod
    def reset(cls, platform: str, server_id: str) -> None:
        """Reset extraction state for a server.

        Args:
            platform: Platform identifier
            server_id: Server ID
        """
        state_path = cls._get_state_path(platform, server_id)
        if state_path.exists():
            state_path.unlink()


# === Message Classification ===


class MessageClassifier:
    """Classifies messages for profile extraction."""

    # Patterns for classification
    QUESTION_PATTERNS = [
        r"\?$",  # Ends with question mark
        r"^(how|what|why|when|where|who|which|can|could|would|should|is|are|do|does|did)\b",
        r"\bany(one|body)\s+(know|help|tried)\b",
        r"\bhow to\b",
        r"\bwhat's the\b",
    ]

    ISSUE_PATTERNS = [
        r"\b(not working|doesn't work|won't|broken|error|bug|issue|problem|crash|fail)\b",
        r"\b(returns? (error|500|404|403|401|null|undefined|nothing))\b",
        r"\b(can't|cannot|unable to)\b",
        r"\b(getting|receiving|seeing) (an? )?error\b",
    ]

    EXPERTISE_PATTERNS = [
        r"```[\s\S]*?```",  # Code block (markdown)
        r"\bhere's (how|what|the)\b",
        r"\byou (can|should|need to)\b",
        r"\btry (this|using|adding)\b",
        r"\bthe (fix|solution|answer|issue) is\b",
        r"\bworked for me\b",
    ]

    INTRO_PATTERNS = [
        r"\b(i'?m|i am) (a|an|the|working as)\b",
        r"\bi work (at|for|in|on)\b",
        r"\bjust (joined|discovered|found|started)\b",
        r"\bnew (here|to|member)\b",
        r"\bhello[!,]?\s*(everyone|all|team|folks)\b",
        r"\bintroduc(e|ing) myself\b",
    ]

    FEEDBACK_PATTERNS = [
        r"\b(love|great|awesome|amazing|excellent|fantastic|good job|well done)\b",
        r"\b(hate|terrible|awful|worst|disappointing|frustrating)\b",
        r"\bfeedback\b",
        r"\bsuggestion\b",
    ]

    FEATURE_REQUEST_PATTERNS = [
        r"\b(would be (nice|great|cool|helpful) (to|if))\b",
        r"\b(feature request|please add|wish (you|there was))\b",
        r"\b(it would help|could you add|any plans to)\b",
    ]

    # Intro channels (common names)
    INTRO_CHANNELS = {
        "introductions",
        "introduce-yourself",
        "intro",
        "welcome",
        "new-members",
        "say-hello",
        "say-hi",
    }

    def __init__(self) -> None:
        """Initialize the classifier with compiled patterns."""
        self._question_re = [re.compile(p, re.IGNORECASE) for p in self.QUESTION_PATTERNS]
        self._issue_re = [re.compile(p, re.IGNORECASE) for p in self.ISSUE_PATTERNS]
        self._expertise_re = [re.compile(p, re.IGNORECASE) for p in self.EXPERTISE_PATTERNS]
        self._intro_re = [re.compile(p, re.IGNORECASE) for p in self.INTRO_PATTERNS]
        self._feedback_re = [re.compile(p, re.IGNORECASE) for p in self.FEEDBACK_PATTERNS]
        self._feature_re = [re.compile(p, re.IGNORECASE) for p in self.FEATURE_REQUEST_PATTERNS]

    def classify(self, msg: ParsedMessage) -> MessageType:
        """Classify a message into a type.

        Args:
            msg: Parsed message to classify

        Returns:
            MessageType classification
        """
        content = msg.content.lower()
        channel = msg.channel_name.lower() if msg.channel_name else ""

        # Check high engagement first (based on reactions)
        if msg.total_reactions >= HIGH_ENGAGEMENT_THRESHOLD:
            return MessageType.HIGH_ENGAGEMENT

        # Check introduction (channel + content)
        is_intro_channel = any(
            intro in channel for intro in self.INTRO_CHANNELS
        )
        if is_intro_channel and any(p.search(content) for p in self._intro_re):
            return MessageType.INTRODUCTION

        # Check expertise (replies with code or solutions)
        if msg.is_reply and any(p.search(msg.content) for p in self._expertise_re):
            return MessageType.EXPERTISE

        # Check issue report
        if any(p.search(content) for p in self._issue_re):
            return MessageType.ISSUE_REPORT

        # Check feature request
        if any(p.search(content) for p in self._feature_re):
            return MessageType.FEATURE_REQUEST

        # Check feedback
        if any(p.search(content) for p in self._feedback_re):
            return MessageType.FEEDBACK

        # Check question
        if any(p.search(content) for p in self._question_re):
            return MessageType.QUESTION

        return MessageType.GENERAL

    def extract_keywords(self, messages: List[ParsedMessage], top_n: int = 10) -> List[str]:
        """Extract top keywords from a list of messages.

        Uses simple TF-based extraction without external dependencies.

        Args:
            messages: List of messages to extract keywords from
            top_n: Number of top keywords to return

        Returns:
            List of top keywords
        """
        # Stopwords
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
            "during", "before", "after", "and", "but", "or", "so", "yet", "not",
            "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she",
            "her", "it", "its", "they", "them", "their", "this", "that", "these",
            "those", "what", "which", "who", "whom", "how", "when", "where", "why",
            "all", "each", "any", "some", "no", "just", "only", "now", "then",
            "here", "there", "up", "out", "if", "about", "more", "very", "also",
            "like", "get", "got", "go", "going", "make", "know", "think", "see",
            "want", "use", "try", "one", "two", "first", "new", "good", "way",
            "thing", "something", "anything", "everything", "lol", "yeah", "yes",
            "ok", "okay", "thanks", "thank", "please", "sorry", "oh", "hi", "hello",
            "hey", "well", "much", "many", "even", "still", "really", "actually",
        }

        # Count word frequencies
        word_counts: Dict[str, int] = defaultdict(int)

        for msg in messages:
            # Clean and tokenize
            text = re.sub(r"https?://\S+", "", msg.content)  # Remove URLs
            text = re.sub(r"@\w+", "", text)  # Remove mentions
            text = re.sub(r":\w+:", "", text)  # Remove emoji codes
            text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)  # Keep alphanumeric

            words = text.lower().split()

            for word in words:
                if word and len(word) >= 3 and word not in stopwords:
                    word_counts[word] += 1

        # Sort by frequency and return top N
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:top_n]]


# === Profile Extractor ===


class ProfileExtractor:
    """Extracts member profiles from synced messages."""

    def __init__(self, store: Optional[ProfileStore] = None) -> None:
        """Initialize the extractor.

        Args:
            store: ProfileStore instance. If None, creates a new one.
        """
        self.store = store or ProfileStore()
        self.classifier = MessageClassifier()
        self.parser = MessageParser()

    def _get_server_dir(self, platform: str, server_id: str) -> Optional[Path]:
        """Find the server data directory.

        Args:
            platform: Platform identifier
            server_id: Server ID (numeric part)

        Returns:
            Path to server directory or None if not found
        """
        local_dir = os.getenv("CLAUDE_LOCAL_DIR")
        root = Path(local_dir) if local_dir else Path.cwd()
        servers_dir = root / "data" / platform / "servers"

        if not servers_dir.exists():
            return None

        # Find directory that starts with server_id
        for d in servers_dir.iterdir():
            if d.is_dir() and d.name.startswith(server_id):
                return d

        return None

    def extract_from_server(
        self,
        platform: str,
        server_id: str,
        incremental: bool = True,
        dry_run: bool = False,
        min_messages: int = MIN_MESSAGES_FOR_PROFILE,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> ExtractionResult:
        """Extract profiles from a server's synced messages.

        Args:
            platform: Platform identifier ("discord" or "telegram")
            server_id: Server ID (numeric portion)
            incremental: If True, only process new messages since last extraction
            dry_run: If True, don't actually save profiles
            min_messages: Minimum messages required to create a profile
            progress_callback: Optional callback(stage, current, total)

        Returns:
            ExtractionResult with statistics
        """
        result = ExtractionResult(
            server_id=server_id,
            platform=platform,
            dry_run=dry_run,
        )

        # Find server directory
        server_dir = self._get_server_dir(platform, server_id)
        if not server_dir:
            result.errors.append(f"Server directory not found for {server_id}")
            return result

        # Load extraction state
        state = ExtractionState.load(platform, server_id) if incremental else ExtractionStateData()

        # Aggregate activity per member
        member_activity: Dict[str, MemberActivity] = {}

        # Find all message files
        message_files = list(server_dir.glob("*/messages.md"))
        total_files = len(message_files)

        if progress_callback:
            progress_callback("parsing", 0, total_files)

        new_state = ExtractionStateData(
            last_extraction=datetime.now().isoformat(),
            channels={},
        )

        # Process each channel
        for idx, file_path in enumerate(message_files):
            channel_name = file_path.parent.name
            channel_state = state.channels.get(channel_name)

            if progress_callback:
                progress_callback("parsing", idx + 1, total_files)

            # Parse messages from this channel
            for msg in self.parser.parse_file(file_path, channel_name):
                # Check if we should skip (incremental mode)
                if incremental and channel_state:
                    if msg.date_str <= channel_state.last_processed_date:
                        continue

                result.messages_processed += 1

                # Get or create member activity
                member_id = msg.author_id
                if member_id not in member_activity:
                    member_activity[member_id] = MemberActivity(
                        member_id=member_id,
                        display_name=msg.author_name,
                    )

                activity = member_activity[member_id]

                # Update basic stats
                activity.message_count += 1
                activity.channels[channel_name] = activity.channels.get(channel_name, 0) + 1

                # Update timestamps
                if activity.first_message is None or msg.timestamp < activity.first_message:
                    activity.first_message = msg.timestamp
                if activity.last_message is None or msg.timestamp > activity.last_message:
                    activity.last_message = msg.timestamp

                # Classify and categorize
                msg_type = self.classifier.classify(msg)
                classified = ClassifiedMessage(message=msg, msg_type=msg_type)

                if msg_type == MessageType.QUESTION:
                    activity.questions.append(classified)
                elif msg_type == MessageType.ISSUE_REPORT:
                    activity.issues.append(classified)
                elif msg_type == MessageType.EXPERTISE:
                    activity.expertise.append(classified)
                elif msg_type == MessageType.INTRODUCTION:
                    activity.introductions.append(classified)
                elif msg_type == MessageType.HIGH_ENGAGEMENT:
                    activity.high_engagement.append(classified)
                elif msg_type == MessageType.FEEDBACK:
                    activity.feedback.append(classified)
                elif msg_type == MessageType.FEATURE_REQUEST:
                    activity.feature_requests.append(classified)

            # Update channel state (track last date seen)
            latest_date = ""
            msg_count = 0
            for msg in self.parser.parse_file(file_path, channel_name):
                msg_count += 1
                if msg.date_str > latest_date:
                    latest_date = msg.date_str

            new_state.channels[channel_name] = ChannelState(
                last_processed_date=latest_date or datetime.now().strftime("%Y-%m-%d"),
                message_count=msg_count,
            )

        result.members_found = len(member_activity)

        if progress_callback:
            progress_callback("generating", 0, len(member_activity))

        # Generate profiles for each member
        for idx, (member_id, activity) in enumerate(member_activity.items()):
            if progress_callback:
                progress_callback("generating", idx + 1, len(member_activity))

            # Skip if not enough messages
            if activity.message_count < min_messages:
                result.skipped_insufficient_messages += 1
                continue

            # Extract keywords for this member
            all_messages = []
            for cm in (
                activity.questions
                + activity.issues
                + activity.expertise
                + activity.introductions
                + activity.high_engagement
                + activity.feedback
                + activity.feature_requests
            ):
                all_messages.append(cm.message)

            activity.all_keywords = self.classifier.extract_keywords(all_messages)

            # Generate observations
            observations = self._generate_observations(activity)

            if not observations:
                continue

            # Save or update profile
            if not dry_run:
                try:
                    existing = self.store.get(platform, member_id)
                    if existing:
                        # Add new observations (limited to avoid spam)
                        for obs_text in observations[:MAX_OBSERVATIONS_PER_EXTRACTION]:
                            self.store.add_observation(
                                platform=platform,
                                member_id=member_id,
                                text=obs_text,
                            )
                        result.profiles_updated += 1
                    else:
                        # Create new profile with first observation
                        profile = create_profile(
                            platform=platform,
                            member_id=member_id,
                            display_name=activity.display_name,
                            initial_observation=observations[0],
                        )
                        # Add remaining observations
                        self.store.save(profile)
                        for obs_text in observations[1:MAX_OBSERVATIONS_PER_EXTRACTION]:
                            self.store.add_observation(
                                platform=platform,
                                member_id=member_id,
                                text=obs_text,
                            )
                        result.profiles_created += 1
                except Exception as e:
                    result.errors.append(f"Failed to save profile {member_id}: {e}")
            else:
                # Dry run - just count
                existing = self.store.get(platform, member_id)
                if existing:
                    result.profiles_updated += 1
                else:
                    result.profiles_created += 1

        # Save extraction state
        if not dry_run:
            ExtractionState.save(platform, server_id, new_state)

        return result

    def _generate_observations(self, activity: MemberActivity) -> List[str]:
        """Generate observations from member activity.

        Args:
            activity: Aggregated member activity

        Returns:
            List of observation strings
        """
        observations: List[str] = []

        # 1. Activity summary (if enough messages)
        if activity.message_count >= MIN_MESSAGES_FOR_ACTIVITY:
            top_channels = sorted(
                activity.channels.items(), key=lambda x: x[1], reverse=True
            )[:3]
            channel_str = ", ".join(f"#{ch}" for ch, _ in top_channels)

            keywords_str = ""
            if activity.all_keywords:
                keywords_str = f"; topics: {', '.join(activity.all_keywords[:5])}"

            observations.append(
                f"Active in {channel_str} ({activity.message_count} messages){keywords_str}"
            )

        # 2. Introduction (if present)
        if activity.introductions:
            intro = activity.introductions[0].message
            # Extract self-description
            content = intro.content[:200].replace("\n", " ").strip()
            if content:
                observations.append(f"Self-intro: {content}")

        # 3. Questions asked (summarize if multiple)
        if activity.questions:
            if len(activity.questions) == 1:
                q = activity.questions[0].message.content[:150].replace("\n", " ")
                observations.append(f"Asked: {q}")
            else:
                # Summarize topics
                keywords = self.classifier.extract_keywords(
                    [cm.message for cm in activity.questions], top_n=5
                )
                if keywords:
                    observations.append(
                        f"Asked {len(activity.questions)} questions about: {', '.join(keywords)}"
                    )

        # 4. Issues reported
        if activity.issues:
            if len(activity.issues) == 1:
                issue = activity.issues[0].message.content[:150].replace("\n", " ")
                observations.append(f"Reported issue: {issue}")
            else:
                keywords = self.classifier.extract_keywords(
                    [cm.message for cm in activity.issues], top_n=5
                )
                if keywords:
                    observations.append(
                        f"Reported {len(activity.issues)} issues related to: {', '.join(keywords)}"
                    )

        # 5. Expertise demonstrated
        if activity.expertise:
            if len(activity.expertise) == 1:
                exp = activity.expertise[0].message.content[:150].replace("\n", " ")
                observations.append(f"Helped with: {exp}")
            else:
                keywords = self.classifier.extract_keywords(
                    [cm.message for cm in activity.expertise], top_n=5
                )
                if keywords:
                    observations.append(
                        f"Helped others {len(activity.expertise)} times; expertise: {', '.join(keywords)}"
                    )

        # 6. High engagement posts
        if activity.high_engagement:
            top = max(activity.high_engagement, key=lambda cm: cm.message.total_reactions)
            content = top.message.content[:100].replace("\n", " ")
            observations.append(
                f"Popular post ({top.message.total_reactions} reactions): {content}"
            )

        # 7. Feature requests
        if activity.feature_requests:
            if len(activity.feature_requests) >= 2:
                observations.append(
                    f"Submitted {len(activity.feature_requests)} feature requests"
                )
            else:
                fr = activity.feature_requests[0].message.content[:150].replace("\n", " ")
                observations.append(f"Suggested: {fr}")

        # 8. Feedback given
        if activity.feedback and len(activity.feedback) >= 3:
            observations.append(f"Actively provides feedback ({len(activity.feedback)} messages)")

        return observations

    def get_extraction_status(self, platform: str, server_id: str) -> Dict[str, Any]:
        """Get extraction status for a server.

        Args:
            platform: Platform identifier
            server_id: Server ID

        Returns:
            Status dictionary
        """
        state = ExtractionState.load(platform, server_id)
        server_dir = self._get_server_dir(platform, server_id)

        status = {
            "server_id": server_id,
            "platform": platform,
            "server_found": server_dir is not None,
            "last_extraction": state.last_extraction,
            "channels_processed": len(state.channels),
            "channel_details": {},
        }

        if server_dir:
            status["server_dir"] = str(server_dir)

            # Get current channel counts
            for file_path in server_dir.glob("*/messages.md"):
                channel_name = file_path.parent.name
                current_count = self.parser.count_messages(file_path)
                prev_state = state.channels.get(channel_name)

                status["channel_details"][channel_name] = {
                    "current_messages": current_count,
                    "last_processed_date": prev_state.last_processed_date if prev_state else None,
                    "prev_message_count": prev_state.message_count if prev_state else 0,
                    "new_messages": current_count - (prev_state.message_count if prev_state else 0),
                }

        return status

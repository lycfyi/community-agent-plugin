"""Message parser for Discord markdown files.

Parses the markdown message format used by the storage module to extract
structured message data for analytics.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple


# Regex patterns for parsing message format
# Message header: ### 10:30 AM - @alice (123456789)
MESSAGE_HEADER_PATTERN = re.compile(
    r'^### (\d{1,2}:\d{2} [AP]M) - @(\w+) \((\d+)\)$'
)

# Date header: ## 2026-01-03
DATE_HEADER_PATTERN = re.compile(r'^## (\d{4}-\d{2}-\d{2})$')

# Reply indicator: ↳ replying to @username:
REPLY_PATTERN = re.compile(r'^↳ replying to @(\w+):')

# Reactions line: Reactions: heart 3 | rocket 5
REACTION_PATTERN = re.compile(r'^Reactions: (.+)$')

# Single reaction: heart 3
SINGLE_REACTION_PATTERN = re.compile(r'(\w+) (\d+)')

# Attachment: [attachment: file.png (245KB) https://...]
ATTACHMENT_PATTERN = re.compile(r'\[attachment: ([^\]]+)\]')

# Embed: > [embed] **Title**
EMBED_PATTERN = re.compile(r'^> \[embed\]')

# YAML frontmatter
FRONTMATTER_PATTERN = re.compile(r'^---\n(.*?)\n---', re.DOTALL)


@dataclass
class ParsedMessage:
    """A single parsed message."""
    timestamp: datetime
    author_name: str
    author_id: str
    content: str
    channel_name: str = ""

    # Reply information
    is_reply: bool = False
    reply_to_author: Optional[str] = None

    # Engagement
    reactions: Dict[str, int] = field(default_factory=dict)
    total_reactions: int = 0

    # Attachments and embeds
    has_attachment: bool = False
    has_embed: bool = False

    # Raw date for grouping
    date_str: str = ""


@dataclass
class ChannelMetadata:
    """Metadata from channel messages file header."""
    channel_name: str
    channel_id: str
    server_name: str
    server_id: str
    last_sync: str


class MessageParser:
    """Parser for markdown message files.

    Handles chunked reading for large files (100k+ messages).
    """

    # Chunk size for processing (number of lines)
    CHUNK_SIZE = 5000

    def __init__(self, chunk_size: int = CHUNK_SIZE):
        """Initialize parser.

        Args:
            chunk_size: Number of lines to process at a time for large files.
        """
        self.chunk_size = chunk_size

    def parse_file(
        self,
        file_path: Path,
        channel_name: str = ""
    ) -> Generator[ParsedMessage, None, None]:
        """Parse messages from a markdown file.

        Yields messages one at a time for memory efficiency.

        Args:
            file_path: Path to messages.md file.
            channel_name: Optional channel name override.

        Yields:
            ParsedMessage objects.
        """
        if not file_path.exists():
            return

        # Read file in chunks for large files
        with open(file_path, 'r', encoding='utf-8') as f:
            current_date = ""
            current_message: Optional[Dict] = None
            content_lines: List[str] = []

            for line in f:
                line = line.rstrip('\n')

                # Check for date header
                date_match = DATE_HEADER_PATTERN.match(line)
                if date_match:
                    # Yield pending message
                    if current_message:
                        yield self._finalize_message(
                            current_message, content_lines, current_date, channel_name
                        )
                        current_message = None
                        content_lines = []

                    current_date = date_match.group(1)
                    continue

                # Check for message header
                header_match = MESSAGE_HEADER_PATTERN.match(line)
                if header_match:
                    # Yield pending message
                    if current_message:
                        yield self._finalize_message(
                            current_message, content_lines, current_date, channel_name
                        )
                        content_lines = []

                    time_str, author_name, author_id = header_match.groups()
                    current_message = {
                        'time_str': time_str,
                        'author_name': author_name,
                        'author_id': author_id,
                        'is_reply': False,
                        'reply_to_author': None,
                        'reactions': {},
                        'has_attachment': False,
                        'has_embed': False,
                    }
                    continue

                # Collect content lines
                if current_message is not None:
                    content_lines.append(line)

            # Yield last message
            if current_message:
                yield self._finalize_message(
                    current_message, content_lines, current_date, channel_name
                )

    def _finalize_message(
        self,
        msg_data: Dict,
        content_lines: List[str],
        date_str: str,
        channel_name: str
    ) -> ParsedMessage:
        """Finalize a message by parsing content lines.

        Args:
            msg_data: Partial message data from header.
            content_lines: Raw content lines.
            date_str: Date string for the message.
            channel_name: Channel name.

        Returns:
            Complete ParsedMessage object.
        """
        # Parse timestamp
        timestamp = self._parse_timestamp(date_str, msg_data['time_str'])

        # Process content lines
        clean_content = []
        reactions = {}
        is_reply = False
        reply_to_author = None
        has_attachment = False
        has_embed = False

        for line in content_lines:
            # Check for reply indicator
            reply_match = REPLY_PATTERN.match(line)
            if reply_match:
                is_reply = True
                reply_to_author = reply_match.group(1)
                continue

            # Check for reactions
            reaction_match = REACTION_PATTERN.match(line)
            if reaction_match:
                reactions = self._parse_reactions(reaction_match.group(1))
                continue

            # Check for attachment
            if ATTACHMENT_PATTERN.search(line):
                has_attachment = True

            # Check for embed
            if EMBED_PATTERN.match(line):
                has_embed = True

            # Skip empty lines at start
            if not clean_content and not line.strip():
                continue

            clean_content.append(line)

        # Remove trailing empty lines
        while clean_content and not clean_content[-1].strip():
            clean_content.pop()

        total_reactions = sum(reactions.values())

        return ParsedMessage(
            timestamp=timestamp,
            author_name=msg_data['author_name'],
            author_id=msg_data['author_id'],
            content='\n'.join(clean_content),
            channel_name=channel_name,
            is_reply=is_reply,
            reply_to_author=reply_to_author,
            reactions=reactions,
            total_reactions=total_reactions,
            has_attachment=has_attachment,
            has_embed=has_embed,
            date_str=date_str,
        )

    def _parse_timestamp(self, date_str: str, time_str: str) -> datetime:
        """Parse date and time strings into datetime.

        Args:
            date_str: Date in YYYY-MM-DD format.
            time_str: Time in H:MM AM/PM format.

        Returns:
            datetime object.
        """
        try:
            combined = f"{date_str} {time_str}"
            return datetime.strptime(combined, "%Y-%m-%d %I:%M %p")
        except ValueError:
            # Fallback to current time if parsing fails
            return datetime.now()

    def _parse_reactions(self, reaction_str: str) -> Dict[str, int]:
        """Parse reaction string into dict.

        Args:
            reaction_str: String like "heart 3 | rocket 5"

        Returns:
            Dict of emoji -> count.
        """
        reactions = {}
        parts = reaction_str.split(' | ')
        for part in parts:
            match = SINGLE_REACTION_PATTERN.match(part.strip())
            if match:
                emoji, count = match.groups()
                reactions[emoji] = int(count)
        return reactions

    def parse_channel_metadata(self, file_path: Path) -> Optional[ChannelMetadata]:
        """Parse channel metadata from frontmatter.

        Args:
            file_path: Path to messages.md file.

        Returns:
            ChannelMetadata or None if not found.
        """
        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            # Read first 1KB for frontmatter
            content = f.read(1024)

        match = FRONTMATTER_PATTERN.match(content)
        if not match:
            return None

        frontmatter = match.group(1)
        metadata = {}
        for line in frontmatter.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

        return ChannelMetadata(
            channel_name=metadata.get('channel_name', ''),
            channel_id=metadata.get('channel_id', ''),
            server_name=metadata.get('server_name', ''),
            server_id=metadata.get('server_id', ''),
            last_sync=metadata.get('last_sync', ''),
        )

    def count_messages(self, file_path: Path) -> int:
        """Count messages in a file without full parsing.

        Args:
            file_path: Path to messages.md file.

        Returns:
            Number of messages.
        """
        if not file_path.exists():
            return 0

        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if MESSAGE_HEADER_PATTERN.match(line):
                    count += 1
        return count

    def parse_directory(
        self,
        server_dir: Path,
        progress_callback: Optional[callable] = None
    ) -> Generator[ParsedMessage, None, None]:
        """Parse all messages from a server directory.

        Args:
            server_dir: Path to server data directory.
            progress_callback: Optional callback(current, total) for progress.

        Yields:
            ParsedMessage objects from all channels.
        """
        if not server_dir.exists():
            return

        # Find all messages.md files
        message_files = list(server_dir.glob("*/messages.md"))
        total_files = len(message_files)

        for idx, file_path in enumerate(message_files):
            channel_name = file_path.parent.name

            if progress_callback:
                progress_callback(idx + 1, total_files)

            yield from self.parse_file(file_path, channel_name)

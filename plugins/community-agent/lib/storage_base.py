"""Base storage utilities for community agent plugins.

Shared file I/O patterns for Discord, Telegram, and other platforms.
"""

import re
from pathlib import Path
from typing import List


class StorageError(Exception):
    """Storage operation failed."""
    pass


def ensure_dir(path: Path) -> None:
    """Ensure a directory exists.

    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)


def sanitize_name(name: str) -> str:
    """Sanitize a name for use as directory/filename.

    Removes characters that are invalid in file paths across platforms.

    Args:
        name: Name to sanitize

    Returns:
        Sanitized lowercase name
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.lower().strip()


def slugify(name: str, max_length: int = 50) -> str:
    """Convert a name to a URL-friendly slug.

    Args:
        name: Name to convert
        max_length: Maximum slug length (default 50)

    Returns:
        URL-friendly slug
    """
    # Remove special characters, keep alphanumeric and spaces
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    # Replace spaces with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug[:max_length]


def parse_last_n_messages(content: str, last_n: int) -> str:
    """Extract last N messages from markdown content.

    Messages are identified by ### headers.

    Args:
        content: Full markdown content
        last_n: Number of messages to extract

    Returns:
        Content with header + last N messages
    """
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
        messages = "\n".join(lines[start_idx:])
        return header + "\n" + messages

    return content


def search_message_blocks(content: str, keyword: str) -> List[str]:
    """Search for messages containing a keyword.

    Parses markdown content into message blocks and filters by keyword.

    Args:
        content: Full markdown content
        keyword: Search keyword (case-insensitive)

    Returns:
        List of matching message blocks
    """
    lines = content.split("\n")
    current_block: List[str] = []
    blocks: List[str] = []
    in_message = False

    for line in lines:
        if line.startswith("### "):
            # Start of new message
            if current_block and in_message:
                blocks.append("\n".join(current_block))
            current_block = [line]
            in_message = True
        elif line.startswith("## ") or line.startswith("# "):
            # Date header or file header - end current block
            if current_block and in_message:
                blocks.append("\n".join(current_block))
            current_block = []
            in_message = False
        elif in_message:
            current_block.append(line)

    # Don't forget the last block
    if current_block and in_message:
        blocks.append("\n".join(current_block))

    # Filter by keyword
    keyword_lower = keyword.lower()
    return [block for block in blocks if keyword_lower in block.lower()]

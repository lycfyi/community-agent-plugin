"""Base markdown formatting utilities for community agent plugins.

Shared formatting functions for Discord, Telegram, and other platforms.
"""

from datetime import datetime
from typing import Dict, List


def format_reply_indicator(reply_to_author: str) -> str:
    """Format a reply indicator line.

    Args:
        reply_to_author: Name of user being replied to

    Returns:
        Reply indicator string with arrow
    """
    return f"↳ replying to @{reply_to_author}:"


def format_date_header(date_str: str) -> str:
    """Format a date section header.

    Args:
        date_str: Date string (typically YYYY-MM-DD format)

    Returns:
        Formatted date header
    """
    return f"## {date_str}"


def group_messages_by_date(messages: List[dict]) -> Dict[str, List[dict]]:
    """Group messages by date.

    Args:
        messages: List of message dicts with 'timestamp' field (ISO 8601)

    Returns:
        Dict mapping date strings (YYYY-MM-DD) to lists of messages
    """
    groups: Dict[str, List[dict]] = {}

    for msg in messages:
        timestamp = msg.get("timestamp", "")
        if not timestamp:
            continue

        # Extract date from ISO timestamp
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")

        if date_str not in groups:
            groups[date_str] = []
        groups[date_str].append(msg)

    return groups


def format_size_bytes(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., "1.5MB", "256KB", "512B")
    """
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f}KB"
    else:
        return f"{size_bytes}B"

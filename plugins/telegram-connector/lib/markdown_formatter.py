"""Markdown formatter for Telegram messages.

Matches discord-agent format for cross-platform compatibility.
"""

from datetime import datetime
from typing import Dict, List, Optional


def format_message_header(
    timestamp: str,
    sender_name: str,
    sender_id: int,
    sender_username: Optional[str] = None
) -> str:
    """Format a message header in markdown.

    Args:
        timestamp: ISO 8601 timestamp
        sender_name: Display name of sender
        sender_id: Telegram user ID
        sender_username: Optional @username

    Returns:
        Formatted header string
    """
    # Parse timestamp and format as "10:30 AM"
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    time_str = dt.strftime("%-I:%M %p")

    # Use username if available, otherwise use display name
    display = f"@{sender_username}" if sender_username else sender_name

    return f"### {time_str} - {display} ({sender_id})"


def format_reply_indicator(reply_to_author: str) -> str:
    """Format a reply indicator line.

    Args:
        reply_to_author: Name of user being replied to

    Returns:
        Reply indicator string
    """
    return f"↳ replying to @{reply_to_author}:"


def format_forward_indicator(forward_from: str) -> str:
    """Format a forward indicator line.

    Args:
        forward_from: Source of the forwarded message

    Returns:
        Forward indicator string
    """
    return f"↪ forwarded from {forward_from}:"


def format_attachment(attachment: dict) -> str:
    """Format an attachment reference.

    Args:
        attachment: Attachment dict with type, filename, size, etc.

    Returns:
        Formatted attachment string
    """
    att_type = attachment.get("type", "file")
    filename = attachment.get("filename")
    size_bytes = attachment.get("size", 0)
    duration = attachment.get("duration")
    caption = attachment.get("caption")

    # Format size
    size_str = ""
    if size_bytes:
        if size_bytes >= 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
        elif size_bytes >= 1024:
            size_str = f"{size_bytes / 1024:.0f}KB"
        else:
            size_str = f"{size_bytes}B"

    # Format based on type
    if att_type == "photo":
        if filename and size_str:
            result = f"[photo: {filename} ({size_str})]"
        elif caption:
            result = f"[photo: {caption}]"
        else:
            result = "[photo]"
    elif att_type == "video":
        duration_str = f"{duration}s" if duration else ""
        if filename and size_str:
            result = f"[video: {filename} ({size_str}) {duration_str}]".strip()
        elif duration_str:
            result = f"[video: {duration_str}]"
        else:
            result = "[video]"
    elif att_type == "voice":
        duration_str = f"{duration}s" if duration else ""
        result = f"[voice: {duration_str}]" if duration_str else "[voice]"
    elif att_type == "audio":
        if filename:
            result = f"[audio: {filename}]"
        elif duration:
            result = f"[audio: {duration}s]"
        else:
            result = "[audio]"
    elif att_type == "sticker":
        emoji = attachment.get("emoji", "")
        result = f"[sticker: {emoji}]" if emoji else "[sticker]"
    elif att_type == "animation":
        result = "[GIF]"
    elif att_type == "document":
        if filename and size_str:
            result = f"[file: {filename} ({size_str})]"
        elif filename:
            result = f"[file: {filename}]"
        else:
            result = "[file]"
    else:
        result = f"[{att_type}]"

    # Add caption if present and not already included
    if caption and caption not in result:
        result += f"\n{caption}"

    return result


def format_reactions(reactions: List[dict]) -> str:
    """Format reaction emojis with counts.

    Args:
        reactions: List of reaction dicts with emoji and count

    Returns:
        Formatted reactions string
    """
    if not reactions:
        return ""

    parts = []
    for reaction in reactions:
        emoji = reaction.get("emoji", "?")
        count = reaction.get("count", 0)
        parts.append(f"{emoji} {count}")

    return "Reactions: " + " | ".join(parts)


def format_message(message: dict) -> str:
    """Format a complete message in markdown.

    Args:
        message: Message dict with all metadata (MessageInfo from contracts)

    Returns:
        Complete formatted message block
    """
    lines = []

    # Header - use sender_name/sender_username instead of author_name
    header = format_message_header(
        timestamp=message.get("timestamp", ""),
        sender_name=message.get("sender_name", "Unknown"),
        sender_id=message.get("sender_id", 0),
        sender_username=message.get("sender_username")
    )
    lines.append(header)

    # Forward indicator (if forwarded)
    forward_from = message.get("forward_from")
    if forward_from:
        lines.append(format_forward_indicator(forward_from))

    # Reply indicator (if replying to someone)
    reply_to = message.get("reply_to_author")
    if reply_to:
        lines.append(format_reply_indicator(reply_to))

    # Message content
    content = message.get("content", "")
    if content:
        lines.append(content)

    # Attachments
    attachments = message.get("attachments", [])
    for att in attachments:
        lines.append("")
        lines.append(format_attachment(att))

    # Reactions
    reactions = message.get("reactions", [])
    if reactions:
        lines.append("")
        lines.append(format_reactions(reactions))

    return "\n".join(lines)


def format_group_header(
    group_name: str,
    group_id: int,
    group_type: str,
    topic_name: Optional[str] = None,
    topic_id: Optional[int] = None,
    last_sync: Optional[str] = None
) -> str:
    """Format the header for a group messages file.

    Args:
        group_name: Group display name
        group_id: Telegram group ID
        group_type: Group type (group, supergroup, channel)
        topic_name: Optional topic name for forum groups
        topic_id: Optional topic ID
        last_sync: Last sync timestamp

    Returns:
        Complete file header
    """
    lines = [
        f"# {group_name}",
        "",
        f"Group: {group_name} ({group_id})",
        f"Type: {group_type}"
    ]

    if topic_name and topic_id:
        lines.append(f"Topic: {topic_name} ({topic_id})")

    if last_sync:
        lines.append(f"Last synced: {last_sync}")

    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def format_date_header(date_str: str) -> str:
    """Format a date section header.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Formatted date header
    """
    return f"## {date_str}"


def group_messages_by_date(messages: List[dict]) -> Dict[str, List[dict]]:
    """Group messages by date.

    Args:
        messages: List of message dicts with timestamps

    Returns:
        Dict mapping date strings to lists of messages
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


def format_messages_markdown(
    messages: List[dict],
    group_name: str,
    group_id: int,
    group_type: str,
    topic_name: Optional[str] = None,
    topic_id: Optional[int] = None,
    last_sync: Optional[str] = None
) -> str:
    """Format a complete messages file in markdown.

    Args:
        messages: List of message dicts
        group_name: Group display name
        group_id: Telegram group ID
        group_type: Group type
        topic_name: Optional topic name
        topic_id: Optional topic ID
        last_sync: Last sync timestamp

    Returns:
        Complete markdown file content
    """
    lines = []

    # File header
    header = format_group_header(
        group_name=group_name,
        group_id=group_id,
        group_type=group_type,
        topic_name=topic_name,
        topic_id=topic_id,
        last_sync=last_sync
    )
    lines.append(header)

    # Group messages by date
    date_groups = group_messages_by_date(messages)

    # Sort dates in reverse order (newest first)
    sorted_dates = sorted(date_groups.keys(), reverse=True)

    for date_str in sorted_dates:
        lines.append(format_date_header(date_str))
        lines.append("")

        # Sort messages within date by timestamp (oldest first for readability)
        day_messages = sorted(
            date_groups[date_str],
            key=lambda m: m.get("timestamp", "")
        )

        for msg in day_messages:
            lines.append(format_message(msg))
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)

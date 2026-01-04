"""Markdown formatter for Discord messages with reply indicators."""

from datetime import datetime
from typing import List, Optional


def format_message_header(
    timestamp: str,
    author_name: str,
    author_id: str,
    reply_to_author: Optional[str] = None
) -> str:
    """Format a message header in markdown.

    Args:
        timestamp: ISO 8601 timestamp
        author_name: Display name of author
        author_id: Discord user ID
        reply_to_author: Name of user being replied to (if reply)

    Returns:
        Formatted header string
    """
    # Parse timestamp and format as "10:30 AM"
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    time_str = dt.strftime("%-I:%M %p")

    header = f"### {time_str} - @{author_name} ({author_id})"

    return header


def format_reply_indicator(reply_to_author: str) -> str:
    """Format a reply indicator line.

    Args:
        reply_to_author: Name of user being replied to

    Returns:
        Reply indicator string
    """
    return f"↳ replying to @{reply_to_author}:"


def format_attachment(attachment: dict) -> str:
    """Format an attachment reference.

    Args:
        attachment: Attachment dict with filename, size, url

    Returns:
        Formatted attachment string
    """
    filename = attachment.get("filename", "file")
    size_bytes = attachment.get("size", 0)
    url = attachment.get("url", "")

    # Format size
    if size_bytes >= 1024 * 1024:
        size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
    elif size_bytes >= 1024:
        size_str = f"{size_bytes / 1024:.0f}KB"
    else:
        size_str = f"{size_bytes}B"

    return f"[attachment: {filename} ({size_str}) {url}]"


def format_embed(embed: dict) -> str:
    """Format a rich embed.

    Args:
        embed: Embed dict with type, title, description, url

    Returns:
        Formatted embed string (multiple lines)
    """
    lines = []

    title = embed.get("title")
    description = embed.get("description")
    url = embed.get("url")

    if title:
        lines.append(f"> [embed] **{title}**")
    else:
        lines.append("> [embed]")

    if description:
        # Truncate long descriptions
        desc = description[:200]
        if len(description) > 200:
            desc += "..."
        lines.append(f"> {desc}")

    if url:
        lines.append(f"> {url}")

    return "\n".join(lines)


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

    return " | ".join(parts)


def format_message(message: dict) -> str:
    """Format a complete message in markdown.

    Args:
        message: Message dict with all metadata

    Returns:
        Complete formatted message block
    """
    lines = []

    # Header
    header = format_message_header(
        timestamp=message.get("timestamp", ""),
        author_name=message.get("author_name", "Unknown"),
        author_id=message.get("author_id", "0")
    )
    lines.append(header)

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

    # Embeds
    embeds = message.get("embeds", [])
    for embed in embeds:
        lines.append("")
        lines.append(format_embed(embed))

    # Reactions
    reactions = message.get("reactions", [])
    if reactions:
        lines.append("")
        lines.append(format_reactions(reactions))

    return "\n".join(lines)


def format_channel_header(
    channel_name: str,
    channel_id: str,
    server_name: str,
    server_id: str,
    last_sync: Optional[str] = None
) -> str:
    """Format the header for a channel messages file.

    Args:
        channel_name: Channel display name
        channel_id: Channel ID
        server_name: Server display name
        server_id: Server ID
        last_sync: Last sync timestamp

    Returns:
        Complete file header
    """
    lines = [
        f"# #{channel_name}",
        "",
        f"Server: {server_name} ({server_id})",
        f"Channel: {channel_name} ({channel_id})"
    ]

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


def group_messages_by_date(messages: List[dict]) -> dict:
    """Group messages by date.

    Args:
        messages: List of message dicts with timestamps

    Returns:
        Dict mapping date strings to lists of messages
    """
    groups = {}

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
    channel_name: str,
    channel_id: str,
    server_name: str,
    server_id: str,
    last_sync: Optional[str] = None
) -> str:
    """Format a complete messages file in markdown.

    Args:
        messages: List of message dicts
        channel_name: Channel display name
        channel_id: Channel ID
        server_name: Server display name
        server_id: Server ID
        last_sync: Last sync timestamp

    Returns:
        Complete markdown file content
    """
    lines = []

    # File header
    header = format_channel_header(
        channel_name=channel_name,
        channel_id=channel_id,
        server_name=server_name,
        server_id=server_id,
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

#!/usr/bin/env python3
"""Read synced Telegram messages.

Usage:
    python telegram_read.py --group GROUP_ID [--last N] [--search KEYWORD] [--date DATE]

Options:
    --group GROUP_ID    Group to read from
    --last N            Show last N messages
    --search KEYWORD    Search for keyword
    --date DATE         Filter by date (YYYY-MM-DD)
    --json              Output as JSON

Output:
    Messages in Markdown format or JSON

Exit Codes:
    0 - Success
    1 - No synced data found
    2 - Group not found
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.storage import get_storage, StorageError


def read_messages(
    group_id: int,
    topic_name: str = "general",
    last_n: int | None = None,
    search: str | None = None,
    date_filter: str | None = None,
    output_json: bool = False,
) -> int:
    """Read messages from storage.

    Args:
        group_id: Group ID to read
        topic_name: Topic name (default "general")
        last_n: Show last N messages
        search: Search keyword
        date_filter: Date filter (YYYY-MM-DD)
        output_json: Output as JSON

    Returns:
        Exit code
    """
    storage = get_storage()

    try:
        if search:
            # Search mode
            results = storage.search_messages(group_id, topic_name, search)

            if not results:
                if output_json:
                    print(json.dumps({"query": search, "matches": []}))
                else:
                    print(f"No messages matching '{search}' found.")
                return 0

            if output_json:
                print(json.dumps({
                    "query": search,
                    "match_count": len(results),
                    "matches": results,
                }))
            else:
                print(f"Found {len(results)} messages matching '{search}':")
                print()
                for match in results:
                    print(match)
                    print()
                    print("-" * 40)

            return 0

        else:
            # Read mode
            content = storage.read_messages(group_id, topic_name, last_n)

            # Filter by date if specified
            if date_filter:
                filtered_lines = []
                in_target_date = False
                current_date_section = []

                for line in content.split("\n"):
                    if line.startswith("## "):
                        # Check if this is our target date
                        if date_filter in line:
                            in_target_date = True
                            current_date_section = [line]
                        else:
                            if in_target_date and current_date_section:
                                filtered_lines.extend(current_date_section)
                            in_target_date = False
                            current_date_section = []
                    elif in_target_date:
                        current_date_section.append(line)

                # Add last section if it matches
                if in_target_date and current_date_section:
                    filtered_lines.extend(current_date_section)

                if not filtered_lines:
                    if output_json:
                        print(json.dumps({"date": date_filter, "content": None}))
                    else:
                        print(f"No messages found for date {date_filter}")
                    return 0

                content = "\n".join(filtered_lines)

            if output_json:
                # Parse content into structured format
                messages = parse_messages_to_json(content)
                print(json.dumps({
                    "group_id": group_id,
                    "topic": topic_name,
                    "message_count": len(messages),
                    "messages": messages,
                }))
            else:
                print(content)

            return 0

    except StorageError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def parse_messages_to_json(content: str) -> list:
    """Parse markdown messages to JSON structure.

    Args:
        content: Markdown content

    Returns:
        List of message dicts
    """
    messages = []
    current_message = None
    current_date = None

    for line in content.split("\n"):
        if line.startswith("## "):
            # Date header
            current_date = line.replace("## ", "").strip()
        elif line.startswith("### "):
            # Message header - save previous message
            if current_message:
                messages.append(current_message)

            # Parse header: ### 10:30 AM - @username (id)
            header = line.replace("### ", "").strip()
            parts = header.split(" - ", 1)
            time_str = parts[0] if parts else ""
            author_part = parts[1] if len(parts) > 1 else ""

            current_message = {
                "date": current_date,
                "time": time_str,
                "author": author_part,
                "content": [],
            }
        elif current_message is not None:
            if line.strip():
                current_message["content"].append(line)

    # Don't forget the last message
    if current_message:
        messages.append(current_message)

    # Join content arrays
    for msg in messages:
        msg["content"] = "\n".join(msg["content"])

    return messages


def main(args: argparse.Namespace) -> int:
    """Main entry point.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    try:
        config = get_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    # Determine which group to read
    group_id = args.group
    if not group_id:
        group_id = config.default_group_id
        if not group_id:
            print("No group specified and no default group configured.", file=sys.stderr)
            print("Use --group GROUP_ID or run 'telegram-init --group GROUP_ID'", file=sys.stderr)
            return 2

    group_id = int(group_id)

    return read_messages(
        group_id=group_id,
        topic_name=args.topic or "general",
        last_n=args.last,
        search=args.search,
        date_filter=args.date,
        output_json=args.json,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Read synced Telegram messages"
    )
    parser.add_argument(
        "--group",
        type=str,
        help="Group ID to read (uses default if not specified)"
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="Topic name (for forum groups)"
    )
    parser.add_argument(
        "--last",
        type=int,
        help="Show last N messages"
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Search for keyword"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Filter by date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = main(args)
    sys.exit(exit_code)

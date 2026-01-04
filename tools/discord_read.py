#!/usr/bin/env python3
"""Discord read tool - Read and search synced messages.

Usage:
    python tools/discord_read.py --channel general
    python tools/discord_read.py --channel general --last 20
    python tools/discord_read.py --channel general --search "project update"
    python tools/discord_read.py --channel general --from 2026-01-01 --to 2026-01-03
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.storage import get_storage, StorageError


def read_messages(
    channel_name: str,
    server_id: Optional[str] = None,
    last_n: Optional[int] = None
) -> str:
    """Read messages from a channel.

    Args:
        channel_name: Channel name
        server_id: Server ID (uses config if not specified)
        last_n: Only return last N messages

    Returns:
        Formatted message content
    """
    config = get_config()
    server_id = server_id or config.server_id

    storage = get_storage()
    return storage.read_messages(
        server_id=server_id,
        channel_name=channel_name,
        last_n=last_n
    )


def search_messages(
    channel_name: str,
    keyword: str,
    server_id: Optional[str] = None
) -> str:
    """Search messages for a keyword.

    Args:
        channel_name: Channel name
        keyword: Search keyword
        server_id: Server ID (uses config if not specified)

    Returns:
        Formatted search results
    """
    config = get_config()
    server_id = server_id or config.server_id

    storage = get_storage()
    matches = storage.search_messages(
        server_id=server_id,
        channel_name=channel_name,
        keyword=keyword
    )

    if not matches:
        return f"No messages found containing '{keyword}' in #{channel_name}"

    result = [f"Found {len(matches)} message(s) containing '{keyword}':\n"]
    result.append("=" * 50)

    for i, match in enumerate(matches, 1):
        result.append(f"\n[{i}]\n{match}")
        result.append("-" * 40)

    return "\n".join(result)


def filter_by_date(
    content: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> str:
    """Filter message content by date range.

    Args:
        content: Full message content
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)

    Returns:
        Filtered content
    """
    if not from_date and not to_date:
        return content

    lines = content.split("\n")
    result_lines = []
    include_section = False
    current_date = None

    # Parse date boundaries
    from_dt = datetime.strptime(from_date, "%Y-%m-%d") if from_date else None
    to_dt = datetime.strptime(to_date, "%Y-%m-%d") if to_date else None

    for line in lines:
        # Check for date headers (## YYYY-MM-DD)
        if line.startswith("## "):
            date_str = line[3:].strip()
            try:
                current_date = datetime.strptime(date_str, "%Y-%m-%d")

                # Check if date is in range
                in_range = True
                if from_dt and current_date < from_dt:
                    in_range = False
                if to_dt and current_date > to_dt:
                    in_range = False

                include_section = in_range
                if in_range:
                    result_lines.append(line)
            except ValueError:
                # Not a date header, include if we're in a valid section
                if include_section:
                    result_lines.append(line)
        elif line.startswith("# ") or line.startswith("Server:") or line.startswith("Channel:") or line.startswith("Last synced:") or line == "---":
            # Always include header lines
            result_lines.append(line)
        elif include_section:
            result_lines.append(line)

    return "\n".join(result_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Read and search synced Discord messages"
    )

    parser.add_argument(
        "--channel",
        required=True,
        help="Channel name to read from"
    )
    parser.add_argument(
        "--server",
        metavar="SERVER_ID",
        help="Server ID (uses config default if not specified)"
    )
    parser.add_argument(
        "--last",
        type=int,
        metavar="N",
        help="Show only the last N messages"
    )
    parser.add_argument(
        "--search",
        metavar="KEYWORD",
        help="Search for messages containing keyword"
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        metavar="DATE",
        help="Filter messages from this date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        metavar="DATE",
        help="Filter messages until this date (YYYY-MM-DD)"
    )

    args = parser.parse_args()

    try:
        if args.search:
            # Search mode
            result = search_messages(
                channel_name=args.channel,
                keyword=args.search,
                server_id=args.server
            )
            print(result)
        else:
            # Read mode
            content = read_messages(
                channel_name=args.channel,
                server_id=args.server,
                last_n=args.last
            )

            # Apply date filter if specified
            if args.from_date or args.to_date:
                content = filter_by_date(
                    content,
                    from_date=args.from_date,
                    to_date=args.to_date
                )

            print(content)

    except ConfigError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except StorageError as e:
        print(f"Storage Error: {e}", file=sys.stderr)
        print("\nHint: Run sync first to download messages from Discord:")
        print("  python tools/discord_sync.py")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()

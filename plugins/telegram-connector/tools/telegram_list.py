#!/usr/bin/env python3
"""List Telegram groups and topics.

Usage:
    python telegram_list.py [--group GROUP_ID] [--json]

Options:
    --group GROUP_ID    List topics in specific group
    --json              Output as JSON instead of human-readable

Output:
    Human-readable table or JSON array of groups/topics

Exit Codes:
    0 - Success
    1 - Authentication error
    2 - Group not found
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.telegram_client import (
    TelegramUserClient,
    AuthenticationError,
    TelegramClientError,
    PermissionError,
)


async def list_groups(client: TelegramUserClient, output_json: bool) -> int:
    """List all accessible groups.

    Args:
        client: Connected Telegram client
        output_json: Whether to output as JSON

    Returns:
        Exit code
    """
    groups = await client.list_dialogs()

    if not groups:
        if output_json:
            print("[]")
        else:
            print("No groups found.")
        return 0

    # Filter out empty names
    groups = [g for g in groups if g.get("name")]

    if output_json:
        print(json.dumps(groups, indent=2))
    else:
        print(f"Found {len(groups)} groups/channels:")
        print()
        print(f"{'ID':<15} {'Type':<12} {'Members':<10} {'Topics':<8} {'Name'}")
        print("-" * 70)

        for group in groups:
            group_id = group["id"]
            group_type = group["type"]
            member_count = group.get("member_count", 0)
            has_topics = "Yes" if group.get("has_topics") else "-"
            name = group["name"][:35]  # Truncate long names

            print(f"{group_id:<15} {group_type:<12} {member_count:<10} {has_topics:<8} {name}")

        print()
        print("Tip: Use --group GROUP_ID to list topics in a forum group")

    return 0


async def list_topics(client: TelegramUserClient, group_id: int, output_json: bool) -> int:
    """List topics in a specific group.

    Args:
        client: Connected Telegram client
        group_id: Group to list topics for
        output_json: Whether to output as JSON

    Returns:
        Exit code
    """
    try:
        # Get group info
        group = await client.get_group(group_id)

        if not group.get("has_topics"):
            if output_json:
                print(json.dumps({
                    "group": group,
                    "topics": [],
                    "message": "This group does not have forum topics enabled"
                }, indent=2))
            else:
                print(f"Group: {group['name']} ({group_id})")
                print(f"Type: {group['type']}")
                print()
                print("This group does not have forum topics enabled.")
                print("Messages will be synced to a single 'general' topic.")
            return 0

        # List topics
        topics = await client.list_topics(group_id)

        if output_json:
            print(json.dumps({
                "group": group,
                "topics": topics
            }, indent=2))
        else:
            print(f"Group: {group['name']} ({group_id})")
            print(f"Type: {group['type']}")
            print(f"Members: {group.get('member_count', 0)}")
            print()

            if topics:
                print(f"Found {len(topics)} topics:")
                print()
                print(f"{'ID':<15} {'Messages':<12} {'Name'}")
                print("-" * 50)

                for topic in topics:
                    topic_id = topic["id"]
                    message_count = topic.get("message_count", 0)
                    name = topic["name"][:30]

                    print(f"{topic_id:<15} {message_count:<12} {name}")
            else:
                print("No topics found.")

        return 0

    except PermissionError as e:
        print(f"Permission error: {e}", file=sys.stderr)
        return 2

    except TelegramClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


async def main(args: argparse.Namespace) -> int:
    """Main entry point.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    try:
        # Validate config
        get_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("Run 'telegram-init' first to set up credentials.", file=sys.stderr)
        return 2

    # Connect to Telegram
    client = TelegramUserClient()

    try:
        await client.connect()

        if args.group:
            return await list_topics(client, int(args.group), args.json)
        else:
            return await list_groups(client, args.json)

    except AuthenticationError as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        print("Your session may have expired. Run 'telegram-init' again.", file=sys.stderr)
        return 1

    except TelegramClientError as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return 1

    finally:
        await client.disconnect()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="List Telegram groups and topics"
    )
    parser.add_argument(
        "--group",
        type=str,
        help="Group ID to list topics for"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

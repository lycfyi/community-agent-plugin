#!/usr/bin/env python3
"""Send message to Telegram.

Usage:
    python telegram_send.py --group GROUP_ID --message "content" [--reply-to MSG_ID]

Options:
    --group GROUP_ID    Target group ID
    --message TEXT      Message content
    --reply-to MSG_ID   Reply to specific message
    --topic TOPIC_ID    Send to specific topic
    --confirm           Skip confirmation prompt

Output:
    Sent message confirmation

Exit Codes:
    0 - Success
    1 - Authentication error
    2 - Permission denied
    3 - Rate limited

WARNING: Using a user token may violate Telegram's Terms of Service.
This is for personal use only.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.telegram_client import (
    TelegramUserClient,
    AuthenticationError,
    TelegramClientError,
    RateLimitError,
    PermissionError,
)


async def send_message(
    client: TelegramUserClient,
    group_id: int,
    message: str,
    reply_to: int | None = None,
    topic_id: int | None = None,
) -> dict:
    """Send a message to a group.

    Args:
        client: Connected Telegram client
        group_id: Target group ID
        message: Message content
        reply_to: Message ID to reply to
        topic_id: Topic ID for forum groups

    Returns:
        Sent message info
    """
    # Get group info for display
    group = await client.get_group(group_id)
    group_name = group["name"]

    print(f"Sending to: {group_name} ({group_id})")
    if topic_id:
        print(f"Topic: {topic_id}")
    if reply_to:
        print(f"Reply to: {reply_to}")
    print()

    # Send message
    result = await client.send_message(
        group_id=group_id,
        content=message,
        reply_to_id=reply_to,
        topic_id=topic_id,
    )

    return result


async def main(args: argparse.Namespace) -> int:
    """Main entry point.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    # Print warning
    print("=" * 60)
    print("WARNING: Using a user token may violate Telegram's ToS.")
    print("This is for personal use only.")
    print("=" * 60)
    print()

    try:
        config = get_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    # Determine which group to send to
    group_id = args.group
    if not group_id:
        group_id = config.default_group_id
        if not group_id:
            print("No group specified and no default group configured.", file=sys.stderr)
            print("Use --group GROUP_ID or run 'telegram-init --group GROUP_ID'", file=sys.stderr)
            return 2

    group_id = int(group_id)

    # Validate message
    message = args.message
    if not message or not message.strip():
        print("Error: Message cannot be empty.", file=sys.stderr)
        return 2

    # Confirmation prompt
    if not args.confirm:
        print(f"Message to send:")
        print("-" * 40)
        print(message)
        print("-" * 40)
        print()

        response = input("Send this message? (y/N): ").strip().lower()
        if response not in ("y", "yes"):
            print("Cancelled.")
            return 0

    # Connect and send
    print()
    print("Connecting to Telegram...")
    client = TelegramUserClient()

    try:
        await client.connect()

        result = await send_message(
            client=client,
            group_id=group_id,
            message=message,
            reply_to=int(args.reply_to) if args.reply_to else None,
            topic_id=int(args.topic) if args.topic else None,
        )

        print("=" * 40)
        print("Message sent successfully!")
        print(f"Message ID: {result['id']}")
        print(f"Timestamp: {result['timestamp']}")

        return 0

    except AuthenticationError as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        return 1

    except PermissionError as e:
        print(f"Permission error: {e}", file=sys.stderr)
        return 2

    except RateLimitError as e:
        print(f"Rate limited: {e}", file=sys.stderr)
        print(f"Wait {e.wait_seconds} seconds and try again.", file=sys.stderr)
        return 3

    except TelegramClientError as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return 1

    finally:
        await client.disconnect()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Send message to Telegram",
        epilog="WARNING: Using a user token may violate Telegram's ToS."
    )
    parser.add_argument(
        "--group",
        type=str,
        help="Target group ID (uses default if not specified)"
    )
    parser.add_argument(
        "--message", "-m",
        type=str,
        required=True,
        help="Message content to send"
    )
    parser.add_argument(
        "--reply-to",
        type=str,
        help="Message ID to reply to"
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="Topic ID for forum groups"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

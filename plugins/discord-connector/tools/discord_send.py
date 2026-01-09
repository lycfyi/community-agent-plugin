#!/usr/bin/env python3
"""Discord send tool - Send messages to Discord channels.

Usage:
    python tools/discord_send.py --channel CHANNEL_ID --message "Hello!"
    python tools/discord_send.py --channel CHANNEL_ID --message "Reply" --reply-to MESSAGE_ID
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import ConfigError
from lib.discord_client import (
    DiscordUserClient,
    DiscordClientError,
    AuthenticationError
)


async def check_permission(channel_id: str) -> tuple[bool, str]:
    """Check if we have permission to send to a channel.

    Args:
        channel_id: Target channel ID

    Returns:
        Tuple of (can_send: bool, reason: str)
    """
    client = DiscordUserClient()
    try:
        return await client.check_send_permission(channel_id)
    finally:
        await client.close()


async def send_message(
    channel_id: str,
    message: str,
    reply_to_id: Optional[str] = None,
    check_only: bool = False
) -> dict:
    """Send a message to a Discord channel.

    Args:
        channel_id: Target channel ID
        message: Message content
        reply_to_id: Optional message ID to reply to
        check_only: If True, only check permission without sending

    Returns:
        Sent message info, or permission check result if check_only
    """
    client = DiscordUserClient()
    try:
        # First check if we have permission
        can_send, reason = await client.check_send_permission(channel_id)

        if check_only:
            return {"can_send": can_send, "reason": reason}

        if not can_send:
            raise DiscordClientError(reason)

        result = await client.send_message(
            channel_id=channel_id,
            content=message,
            reply_to_id=reply_to_id
        )
        return result
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Send messages to Discord channels"
    )

    parser.add_argument(
        "--channel",
        required=True,
        metavar="CHANNEL_ID",
        help="Target channel ID"
    )
    parser.add_argument(
        "--message",
        required=True,
        help="Message content to send"
    )
    parser.add_argument(
        "--reply-to",
        metavar="MESSAGE_ID",
        help="Message ID to reply to (optional)"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check if we have permission to send (don't actually send)"
    )

    args = parser.parse_args()

    # Handle check-only mode
    if args.check_only:
        try:
            result = asyncio.run(send_message(
                channel_id=args.channel,
                message="",  # Not used in check-only mode
                check_only=True
            ))
            if result["can_send"]:
                print(f"Permission check passed: {result['reason']}")
                sys.exit(0)
            else:
                print(f"Permission check failed: {result['reason']}", file=sys.stderr)
                sys.exit(1)
        except (ConfigError, AuthenticationError, DiscordClientError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate message content (only for actual send)
    if not args.message.strip():
        print("Error: Message cannot be empty", file=sys.stderr)
        sys.exit(1)

    if len(args.message) > 2000:
        print("Error: Message exceeds Discord's 2000 character limit", file=sys.stderr)
        sys.exit(1)

    try:
        result = asyncio.run(send_message(
            channel_id=args.channel,
            message=args.message,
            reply_to_id=args.reply_to
        ))

        # Print confirmation
        print("Message sent successfully!")
        print(f"  Message ID: {result['id']}")
        print(f"  Channel: {result['channel_id']}")
        print(f"  Timestamp: {result['timestamp']}")

        if args.reply_to:
            print(f"  Reply to: {args.reply_to}")

    except ConfigError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except AuthenticationError as e:
        print(f"Authentication Error: {e}", file=sys.stderr)
        sys.exit(1)
    except DiscordClientError as e:
        print(f"Discord Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()

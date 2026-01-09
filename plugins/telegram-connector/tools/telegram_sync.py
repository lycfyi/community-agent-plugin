#!/usr/bin/env python3
"""Sync Telegram messages to local storage.

Usage:
    python telegram_sync.py [--group GROUP_ID] [--days N] [--full] [--limit N]

Options:
    --group GROUP_ID    Sync specific group (default: configured group)
    --days N            Sync last N days (default: 7)
    --full              Full sync, ignore previous sync state
    --topic TOPIC_ID    Sync specific topic only
    --limit N           Max messages to sync (default: from config, typically 2000)

Output:
    Progress to stdout, messages saved to data/{group_id}/messages.md

Exit Codes:
    0 - Success
    1 - Authentication error
    2 - Group not found
    3 - Rate limited (includes wait time in error)
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.storage import get_storage
from lib.telegram_client import (
    TelegramUserClient,
    AuthenticationError,
    TelegramClientError,
    RateLimitError,
    PermissionError,
)


async def sync_group(
    client: TelegramUserClient,
    group_id: int,
    days: int,
    full_sync: bool,
    topic_id: int | None = None,
    limit: int | None = None
) -> tuple[int, int]:
    """Sync messages from a group.

    Args:
        client: Connected Telegram client
        group_id: Group to sync
        days: Number of days to sync
        full_sync: Whether to ignore previous sync state
        topic_id: Optional specific topic to sync
        limit: Max messages to sync (None = use default)

    Returns:
        Tuple of (messages_synced, topics_synced)
    """
    storage = get_storage()

    # Get group info
    print(f"Fetching group info...")
    group = await client.get_group(group_id)
    group_name = group["name"]
    group_type = group["type"]
    has_topics = group.get("has_topics", False)

    print(f"Group: {group_name} ({group_id})")
    print(f"Type: {group_type}")

    # Save group metadata
    storage.save_group_metadata(
        group_id=group_id,
        group_name=group_name,
        group_type=group_type,
        username=group.get("username"),
        member_count=group.get("member_count", 0),
        has_topics=has_topics,
    )

    # Calculate date range
    offset_date = None
    if days > 0:
        offset_date = datetime.now(timezone.utc) - timedelta(days=days)
        print(f"Syncing messages from last {days} days")

    total_messages = 0
    topics_synced = 0

    if has_topics and not topic_id:
        # Sync each topic separately
        print(f"Fetching forum topics...")
        topics = await client.list_topics(group_id)

        if topics:
            print(f"Found {len(topics)} topics")

            for topic in topics:
                tid = topic["id"]
                tname = topic["name"]
                print(f"\nSyncing topic: {tname} ({tid})")

                count = await sync_topic(
                    client=client,
                    storage=storage,
                    group_id=group_id,
                    group_name=group_name,
                    topic_id=tid,
                    topic_name=tname,
                    offset_date=offset_date,
                    full_sync=full_sync,
                    limit=limit,
                )
                total_messages += count
                topics_synced += 1
                print(f"  Synced {count} messages")
        else:
            # No topics found, sync as single channel
            count = await sync_topic(
                client=client,
                storage=storage,
                group_id=group_id,
                group_name=group_name,
                topic_id=None,
                topic_name="general",
                offset_date=offset_date,
                full_sync=full_sync,
                limit=limit,
            )
            total_messages += count
            topics_synced = 1

    elif topic_id:
        # Sync specific topic
        topics = await client.list_topics(group_id)
        topic_name = "topic"
        for t in topics:
            if t["id"] == topic_id:
                topic_name = t["name"]
                break

        count = await sync_topic(
            client=client,
            storage=storage,
            group_id=group_id,
            group_name=group_name,
            topic_id=topic_id,
            topic_name=topic_name,
            offset_date=offset_date,
            full_sync=full_sync,
            limit=limit,
        )
        total_messages += count
        topics_synced = 1

    else:
        # Sync as single channel
        count = await sync_topic(
            client=client,
            storage=storage,
            group_id=group_id,
            group_name=group_name,
            topic_id=None,
            topic_name="general",
            offset_date=offset_date,
            full_sync=full_sync,
            limit=limit,
        )
        total_messages += count
        topics_synced = 1

    return total_messages, topics_synced


async def sync_topic(
    client: TelegramUserClient,
    storage,
    group_id: int,
    group_name: str,
    topic_id: int | None,
    topic_name: str,
    offset_date: datetime | None,
    full_sync: bool,
    limit: int | None = None,
) -> int:
    """Sync messages from a specific topic/channel.

    Args:
        client: Connected Telegram client
        storage: Storage instance
        group_id: Group ID
        group_name: Group name
        topic_id: Topic ID (None for non-forum groups)
        topic_name: Topic name
        offset_date: Only sync messages after this date
        full_sync: Whether to ignore previous sync state
        limit: Max messages to sync (None = use default)

    Returns:
        Number of messages synced
    """
    # Get last synced message ID for incremental sync
    min_id = None
    if not full_sync:
        min_id = storage.get_last_message_id(group_id, topic_name)
        if min_id:
            print(f"  Incremental sync from message {min_id}")

    # Fetch messages
    messages = []
    message_count = 0

    async for msg in client.fetch_messages(
        group_id=group_id,
        topic_id=topic_id,
        min_id=min_id,
        offset_date=offset_date,
        limit=limit,
    ):
        messages.append(msg)
        message_count += 1

        # Progress indicator
        if message_count % 100 == 0:
            print(f"  Fetched {message_count} messages...")

    if not messages:
        print(f"  No new messages")
        return 0

    # Save messages
    storage.append_messages(
        group_id=group_id,
        group_name=group_name,
        topic_id=topic_id,
        topic_name=topic_name,
        messages=messages,
    )

    return len(messages)


async def main(args: argparse.Namespace) -> int:
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
        print("Run 'telegram-init' first to set up credentials.", file=sys.stderr)
        return 2

    # Determine which group to sync
    group_id = args.group
    if not group_id:
        group_id = config.default_group_id
        if not group_id:
            print("No group specified and no default group configured.", file=sys.stderr)
            print("Use --group GROUP_ID or run 'telegram-init --group GROUP_ID'", file=sys.stderr)
            return 2

    group_id = int(group_id)

    # Get message limit from args or config
    limit = args.limit or config.max_messages_per_group
    print(f"Message limit: {limit}")

    # Connect to Telegram
    print("Connecting to Telegram...")
    client = TelegramUserClient()

    try:
        await client.connect()

        # Sync messages
        messages_synced, topics_synced = await sync_group(
            client=client,
            group_id=group_id,
            days=args.days,
            full_sync=args.full,
            topic_id=int(args.topic) if args.topic else None,
            limit=limit,
        )

        print()
        print("=" * 40)
        print(f"Sync complete!")
        print(f"  Messages synced: {messages_synced}")
        print(f"  Topics synced: {topics_synced}")

        # Update manifest
        storage = get_storage()
        storage.update_manifest()
        print(f"  Manifest updated")

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
        description="Sync Telegram messages to local storage"
    )
    parser.add_argument(
        "--group",
        type=str,
        help="Group ID to sync (uses default if not specified)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to sync (default: 7)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full sync, ignore previous sync state"
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="Specific topic ID to sync (for forum groups)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Max messages to sync (default: from config, typically 2000)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

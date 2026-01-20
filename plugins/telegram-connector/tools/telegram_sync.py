#!/usr/bin/env python3
"""Sync Telegram messages to local storage.

Usage:
    python telegram_sync.py [--group GROUP_ID] [--days N] [--full] [--limit N]
    python telegram_sync.py --dm USER_ID [--days N] [--dm-limit N]
    python telegram_sync.py --no-dms [--group GROUP_ID]

Options:
    --group GROUP_ID    Sync specific group (default: configured group)
    --days N            Sync last N days (default: 7)
    --full              Full sync, ignore previous sync state
    --topic TOPIC_ID    Sync specific topic only
    --limit N           Max messages to sync for groups (default: 2000)
    --dm USER_ID        Sync DMs with specific user only
    --no-dms            Exclude DMs from sync (groups only)
    --dm-limit N        Max messages for DMs (default: 100, privacy-conscious)

Output:
    Progress to stdout, messages saved to:
    - Groups: data/{group_id}/messages.md
    - DMs: dms/telegram/{user_id}-{name}/messages.md

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

    # Get entity type from dialogs first (more reliable entity resolution)
    print(f"Fetching group info...")
    entity_type = None
    try:
        dialogs = await client.list_dialogs()
        for g in dialogs:
            if abs(g["id"]) == abs(group_id):
                entity_type = g["type"]
                break
    except Exception:
        pass  # Fall back to get_group without type hint

    group = await client.get_group(group_id, entity_type=entity_type)
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


async def sync_dm(
    client: TelegramUserClient,
    user_id: int,
    username: str | None,
    display_name: str,
    days: int,
    full_sync: bool,
    limit: int = 100,
) -> int:
    """Sync messages from a DM.

    Args:
        client: Connected Telegram client
        user_id: User ID to sync DMs with
        username: User's @username (if available)
        display_name: User's display name
        days: Number of days to sync
        full_sync: Whether to ignore previous sync state
        limit: Max messages to sync (default: 100)

    Returns:
        Number of messages synced
    """
    storage = get_storage()

    print(f"Syncing DM with: {display_name} (@{username or user_id})")

    # Save user metadata
    storage.save_dm_metadata(
        user_id=user_id,
        username=username,
        display_name=display_name,
    )

    # Calculate date range
    offset_date = None
    if days > 0:
        offset_date = datetime.now(timezone.utc) - timedelta(days=days)
        print(f"  Syncing messages from last {days} days")

    # Get last synced message ID for incremental sync
    min_id = None
    if not full_sync:
        min_id = storage.get_dm_last_message_id(user_id)
        if min_id:
            print(f"  Incremental sync from message {min_id}")

    # Fetch messages from the DM
    messages = []
    message_count = 0

    async for msg in client.fetch_messages(
        group_id=user_id,  # For DMs, the "group_id" is the user_id
        topic_id=None,
        min_id=min_id,
        offset_date=offset_date,
        limit=limit,
    ):
        messages.append(msg)
        message_count += 1

        # Progress indicator
        if message_count % 50 == 0:
            print(f"  Fetched {message_count} messages...")

    if not messages:
        print(f"  No new messages")
        return 0

    # Save messages
    storage.append_dm_messages(
        user_id=user_id,
        username=username,
        display_name=display_name,
        messages=messages,
    )

    print(f"  Synced {len(messages)} messages")
    return len(messages)


async def sync_all_dms(
    client: TelegramUserClient,
    days: int,
    full_sync: bool,
    limit: int = 100,
) -> tuple[int, int]:
    """Sync all DMs.

    Args:
        client: Connected Telegram client
        days: Number of days to sync
        full_sync: Whether to ignore previous sync state
        limit: Max messages per DM (default: 100)

    Returns:
        Tuple of (total_messages, total_dms)
    """
    # Get all DMs (private chats)
    print("Fetching DM list...")
    dialogs = await client.list_dialogs(include_dms=True)

    # Filter to only private chats
    dms = [d for d in dialogs if d.get("type") == "private"]

    if not dms:
        print("No DMs found.")
        return 0, 0

    print(f"Found {len(dms)} DMs to sync")
    print()

    total_messages = 0
    synced_dms = 0

    for dm in dms:
        user_id = dm["id"]
        username = dm.get("username")
        display_name = dm["name"]

        count = await sync_dm(
            client=client,
            user_id=user_id,
            username=username,
            display_name=display_name,
            days=days,
            full_sync=full_sync,
            limit=limit,
        )

        if count > 0:
            total_messages += count
            synced_dms += 1
        print()

    return total_messages, synced_dms


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

    storage = get_storage()

    # Check for storage migration (v1 -> v2 unified structure)
    if storage.needs_migration():
        print("Detected legacy storage structure. Migrating to unified structure...")
        report = storage.migrate_to_v2()
        if report.get("errors"):
            print(f"Migration completed with {len(report['errors'])} errors:")
            for err in report["errors"]:
                print(f"  - {err}")
        else:
            groups = len(report.get("groups_migrated", []))
            dms = len(report.get("dms_migrated", []))
            print(f"Migration complete: {groups} groups, {dms} DMs moved to data/telegram/")

    # Connect to Telegram
    print("Connecting to Telegram...")
    client = TelegramUserClient()

    try:
        await client.connect()

        total_messages = 0
        total_groups = 0
        total_dms = 0

        # Mode 1: Sync specific DM only (--dm USER_ID)
        if args.dm_user_id:
            print(f"DM sync mode: user ID {args.dm_user_id}")
            print(f"DM message limit: {args.dm_limit}")

            # Find the user in dialogs to get display name
            dialogs = await client.list_dialogs(include_dms=True)
            user_info = None
            for d in dialogs:
                if d["id"] == args.dm_user_id and d.get("type") == "private":
                    user_info = d
                    break

            if not user_info:
                print(f"DM with user {args.dm_user_id} not found.", file=sys.stderr)
                print("Make sure you have an active conversation with this user.", file=sys.stderr)
                return 2

            count = await sync_dm(
                client=client,
                user_id=user_info["id"],
                username=user_info.get("username"),
                display_name=user_info["name"],
                days=args.days,
                full_sync=args.full,
                limit=args.dm_limit,
            )
            total_messages = count
            total_dms = 1 if count > 0 else 0

            # Update DM manifest
            storage.update_dm_manifest()

        # Mode 2: Sync groups only (--no-dms or --group specified)
        elif args.no_dms or args.group:
            group_id = args.group
            if not group_id:
                group_id = config.default_group_id
                if not group_id:
                    # Try to auto-select or show available groups
                    print("No default group configured. Fetching available groups...", file=sys.stderr)

                    groups = await client.list_dialogs(include_dms=False)

                    if len(groups) == 0:
                        print("No accessible groups found.", file=sys.stderr)
                        return 2
                    elif len(groups) == 1:
                        group_id = groups[0]["id"]
                        print(f"Auto-selected only available group: {groups[0]['name']}", file=sys.stderr)
                    else:
                        print(f"\nFound {len(groups)} accessible groups:", file=sys.stderr)
                        for i, g in enumerate(groups[:15], 1):
                            gtype = g.get("type", "unknown")
                            members = g.get("member_count", 0)
                            print(f"  {i:2}. {g['name'][:40]:<40} (ID: {g['id']}, {gtype}, {members} members)", file=sys.stderr)
                        if len(groups) > 15:
                            print(f"  ... and {len(groups) - 15} more", file=sys.stderr)
                        print(f"\nTo sync a specific group:", file=sys.stderr)
                        print(f"  telegram-sync --group GROUP_ID", file=sys.stderr)
                        print(f"\nTo set a default group:", file=sys.stderr)
                        print(f"  telegram-init --group GROUP_ID", file=sys.stderr)
                        return 2

            group_id = int(group_id)

            # Get message limit from args or config
            limit = args.limit or config.max_messages_per_group
            print(f"Message limit: {limit}")

            # Sync group messages
            messages_synced, topics_synced = await sync_group(
                client=client,
                group_id=group_id,
                days=args.days,
                full_sync=args.full,
                topic_id=int(args.topic) if args.topic else None,
                limit=limit,
            )
            total_messages = messages_synced
            total_groups = topics_synced

            # Update manifest
            storage.update_manifest()

        # Mode 3: Sync both groups and DMs (default behavior)
        else:
            print("Syncing groups and DMs (use --no-dms to exclude DMs)")
            print()

            # Get message limits
            group_limit = args.limit or config.max_messages_per_group
            dm_limit = args.dm_limit

            # First sync all DMs
            print("=== Syncing DMs ===")
            print(f"DM message limit: {dm_limit}")
            dm_messages, synced_dms = await sync_all_dms(
                client=client,
                days=args.days,
                full_sync=args.full,
                limit=dm_limit,
            )
            total_messages += dm_messages
            total_dms = synced_dms

            # Update DM manifest
            if synced_dms > 0:
                storage.update_dm_manifest()

            # Then sync groups if there's a default or configured group
            group_id = args.group or config.default_group_id
            if group_id:
                print()
                print("=== Syncing Groups ===")
                print(f"Group message limit: {group_limit}")
                group_id = int(group_id)

                messages_synced, topics_synced = await sync_group(
                    client=client,
                    group_id=group_id,
                    days=args.days,
                    full_sync=args.full,
                    topic_id=int(args.topic) if args.topic else None,
                    limit=group_limit,
                )
                total_messages += messages_synced
                total_groups = topics_synced

                # Update manifest
                storage.update_manifest()
            else:
                print()
                print("Note: No default group configured. Use --group to sync a specific group.")

        print()
        print("=" * 40)
        print(f"Sync complete!")
        print(f"  Messages synced: {total_messages}")
        if total_groups > 0:
            print(f"  Groups/topics synced: {total_groups}")
        if total_dms > 0:
            print(f"  DMs synced: {total_dms}")

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
        help="Max messages to sync for groups (default: from config, typically 2000)"
    )
    # DM-related arguments
    parser.add_argument(
        "--dm",
        type=int,
        dest="dm_user_id",
        help="Sync DMs with specific user ID only"
    )
    parser.add_argument(
        "--no-dms",
        action="store_true",
        dest="no_dms",
        help="Exclude DMs from sync (groups only)"
    )
    parser.add_argument(
        "--dm-limit",
        type=int,
        default=100,
        dest="dm_limit",
        help="Max messages for DMs (default: 100, privacy-conscious)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

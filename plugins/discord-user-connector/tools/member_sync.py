#!/usr/bin/env python3
"""
Discord member sync tool.

Syncs complete member list from Discord servers via Gateway API.
Supports servers with 100k+ members.

NOTE: This tool uses discord.py-self (user token). For fast member syncing
with Gateway Intents, use the discord-bot-connector plugin instead.

Usage:
    python member_sync.py --server SERVER_ID [--enrich-profiles] [--create-profiles] [--include-bots]
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.member_models import (
    MemberSnapshot,
    CurrentMemberList,
    ChurnedMember,
    SyncOperation,
)
from lib.member_storage import get_member_storage
from lib.gateway_client import GatewayMemberFetcher, GatewayClientError

# Import ProfileEnricher - handle both direct execution and module import
try:
    from tools.profile_enricher import ProfileEnricher
except ImportError:
    from profile_enricher import ProfileEnricher


def print_progress(current: int, total: int) -> None:
    """Print a progress bar."""
    if total == 0:
        return

    percent = (current / total) * 100
    bar_length = 40
    filled = int(bar_length * current // total)
    bar = '=' * filled + '>' + ' ' * (bar_length - filled - 1)
    bar = bar[:bar_length]

    # Format numbers with commas
    current_str = f"{current:,}"
    total_str = f"{total:,}"

    print(f"\rSyncing... [{bar}] {current_str}/{total_str} ({percent:.1f}%)", end='', flush=True)


async def sync_members(
    server_id: str,
    include_bots: bool = False,
    enrich_profiles: bool = False,
    create_profiles: bool = False,
    data_dir: str = "./data"
) -> dict:
    """
    Sync members from a Discord server.

    Args:
        server_id: Discord server ID
        include_bots: Include bot accounts
        enrich_profiles: Update unified profiles with Discord data
        create_profiles: Create new profiles for members without one
        data_dir: Base data directory

    Returns:
        Dict with sync results
    """
    storage = get_member_storage(data_dir)
    fetcher = GatewayMemberFetcher()

    sync_id = storage.generate_sync_id()
    started_at = datetime.now(timezone.utc)

    operation = SyncOperation(
        sync_id=sync_id,
        server_id=server_id,
        started_at=started_at,
        sync_source="user_token",  # discord.py-self uses user token
    )

    try:
        # Get server info
        print(f"Connecting to Discord...")
        guild_info = await fetcher.get_guild_info(server_id)
        server_name = guild_info["name"]
        icon_url = guild_info.get("icon_url")
        member_count_estimate = guild_info.get("member_count", 0)

        print(f"Syncing members from {server_name} ({server_id})...")
        print(f"Estimated members: {member_count_estimate:,}")
        print()

        # Fetch all members with progress
        members = await fetcher.fetch_all_members(
            server_id,
            include_bots=include_bots,
            progress_callback=print_progress
        )

        print()  # New line after progress bar
        print()

        # Count bots vs humans
        humans = [m for m in members if not m.is_bot]
        bots = [m for m in members if m.is_bot]

        # Get previous snapshot for change detection
        previous_ids = set()
        previous_snapshot = storage.get_latest_snapshot(server_id)
        if previous_snapshot:
            previous_ids = set(previous_snapshot.member_ids)

        current_ids = {m.user_id for m in members}

        # Detect changes
        new_member_ids = current_ids - previous_ids
        departed_member_ids = previous_ids - current_ids

        new_members = [m for m in members if m.user_id in new_member_ids]
        operation.new_members_count = len(new_members)
        operation.departed_members_count = len(departed_member_ids)

        # Update server metadata
        storage.update_server_metadata_on_sync(
            server_id=server_id,
            server_name=server_name,
            icon_url=icon_url
        )

        # Save current member list
        current_list = CurrentMemberList(
            sync_id=sync_id,
            server_id=server_id,
            server_name=server_name,
            timestamp=started_at,
            member_count=len(members),
            members=members,
        )
        storage.save_current_members(current_list)

        # Save snapshot (IDs only for efficiency)
        snapshot = MemberSnapshot(
            sync_id=sync_id,
            server_id=server_id,
            timestamp=started_at,
            member_count=len(members),
            member_ids=list(current_ids),
            stats={
                "total_members": len(members),
                "humans": len(humans),
                "bots": len(bots),
                "new_since_last_sync": len(new_member_ids),
                "departed_since_last_sync": len(departed_member_ids),
            }
        )
        storage.save_snapshot(snapshot, server_name)

        # Handle churned members
        if departed_member_ids and previous_snapshot:
            print(f"Detecting {len(departed_member_ids)} departed members...")
            await _process_churned_members(
                departed_member_ids,
                sync_id,
                started_at,
                server_id,
                server_name,
                storage
            )

        # Profile enrichment (if enabled)
        if enrich_profiles:
            print("Enriching unified profiles...")
            enricher = ProfileEnricher(data_dir)

            def enrich_progress(current: int, total: int) -> None:
                percent = (current / total) * 100
                print(f"\rEnriching... {current:,}/{total:,} ({percent:.1f}%)", end='', flush=True)

            enrich_stats = enricher.enrich_profiles_from_members(
                members=members,
                server_id=server_id,
                server_name=server_name,
                create_new=create_profiles,
                progress_callback=enrich_progress,
            )

            print()  # New line after progress
            operation.profiles_created = enrich_stats["created"]
            operation.profiles_updated = enrich_stats["updated"]
            operation.profiles_skipped = enrich_stats["skipped"]

            print(f"- Profiles created: {enrich_stats['created']:,}")
            print(f"- Profiles updated: {enrich_stats['updated']:,}")
            if enrich_stats['failed'] > 0:
                print(f"- Profiles failed: {enrich_stats['failed']:,}")

        # Complete operation
        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        operation.member_count = len(members)
        operation.completed_at = completed_at
        operation.duration_seconds = duration
        operation.status = "success"

        storage.save_sync_operation(operation, server_name)

        # Print summary
        print(f"Sync complete in {duration:.1f} seconds")
        print(f"- Total members: {len(members):,} ({len(humans):,} humans, {len(bots):,} bots)")
        print(f"- New since last sync: {len(new_member_ids):,}")
        print(f"- Departed since last sync: {len(departed_member_ids):,}")
        print()

        server_dir = storage._get_server_dir(server_id, server_name)
        print(f"Data saved to: {server_dir}/members/")

        return {
            "success": True,
            "sync_id": sync_id,
            "member_count": len(members),
            "new_members": len(new_member_ids),
            "departed_members": len(departed_member_ids),
            "duration_seconds": duration,
        }

    except GatewayClientError as e:
        print(f"\nError: {e}", file=sys.stderr)
        operation.status = "error"
        operation.error = str(e)
        storage.save_sync_operation(operation)
        return {"success": False, "error": str(e)}

    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        operation.status = "error"
        operation.error = str(e)
        storage.save_sync_operation(operation)
        raise

    finally:
        await fetcher.close()


async def _process_churned_members(
    departed_ids: set[str],
    sync_id: str,
    detected_at: datetime,
    server_id: str,
    server_name: str,
    storage
) -> None:
    """Process and save churned member records."""
    # Load previous member data to get details
    previous_list = storage.load_current_members(server_id)
    if not previous_list:
        return

    previous_members = {m.user_id: m for m in previous_list.members}

    for user_id in departed_ids:
        member = previous_members.get(user_id)
        if not member:
            continue

        # Calculate tenure
        tenure_days = 0
        if member.joined_at:
            tenure_days = (detected_at - member.joined_at).days

        churned = ChurnedMember(
            user_id=member.user_id,
            username=member.username,
            display_name=member.display_name,
            joined_at=member.joined_at,
            departure_detected_at=detected_at,
            departure_detected_sync=sync_id,
            tenure_days=tenure_days,
            activity=None,  # Will be populated later if message data available
            roles_at_departure=member.roles,
            profile_snapshot=None,  # Will be populated if profile exists
        )

        storage.save_churned_member(churned, server_id, server_name)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sync Discord server member list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Sync members from a server
    python member_sync.py --server 1234567890

    # Include bot accounts
    python member_sync.py --server 1234567890 --include-bots

    # Sync and enrich profiles
    python member_sync.py --server 1234567890 --enrich-profiles
        """
    )

    parser.add_argument(
        "--server",
        required=True,
        help="Discord server ID to sync"
    )
    parser.add_argument(
        "--include-bots",
        action="store_true",
        help="Include bot accounts in the sync"
    )
    parser.add_argument(
        "--enrich-profiles",
        action="store_true",
        help="Update unified profiles with Discord data"
    )
    parser.add_argument(
        "--create-profiles",
        action="store_true",
        help="Create new profiles for members (requires --enrich-profiles)"
    )
    parser.add_argument(
        "--data-dir",
        default="./data",
        help="Base data directory (default: ./data)"
    )

    args = parser.parse_args()

    # Validate args
    if args.create_profiles and not args.enrich_profiles:
        print("Error: --create-profiles requires --enrich-profiles", file=sys.stderr)
        sys.exit(1)

    # Run sync
    try:
        result = asyncio.run(sync_members(
            server_id=args.server,
            include_bots=args.include_bots,
            enrich_profiles=args.enrich_profiles,
            create_profiles=args.create_profiles,
            data_dir=args.data_dir,
        ))

        if not result.get("success"):
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nSync cancelled.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

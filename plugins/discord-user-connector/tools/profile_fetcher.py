#!/usr/bin/env python3
"""
Discord profile fetcher tool.

Fetch and display member profiles with rich data (bio, connected accounts).

Usage:
    python profile_fetcher.py --user USER_ID --server SERVER_ID
    python profile_fetcher.py --user USER_ID --server SERVER_ID --unified
    python profile_fetcher.py --server SERVER_ID --sample 50
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.member_storage import get_member_storage
from lib.profile_index import get_profile_manager
from lib.gateway_client import RichProfileFetcher, GatewayClientError
from lib.profile_models import (
    UnifiedMemberProfile,
    ServerMembership,
)
from lib.member_models import ConnectedAccount


def print_profile(profile: UnifiedMemberProfile, unified: bool = False) -> None:
    """Pretty print a member profile."""
    print(f"Profile: {profile.display_name} (@{profile.username})")
    print()

    print("=" * 3 + " Discord Data " + "=" * 3)
    print(f"User ID:      {profile.user_id}")

    # Membership info
    if profile.discord_data.servers:
        for server in profile.discord_data.servers:
            if server.joined_at:
                days_ago = (datetime.now(timezone.utc) - server.joined_at).days
                print(f"Joined:       {server.joined_at.strftime('%Y-%m-%d')} ({days_ago} days ago)")
            if server.roles:
                roles_str = ", ".join(server.roles[:5])
                if len(server.roles) > 5:
                    roles_str += f" (+{len(server.roles) - 5} more)"
                print(f"Roles:        {roles_str}")

    # Rich profile data
    if profile.discord_data.bio:
        print(f"Bio:          \"{profile.discord_data.bio}\"")
    if profile.discord_data.pronouns:
        print(f"Pronouns:     {profile.discord_data.pronouns}")
    print()

    # Connected accounts
    if profile.discord_data.connected_accounts:
        print("Connected Accounts:")
        for ca in profile.discord_data.connected_accounts:
            verified = "+" if ca.verified else ""
            print(f"  * {ca.platform.title()}: {ca.name} {verified}")
        print()

    # Badges
    if profile.discord_data.badges:
        print(f"Badges:       {', '.join(profile.discord_data.badges)}")
        print()

    if unified:
        print("=" * 3 + " Behavioral Observations " + "=" * 3)

        if profile.behavioral_data.keywords:
            print(f"Keywords:     {', '.join(profile.behavioral_data.keywords)}")
        if profile.behavioral_data.notes:
            print(f"Notes:        {profile.behavioral_data.notes}")
        print()

        if profile.behavioral_data.observations:
            print("Recent Observations:")
            for obs in profile.behavioral_data.observations[-5:]:
                date_str = obs.timestamp.strftime("%Y-%m-%d")
                print(f"  [{date_str}] {obs.content}")
            print()

        print("=" * 3 + " Derived Insights " + "=" * 3)
        print(f"Engagement:   {profile.derived_insights.engagement_tier.value.title()}")
        print(f"Value Score:  {profile.derived_insights.member_value_score}/100")

        if profile.derived_insights.inferred_interests:
            interests = [ii.interest for ii in profile.derived_insights.inferred_interests[:5]]
            print(f"Interests:    {', '.join(interests)}")

        if profile.derived_insights.expertise_tags:
            print(f"Expertise:    {', '.join(profile.derived_insights.expertise_tags)}")


async def cmd_single_profile(args) -> int:
    """View a single member profile."""
    storage = get_member_storage(args.data_dir)
    profile_manager = get_profile_manager(args.data_dir)

    # Try to load from profile store first
    profile = profile_manager.load_profile(args.user)

    if profile:
        if args.format == "json":
            print(json.dumps(profile.to_dict(), indent=2))
        elif args.format == "yaml":
            import yaml
            print(yaml.safe_dump(profile.to_dict(), default_flow_style=False))
        else:
            print_profile(profile, unified=args.unified)
        return 0

    # No stored profile, try to fetch from current members
    current = storage.load_current_members(args.server)
    if not current:
        print(f"Error: No synced data for server {args.server}", file=sys.stderr)
        return 1

    # Find member in current list
    member = None
    for m in current.members:
        if m.user_id == args.user:
            member = m
            break

    if not member:
        print(f"Error: Member {args.user} not found in server {args.server}", file=sys.stderr)
        return 1

    # Create basic profile from member data
    profile = UnifiedMemberProfile(
        user_id=member.user_id,
        username=member.username,
        display_name=member.display_name,
        discriminator=member.discriminator,
        avatar_url=member.avatar_url,
    )

    # Add server membership
    profile.discord_data.servers.append(ServerMembership(
        server_id=args.server,
        server_name=current.server_name,
        joined_at=member.joined_at,
        roles=member.roles,
        nickname=member.nickname,
    ))

    profile.discord_data.is_bot = member.is_bot
    profile.discord_data.account_created_at = member.account_created_at

    # Try to fetch rich profile data
    if not args.no_fetch:
        try:
            print("Fetching rich profile data...", file=sys.stderr)
            fetcher = RichProfileFetcher()
            rich_data = await fetcher.fetch_user_profile(args.user, args.server)
            await fetcher.close()

            if rich_data:
                profile.discord_data.bio = rich_data.get("bio")
                profile.discord_data.pronouns = rich_data.get("pronouns")
                profile.discord_data.badges = rich_data.get("badges", [])

                for ca_data in rich_data.get("connected_accounts", []):
                    profile.discord_data.connected_accounts.append(
                        ConnectedAccount(
                            platform=ca_data.get("platform", "unknown"),
                            name=ca_data.get("name", ""),
                            verified=ca_data.get("verified", False),
                        )
                    )

                profile.discord_data.sync_source = "user_token"

        except GatewayClientError as e:
            print(f"Warning: Could not fetch rich profile: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error fetching profile: {e}", file=sys.stderr)

    # Compute insights
    profile.compute_insights()

    if args.format == "json":
        print(json.dumps(profile.to_dict(), indent=2))
    elif args.format == "yaml":
        import yaml
        print(yaml.safe_dump(profile.to_dict(), default_flow_style=False))
    else:
        print_profile(profile, unified=args.unified)

    return 0


async def cmd_batch_profiles(args) -> int:
    """Fetch rich profiles for multiple members."""
    storage = get_member_storage(args.data_dir)

    # Load current members
    current = storage.load_current_members(args.server)
    if not current:
        print(f"Error: No synced data for server {args.server}", file=sys.stderr)
        return 1

    # Get members to fetch
    members = [m for m in current.members if not m.is_bot]

    if args.missing_only:
        profile_manager = get_profile_manager(args.data_dir)
        existing_ids = set(profile_manager.list_profile_ids())
        members = [m for m in members if m.user_id not in existing_ids]

    if args.all:
        sample = members
    else:
        # Random sample
        import random
        sample_size = min(args.sample, len(members))
        sample = random.sample(members, sample_size)

    if not sample:
        print("No members to fetch profiles for.")
        return 0

    print(f"Fetching rich profiles from {current.server_name}...")
    print(f"Target: {len(sample)} members")
    print()

    # Fetch profiles
    fetcher = RichProfileFetcher()

    stats = {
        "fetched": 0,
        "with_bio": 0,
        "with_connected": 0,
        "failed": 0,
    }

    try:
        user_ids = [m.user_id for m in sample]

        def progress_callback(current_idx, total):
            pct = (current_idx / total) * 100
            bar_len = 40
            filled = int(bar_len * current_idx // total)
            bar = '=' * filled + '>' + ' ' * (bar_len - filled - 1)
            bar = bar[:bar_len]
            print(f"\r[{bar}] {current_idx}/{total} ({pct:.1f}%)", end='', flush=True)

        results = await fetcher.fetch_profiles_batch(
            user_ids,
            args.server,
            progress_callback=progress_callback,
            delay_between_requests=0.5,
        )

        print()  # New line after progress bar
        print()

        for user_id, profile_data in results.items():
            if profile_data:
                stats["fetched"] += 1
                if profile_data.get("bio"):
                    stats["with_bio"] += 1
                if profile_data.get("connected_accounts"):
                    stats["with_connected"] += 1
            else:
                stats["failed"] += 1

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    finally:
        await fetcher.close()

    # Print results
    print("Results:")
    print(f"- Fetched: {stats['fetched']}")
    print(f"- With bio: {stats['with_bio']} ({stats['with_bio']/stats['fetched']*100:.0f}%)" if stats['fetched'] > 0 else "- With bio: 0")
    print(f"- With connected accounts: {stats['with_connected']} ({stats['with_connected']/stats['fetched']*100:.0f}%)" if stats['fetched'] > 0 else "- With connected: 0")
    print(f"- Failed (rate limited): {stats['failed']}")
    print()
    print("Note: Rich profile data requires User Token. Using Bot Token only provides basic data.")

    return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch and display Discord member profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--server", required=True, help="Discord server ID")
    parser.add_argument("--user", help="User ID to view profile for")
    parser.add_argument("--unified", action="store_true", help="Include behavioral observations")
    parser.add_argument("--format", choices=["pretty", "json", "yaml"], default="pretty")
    parser.add_argument("--no-fetch", action="store_true", help="Don't fetch rich data from API")

    # Batch options
    parser.add_argument("--sample", type=int, default=50, help="Number of random members to fetch")
    parser.add_argument("--all", action="store_true", help="Fetch all members (slow)")
    parser.add_argument("--missing-only", action="store_true", help="Only fetch members without rich data")

    parser.add_argument("--data-dir", default="./data")

    args = parser.parse_args()

    if args.user:
        # Single profile
        return asyncio.run(cmd_single_profile(args))
    else:
        # Batch profiles
        return asyncio.run(cmd_batch_profiles(args))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Profile enricher for Discord member data.

Enriches unified member profiles with Discord API data while preserving
existing behavioral observations from 012-customer-profile-manager.

Usage:
    python profile_enricher.py --server SERVER_ID [--create-profiles] [--dry-run]
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.member_models import MemberBasic, MemberRichProfile
from lib.member_storage import get_member_storage
from lib.profile_models import (
    UnifiedMemberProfile,
    DiscordData,
    ServerMembership,
    BehavioralData,
)
from lib.profile_index import ProfileManager


# Static mapping: connected account platform → interest category
# Extended from spec.md table
PLATFORM_INTEREST_MAPPING = {
    "spotify": "music",
    "steam": "gaming",
    "xbox": "gaming",
    "playstation": "gaming",
    "twitch": "streaming",
    "youtube": "video",
    "twitter": "social",
    "tiktok": "social",
    "reddit": "community",
    "github": "coding",
    "battlenet": "gaming",
    "riotgames": "gaming",
    "epicgames": "gaming",
    "facebook": "social",
    "instagram": "photography",
    "crunchyroll": "anime",
    "roblox": "gaming",
}

# Role keywords → expertise tags mapping
ROLE_EXPERTISE_MAPPING = {
    "developer": "tech",
    "dev": "tech",
    "engineer": "tech",
    "programmer": "tech",
    "coder": "tech",
    "moderator": "community",
    "mod": "community",
    "admin": "community",
    "staff": "community",
    "designer": "design",
    "artist": "design",
    "creative": "design",
    "writer": "content",
    "content": "content",
    "creator": "content",
    "streamer": "media",
    "youtuber": "media",
}


class ProfileEnricher:
    """
    Enriches unified member profiles with Discord API data.

    Preserves existing behavioral_data while updating discord_data.
    """

    def __init__(self, data_dir: str = "."):
        """
        Initialize profile enricher.

        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)
        self.profile_manager = ProfileManager(data_dir)
        self.member_storage = get_member_storage(data_dir)

    def enrich_profiles_from_members(
        self,
        members: list[MemberBasic],
        server_id: str,
        server_name: str,
        rich_profiles: Optional[dict[str, MemberRichProfile]] = None,
        create_new: bool = False,
        message_counts: Optional[dict[str, int]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> dict:
        """
        Enrich unified profiles with member data from a sync.

        Args:
            members: List of MemberBasic from sync
            server_id: Discord server ID
            server_name: Discord server name
            rich_profiles: Optional dict of user_id → MemberRichProfile (from User Token)
            create_new: Whether to create new profiles for members without one
            message_counts: Optional dict of user_id → message count for engagement calculation
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Dict with stats: created, updated, skipped, failed
        """
        rich_profiles = rich_profiles or {}
        message_counts = message_counts or {}

        stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
        }

        total = len(members)
        profiles_to_save = []

        for i, member in enumerate(members):
            try:
                # Skip bots
                if member.is_bot:
                    stats["skipped"] += 1
                    continue

                # Check if profile exists
                existing_profile = self.profile_manager.load_profile(member.user_id)
                rich_profile = rich_profiles.get(member.user_id)
                message_count = message_counts.get(member.user_id, 0)

                if existing_profile:
                    # Update existing profile
                    profile = self._update_existing_profile(
                        existing_profile,
                        member,
                        server_id,
                        server_name,
                        rich_profile,
                        message_count,
                    )
                    profiles_to_save.append(profile)
                    stats["updated"] += 1
                elif create_new:
                    # Create new profile
                    profile = self._create_new_profile(
                        member,
                        server_id,
                        server_name,
                        rich_profile,
                        message_count,
                    )
                    profiles_to_save.append(profile)
                    stats["created"] += 1
                else:
                    stats["skipped"] += 1

                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception as e:
                stats["failed"] += 1
                print(f"Warning: Failed to enrich profile for {member.username}: {e}")

        # Batch save profiles
        if profiles_to_save:
            self.profile_manager.batch_update_profiles(profiles_to_save)

        return stats

    def _update_existing_profile(
        self,
        profile: UnifiedMemberProfile,
        member: MemberBasic,
        server_id: str,
        server_name: str,
        rich_profile: Optional[MemberRichProfile],
        message_count: int,
    ) -> UnifiedMemberProfile:
        """
        Update an existing profile with new Discord data.

        IMPORTANT: Preserves existing behavioral_data.

        Args:
            profile: Existing profile to update
            member: Current member data
            server_id: Server ID
            server_name: Server name
            rich_profile: Rich profile data (if available)
            message_count: Message count for engagement calculation

        Returns:
            Updated profile
        """
        # Update identity fields
        profile.username = member.username
        profile.display_name = member.display_name
        profile.discriminator = member.discriminator
        profile.avatar_url = member.avatar_url

        # Update or add server membership
        server_membership = ServerMembership(
            server_id=server_id,
            server_name=server_name,
            joined_at=member.joined_at,
            roles=member.roles,
            nickname=member.nickname,
            pending=member.pending,
        )

        # Find and update existing server entry, or add new one
        existing_server_idx = None
        for idx, s in enumerate(profile.discord_data.servers):
            if s.server_id == server_id:
                existing_server_idx = idx
                break

        if existing_server_idx is not None:
            profile.discord_data.servers[existing_server_idx] = server_membership
        else:
            profile.discord_data.servers.append(server_membership)

        # Update account metadata
        profile.discord_data.is_bot = member.is_bot
        profile.discord_data.account_created_at = member.account_created_at

        # Update rich profile data if available
        if rich_profile:
            profile.discord_data.bio = rich_profile.bio
            profile.discord_data.pronouns = rich_profile.pronouns
            profile.discord_data.badges = rich_profile.badges
            profile.discord_data.connected_accounts = rich_profile.connected_accounts
            profile.discord_data.sync_source = "user_token"
        else:
            profile.discord_data.sync_source = "bot_token"

        profile.discord_data.last_synced_at = datetime.now(timezone.utc)

        # Recompute derived insights (preserves behavioral_data)
        has_mod_role = self._has_moderator_role(member.roles)
        profile.compute_insights(message_count=message_count, has_moderator_role=has_mod_role)

        # behavioral_data is untouched - preserved automatically

        return profile

    def _create_new_profile(
        self,
        member: MemberBasic,
        server_id: str,
        server_name: str,
        rich_profile: Optional[MemberRichProfile],
        message_count: int,
    ) -> UnifiedMemberProfile:
        """
        Create a new unified profile from member data.

        Args:
            member: Member data
            server_id: Server ID
            server_name: Server name
            rich_profile: Rich profile data (if available)
            message_count: Message count for engagement calculation

        Returns:
            New profile
        """
        now = datetime.now(timezone.utc)

        # Build server membership
        server_membership = ServerMembership(
            server_id=server_id,
            server_name=server_name,
            joined_at=member.joined_at,
            roles=member.roles,
            nickname=member.nickname,
            pending=member.pending,
        )

        # Build connected accounts if rich profile available
        connected_accounts = []
        badges = []
        bio = None
        pronouns = None
        sync_source = "bot_token"

        if rich_profile:
            connected_accounts = rich_profile.connected_accounts
            badges = rich_profile.badges
            bio = rich_profile.bio
            pronouns = rich_profile.pronouns
            sync_source = "user_token"

        # Build discord_data
        discord_data = DiscordData(
            servers=[server_membership],
            is_bot=member.is_bot,
            account_created_at=member.account_created_at,
            badges=badges,
            bio=bio,
            pronouns=pronouns,
            connected_accounts=connected_accounts,
            last_synced_at=now,
            sync_source=sync_source,
        )

        # Create empty behavioral_data (will be populated by agent observations)
        behavioral_data = BehavioralData()

        # Create profile
        profile = UnifiedMemberProfile(
            user_id=member.user_id,
            username=member.username,
            display_name=member.display_name,
            discriminator=member.discriminator,
            avatar_url=member.avatar_url,
            discord_data=discord_data,
            behavioral_data=behavioral_data,
            created_at=now,
            updated_at=now,
        )

        # Compute derived insights
        has_mod_role = self._has_moderator_role(member.roles)
        profile.compute_insights(message_count=message_count, has_moderator_role=has_mod_role)

        return profile

    def _has_moderator_role(self, roles: list[str]) -> bool:
        """Check if member has a moderator-level role."""
        mod_keywords = ["moderator", "mod", "admin", "staff", "owner"]
        for role in roles:
            role_lower = role.lower()
            if any(kw in role_lower for kw in mod_keywords):
                return True
        return False

    def enrich_single_profile(
        self,
        user_id: str,
        server_id: str,
        message_count: int = 0,
    ) -> Optional[UnifiedMemberProfile]:
        """
        Enrich a single profile by user ID.

        Looks up member data from the current member list and updates the profile.

        Args:
            user_id: Discord user ID
            server_id: Server ID to get member data from
            message_count: Optional message count

        Returns:
            Updated profile, or None if member not found
        """
        # Load current member list
        current_list = self.member_storage.load_current_members(server_id)
        if not current_list:
            return None

        # Find member
        member = None
        for m in current_list.members:
            if m.user_id == user_id:
                member = m
                break

        if not member:
            return None

        # Load or create profile
        profile = self.profile_manager.load_profile(user_id)

        if profile:
            profile = self._update_existing_profile(
                profile,
                member,
                server_id,
                current_list.server_name,
                None,  # No rich profile
                message_count,
            )
        else:
            profile = self._create_new_profile(
                member,
                server_id,
                current_list.server_name,
                None,  # No rich profile
                message_count,
            )

        self.profile_manager.save_profile(profile)
        return profile


def get_interest_from_platform(platform: str) -> Optional[str]:
    """Get inferred interest from platform type."""
    return PLATFORM_INTEREST_MAPPING.get(platform.lower())


def get_expertise_from_role(role: str) -> Optional[str]:
    """Get expertise tag from role name."""
    role_lower = role.lower()
    for keyword, expertise in ROLE_EXPERTISE_MAPPING.items():
        if keyword in role_lower:
            return expertise
    return None


def main():
    """CLI entry point for standalone profile enrichment."""
    parser = argparse.ArgumentParser(
        description="Enrich unified profiles with Discord member data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Enrich profiles for existing members
    python profile_enricher.py --server 1234567890

    # Create profiles for all members
    python profile_enricher.py --server 1234567890 --create-profiles

    # Dry run (show what would be done)
    python profile_enricher.py --server 1234567890 --dry-run
        """
    )

    parser.add_argument(
        "--server",
        required=True,
        help="Discord server ID"
    )
    parser.add_argument(
        "--create-profiles",
        action="store_true",
        help="Create new profiles for members without one"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Base data directory (default: current directory)"
    )

    args = parser.parse_args()

    enricher = ProfileEnricher(args.data_dir)
    storage = get_member_storage(args.data_dir)

    # Load current member list
    current_list = storage.load_current_members(args.server)
    if not current_list:
        print(f"Error: No member data found for server {args.server}")
        print("Run 'discord members sync' first to sync member data.")
        sys.exit(1)

    print(f"Enriching profiles for {current_list.server_name}...")
    print(f"Members to process: {len(current_list.members):,}")
    print()

    if args.dry_run:
        # Count existing profiles
        existing_ids = set(enricher.profile_manager.list_profile_ids())
        member_ids = {m.user_id for m in current_list.members if not m.is_bot}

        would_update = len(existing_ids & member_ids)
        would_create = len(member_ids - existing_ids) if args.create_profiles else 0
        would_skip = len(member_ids) - would_update - would_create

        print("Dry run results:")
        print(f"  Existing profiles: {len(existing_ids):,}")
        print(f"  Would update: {would_update:,}")
        print(f"  Would create: {would_create:,}")
        print(f"  Would skip: {would_skip:,}")
        return

    def progress(current: int, total: int) -> None:
        percent = (current / total) * 100
        print(f"\rEnriching... {current:,}/{total:,} ({percent:.1f}%)", end='', flush=True)

    stats = enricher.enrich_profiles_from_members(
        members=current_list.members,
        server_id=args.server,
        server_name=current_list.server_name,
        create_new=args.create_profiles,
        progress_callback=progress,
    )

    print()
    print()
    print("Enrichment complete:")
    print(f"  Created: {stats['created']:,}")
    print(f"  Updated: {stats['updated']:,}")
    print(f"  Skipped: {stats['skipped']:,}")
    print(f"  Failed: {stats['failed']:,}")


if __name__ == "__main__":
    main()

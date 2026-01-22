"""
Data models for Discord member management.

Defines dataclasses for member data, sync operations, and churn tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EngagementTier(Enum):
    """Member engagement level based on message count."""
    SILENT = "silent"          # 0 messages
    LURKER = "lurker"          # 1-4 messages
    OCCASIONAL = "occasional"  # 5-20 messages
    ACTIVE = "active"          # 21-100 messages
    CHAMPION = "champion"      # 100+ messages or moderator


@dataclass
class MemberBasic:
    """Basic member data from Gateway API (available with Bot Token)."""
    user_id: str
    username: str
    display_name: str
    discriminator: str = "0"
    avatar_url: Optional[str] = None
    joined_at: Optional[datetime] = None
    roles: list[str] = field(default_factory=list)
    nickname: Optional[str] = None
    pending: bool = False
    is_bot: bool = False
    account_created_at: Optional[datetime] = None

    @property
    def tenure_days(self) -> int:
        """Days since joining the server."""
        if not self.joined_at:
            return 0
        delta = datetime.now(self.joined_at.tzinfo) - self.joined_at
        return max(0, delta.days)

    @property
    def account_age_days(self) -> int:
        """Days since Discord account was created."""
        if not self.account_created_at:
            return 0
        delta = datetime.now(self.account_created_at.tzinfo) - self.account_created_at
        return max(0, delta.days)

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "discriminator": self.discriminator,
            "avatar_url": self.avatar_url,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "roles": self.roles,
            "nickname": self.nickname,
            "pending": self.pending,
            "is_bot": self.is_bot,
            "account_created_at": self.account_created_at.isoformat() if self.account_created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemberBasic":
        """Create from dictionary."""
        joined_at = None
        if data.get("joined_at"):
            joined_at = datetime.fromisoformat(data["joined_at"].replace("Z", "+00:00"))

        account_created_at = None
        if data.get("account_created_at"):
            account_created_at = datetime.fromisoformat(data["account_created_at"].replace("Z", "+00:00"))

        return cls(
            user_id=data["user_id"],
            username=data["username"],
            display_name=data.get("display_name", data["username"]),
            discriminator=data.get("discriminator", "0"),
            avatar_url=data.get("avatar_url"),
            joined_at=joined_at,
            roles=data.get("roles", []),
            nickname=data.get("nickname"),
            pending=data.get("pending", False),
            is_bot=data.get("is_bot", False),
            account_created_at=account_created_at,
        )


@dataclass
class ConnectedAccount:
    """External account linked to Discord profile."""
    platform: str  # spotify, steam, github, etc.
    name: str
    account_id: Optional[str] = None
    verified: bool = False

    @property
    def inferred_interest(self) -> Optional[str]:
        """Infer interest category from platform type."""
        mapping = {
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
        return mapping.get(self.platform.lower())

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "name": self.name,
            "account_id": self.account_id,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConnectedAccount":
        return cls(
            platform=data["platform"],
            name=data["name"],
            account_id=data.get("account_id"),
            verified=data.get("verified", False),
        )


@dataclass
class MemberRichProfile:
    """Rich profile data (requires User Token)."""
    bio: Optional[str] = None
    pronouns: Optional[str] = None
    connected_accounts: list[ConnectedAccount] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "bio": self.bio,
            "pronouns": self.pronouns,
            "connected_accounts": [ca.to_dict() for ca in self.connected_accounts],
            "badges": self.badges,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemberRichProfile":
        connected_accounts = [
            ConnectedAccount.from_dict(ca) for ca in data.get("connected_accounts", [])
        ]
        return cls(
            bio=data.get("bio"),
            pronouns=data.get("pronouns"),
            connected_accounts=connected_accounts,
            badges=data.get("badges", []),
        )


@dataclass
class MemberActivity:
    """Aggregated engagement data for a member."""
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    channels_active: list[str] = field(default_factory=list)
    reaction_count: int = 0

    @property
    def engagement_tier(self) -> EngagementTier:
        """Calculate engagement tier from message count."""
        if self.message_count == 0:
            return EngagementTier.SILENT
        elif self.message_count <= 4:
            return EngagementTier.LURKER
        elif self.message_count <= 20:
            return EngagementTier.OCCASIONAL
        elif self.message_count <= 100:
            return EngagementTier.ACTIVE
        else:
            return EngagementTier.CHAMPION

    def to_dict(self) -> dict:
        return {
            "message_count": self.message_count,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "channels_active": self.channels_active,
            "reaction_count": self.reaction_count,
            "engagement_tier": self.engagement_tier.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemberActivity":
        last_message_at = None
        if data.get("last_message_at"):
            last_message_at = datetime.fromisoformat(data["last_message_at"].replace("Z", "+00:00"))

        return cls(
            message_count=data.get("message_count", 0),
            last_message_at=last_message_at,
            channels_active=data.get("channels_active", []),
            reaction_count=data.get("reaction_count", 0),
        )


@dataclass
class MemberSnapshot:
    """Historical snapshot of member list at a point in time."""
    sync_id: str  # Format: YYYYMMDD_HHMMSS
    server_id: str
    timestamp: datetime
    member_count: int
    member_ids: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sync_id": self.sync_id,
            "server_id": self.server_id,
            "timestamp": self.timestamp.isoformat(),
            "member_count": self.member_count,
            "member_ids": self.member_ids,
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemberSnapshot":
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        return cls(
            sync_id=data["sync_id"],
            server_id=data["server_id"],
            timestamp=timestamp,
            member_count=data["member_count"],
            member_ids=data.get("member_ids", []),
            stats=data.get("stats", {}),
        )


@dataclass
class CurrentMemberList:
    """Full member data from latest sync."""
    sync_id: str
    server_id: str
    server_name: str
    timestamp: datetime
    member_count: int
    members: list[MemberBasic] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sync_id": self.sync_id,
            "server_id": self.server_id,
            "server_name": self.server_name,
            "timestamp": self.timestamp.isoformat(),
            "member_count": self.member_count,
            "members": [m.to_dict() for m in self.members],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CurrentMemberList":
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        members = [MemberBasic.from_dict(m) for m in data.get("members", [])]
        return cls(
            sync_id=data["sync_id"],
            server_id=data["server_id"],
            server_name=data["server_name"],
            timestamp=timestamp,
            member_count=data["member_count"],
            members=members,
        )


@dataclass
class ChurnedMember:
    """Record of a member who left the server."""
    user_id: str
    username: str
    display_name: str
    joined_at: Optional[datetime] = None
    departure_detected_at: Optional[datetime] = None
    departure_detected_sync: Optional[str] = None
    tenure_days: int = 0
    activity: Optional[MemberActivity] = None
    roles_at_departure: list[str] = field(default_factory=list)
    profile_snapshot: Optional[dict] = None

    @property
    def was_active(self) -> bool:
        """True if member ever posted a message."""
        if self.activity:
            return self.activity.message_count > 0
        return False

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "departure_detected_at": self.departure_detected_at.isoformat() if self.departure_detected_at else None,
            "departure_detected_sync": self.departure_detected_sync,
            "tenure_days": self.tenure_days,
            "activity": self.activity.to_dict() if self.activity else None,
            "roles_at_departure": self.roles_at_departure,
            "profile_snapshot": self.profile_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChurnedMember":
        joined_at = None
        if data.get("joined_at"):
            joined_at = datetime.fromisoformat(data["joined_at"].replace("Z", "+00:00"))

        departure_detected_at = None
        if data.get("departure_detected_at"):
            departure_detected_at = datetime.fromisoformat(data["departure_detected_at"].replace("Z", "+00:00"))

        activity = None
        if data.get("activity"):
            activity = MemberActivity.from_dict(data["activity"])

        return cls(
            user_id=data["user_id"],
            username=data["username"],
            display_name=data.get("display_name", data["username"]),
            joined_at=joined_at,
            departure_detected_at=departure_detected_at,
            departure_detected_sync=data.get("departure_detected_sync"),
            tenure_days=data.get("tenure_days", 0),
            activity=activity,
            roles_at_departure=data.get("roles_at_departure", []),
            profile_snapshot=data.get("profile_snapshot"),
        )


@dataclass
class SyncOperation:
    """Record of a member sync operation."""
    sync_id: str
    server_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0
    member_count: int = 0
    new_members_count: int = 0
    departed_members_count: int = 0
    profiles_created: int = 0
    profiles_updated: int = 0
    profiles_skipped: int = 0
    sync_source: str = "bot_token"
    status: str = "in_progress"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "sync_id": self.sync_id,
            "server_id": self.server_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "member_count": self.member_count,
            "new_members_count": self.new_members_count,
            "departed_members_count": self.departed_members_count,
            "profiles_created": self.profiles_created,
            "profiles_updated": self.profiles_updated,
            "profiles_skipped": self.profiles_skipped,
            "sync_source": self.sync_source,
            "status": self.status,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SyncOperation":
        started_at = datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))
        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"].replace("Z", "+00:00"))

        return cls(
            sync_id=data["sync_id"],
            server_id=data["server_id"],
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=data.get("duration_seconds", 0),
            member_count=data.get("member_count", 0),
            new_members_count=data.get("new_members_count", 0),
            departed_members_count=data.get("departed_members_count", 0),
            profiles_created=data.get("profiles_created", 0),
            profiles_updated=data.get("profiles_updated", 0),
            profiles_skipped=data.get("profiles_skipped", 0),
            sync_source=data.get("sync_source", "bot_token"),
            status=data.get("status", "unknown"),
            error=data.get("error"),
        )


@dataclass
class ServerMetadata:
    """Server information for display and slug updates."""
    server_id: str
    name: str
    slug: str
    icon_url: Optional[str] = None
    first_synced_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    sync_count: int = 0
    name_history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "server_id": self.server_id,
            "name": self.name,
            "slug": self.slug,
            "icon_url": self.icon_url,
            "first_synced_at": self.first_synced_at.isoformat() if self.first_synced_at else None,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "sync_count": self.sync_count,
            "name_history": self.name_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ServerMetadata":
        first_synced_at = None
        if data.get("first_synced_at"):
            first_synced_at = datetime.fromisoformat(data["first_synced_at"].replace("Z", "+00:00"))

        last_synced_at = None
        if data.get("last_synced_at"):
            last_synced_at = datetime.fromisoformat(data["last_synced_at"].replace("Z", "+00:00"))

        return cls(
            server_id=data["server_id"],
            name=data["name"],
            slug=data["slug"],
            icon_url=data.get("icon_url"),
            first_synced_at=first_synced_at,
            last_synced_at=last_synced_at,
            sync_count=data.get("sync_count", 0),
            name_history=data.get("name_history", []),
        )

"""
Data models for unified member profiles.

Integrates Discord API data with behavioral observations from 012-customer-profile-manager.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .member_models import ConnectedAccount, EngagementTier


@dataclass
class Observation:
    """A timestamped observation about a member."""
    timestamp: datetime
    source: str  # "chat", "manual", "system"
    content: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Observation":
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        return cls(
            timestamp=timestamp,
            source=data["source"],
            content=data["content"],
        )


@dataclass
class ServerMembership:
    """Membership info for a specific server."""
    server_id: str
    server_name: str
    joined_at: Optional[datetime] = None
    roles: list[str] = field(default_factory=list)
    nickname: Optional[str] = None
    pending: bool = False

    def to_dict(self) -> dict:
        return {
            "server_id": self.server_id,
            "server_name": self.server_name,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "roles": self.roles,
            "nickname": self.nickname,
            "pending": self.pending,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ServerMembership":
        joined_at = None
        if data.get("joined_at"):
            joined_at = datetime.fromisoformat(data["joined_at"].replace("Z", "+00:00"))

        return cls(
            server_id=data["server_id"],
            server_name=data["server_name"],
            joined_at=joined_at,
            roles=data.get("roles", []),
            nickname=data.get("nickname"),
            pending=data.get("pending", False),
        )


@dataclass
class DiscordData:
    """Discord API data that is auto-synced."""
    servers: list[ServerMembership] = field(default_factory=list)
    is_bot: bool = False
    account_created_at: Optional[datetime] = None
    badges: list[str] = field(default_factory=list)
    bio: Optional[str] = None
    pronouns: Optional[str] = None
    connected_accounts: list[ConnectedAccount] = field(default_factory=list)
    last_synced_at: Optional[datetime] = None
    sync_source: str = "bot_token"  # "bot_token" or "user_token"

    def to_dict(self) -> dict:
        return {
            "servers": [s.to_dict() for s in self.servers],
            "is_bot": self.is_bot,
            "account_created_at": self.account_created_at.isoformat() if self.account_created_at else None,
            "badges": self.badges,
            "bio": self.bio,
            "pronouns": self.pronouns,
            "connected_accounts": [ca.to_dict() for ca in self.connected_accounts],
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "sync_source": self.sync_source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscordData":
        servers = [ServerMembership.from_dict(s) for s in data.get("servers", [])]
        connected_accounts = [ConnectedAccount.from_dict(ca) for ca in data.get("connected_accounts", [])]

        account_created_at = None
        if data.get("account_created_at"):
            account_created_at = datetime.fromisoformat(data["account_created_at"].replace("Z", "+00:00"))

        last_synced_at = None
        if data.get("last_synced_at"):
            last_synced_at = datetime.fromisoformat(data["last_synced_at"].replace("Z", "+00:00"))

        return cls(
            servers=servers,
            is_bot=data.get("is_bot", False),
            account_created_at=account_created_at,
            badges=data.get("badges", []),
            bio=data.get("bio"),
            pronouns=data.get("pronouns"),
            connected_accounts=connected_accounts,
            last_synced_at=last_synced_at,
            sync_source=data.get("sync_source", "bot_token"),
        )


@dataclass
class BehavioralData:
    """Behavioral observations from 012-customer-profile-manager."""
    observations: list[Observation] = field(default_factory=list)  # Max 50
    keywords: list[str] = field(default_factory=list)  # Max 10
    notes: Optional[str] = None
    topics_discussed: list[str] = field(default_factory=list)
    interaction_count: int = 0
    last_interaction_at: Optional[datetime] = None

    def add_observation(self, source: str, content: str) -> None:
        """Add observation, maintaining max 50 limit (oldest removed first)."""
        obs = Observation(
            timestamp=datetime.now(),
            source=source,
            content=content,
        )
        self.observations.append(obs)
        # Keep only the most recent 50
        if len(self.observations) > 50:
            self.observations = self.observations[-50:]

    def add_keyword(self, keyword: str) -> None:
        """Add keyword, maintaining max 10 limit."""
        if keyword not in self.keywords:
            self.keywords.append(keyword)
            # Keep only the most recent 10
            if len(self.keywords) > 10:
                self.keywords = self.keywords[-10:]

    def to_dict(self) -> dict:
        return {
            "observations": [o.to_dict() for o in self.observations],
            "keywords": self.keywords,
            "notes": self.notes,
            "topics_discussed": self.topics_discussed,
            "interaction_count": self.interaction_count,
            "last_interaction_at": self.last_interaction_at.isoformat() if self.last_interaction_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BehavioralData":
        observations = [Observation.from_dict(o) for o in data.get("observations", [])]

        last_interaction_at = None
        if data.get("last_interaction_at"):
            last_interaction_at = datetime.fromisoformat(data["last_interaction_at"].replace("Z", "+00:00"))

        return cls(
            observations=observations,
            keywords=data.get("keywords", []),
            notes=data.get("notes"),
            topics_discussed=data.get("topics_discussed", []),
            interaction_count=data.get("interaction_count", 0),
            last_interaction_at=last_interaction_at,
        )


@dataclass
class InferredInterest:
    """An inferred interest with its source."""
    interest: str
    source: str  # e.g., "connected_account:spotify", "keywords", "bio"

    def to_dict(self) -> dict:
        return {
            "interest": self.interest,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InferredInterest":
        return cls(
            interest=data["interest"],
            source=data["source"],
        )


@dataclass
class DerivedInsights:
    """Computed insights from combined Discord and behavioral data."""
    inferred_interests: list[InferredInterest] = field(default_factory=list)
    engagement_tier: EngagementTier = EngagementTier.SILENT
    member_value_score: int = 0  # 0-100
    expertise_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "inferred_interests": [ii.to_dict() for ii in self.inferred_interests],
            "engagement_tier": self.engagement_tier.value,
            "member_value_score": self.member_value_score,
            "expertise_tags": self.expertise_tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DerivedInsights":
        inferred_interests = [InferredInterest.from_dict(ii) for ii in data.get("inferred_interests", [])]
        engagement_tier = EngagementTier(data.get("engagement_tier", "silent"))

        return cls(
            inferred_interests=inferred_interests,
            engagement_tier=engagement_tier,
            member_value_score=data.get("member_value_score", 0),
            expertise_tags=data.get("expertise_tags", []),
        )


@dataclass
class UnifiedMemberProfile:
    """
    Unified profile combining Discord API data and behavioral observations.

    Storage: profiles/discord/{user_id}_{slug}.yaml
    """
    # Identity (from Discord API)
    user_id: str
    username: str
    display_name: str
    discriminator: str = "0"
    avatar_url: Optional[str] = None

    # Discord data (auto-synced)
    discord_data: DiscordData = field(default_factory=DiscordData)

    # Behavioral data (from 012-customer-profile)
    behavioral_data: BehavioralData = field(default_factory=BehavioralData)

    # Derived insights (computed)
    derived_insights: DerivedInsights = field(default_factory=DerivedInsights)

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def compute_insights(self, message_count: int = 0, has_moderator_role: bool = False) -> None:
        """Recompute derived insights from current data."""
        # Infer interests from connected accounts
        interests: list[InferredInterest] = []
        for ca in self.discord_data.connected_accounts:
            if ca.inferred_interest:
                interests.append(InferredInterest(
                    interest=ca.inferred_interest,
                    source=f"connected_account:{ca.platform}",
                ))

        # Add interests from keywords
        for keyword in self.behavioral_data.keywords:
            interests.append(InferredInterest(
                interest=keyword,
                source="keywords",
            ))

        self.derived_insights.inferred_interests = interests

        # Calculate engagement tier
        if has_moderator_role or message_count > 100:
            self.derived_insights.engagement_tier = EngagementTier.CHAMPION
        elif message_count > 20:
            self.derived_insights.engagement_tier = EngagementTier.ACTIVE
        elif message_count > 4:
            self.derived_insights.engagement_tier = EngagementTier.OCCASIONAL
        elif message_count > 0:
            self.derived_insights.engagement_tier = EngagementTier.LURKER
        else:
            self.derived_insights.engagement_tier = EngagementTier.SILENT

        # Calculate member value score
        score = 0

        # Tenure score (30 points max)
        if self.discord_data.servers:
            oldest_join = min(
                (s.joined_at for s in self.discord_data.servers if s.joined_at),
                default=None
            )
            if oldest_join:
                tenure_days = (datetime.now(oldest_join.tzinfo) - oldest_join).days
                tenure_score = min(30, (tenure_days / 365) * 30)
                score += tenure_score

        # Activity score (40 points max)
        activity_score = min(40, (message_count / 100) * 40)
        score += activity_score

        # Role score (30 points max)
        role_score = 0
        for server in self.discord_data.servers:
            if any(r.lower() in ["moderator", "mod", "admin", "staff"] for r in server.roles):
                role_score = max(role_score, 30)
            elif any(r.lower() in ["contributor", "helper", "vip"] for r in server.roles):
                role_score = max(role_score, 20)
            elif any(r.lower() not in ["member", "@everyone"] for r in server.roles):
                role_score = max(role_score, 10)
        score += role_score

        self.derived_insights.member_value_score = int(score)

        # Expertise tags from roles
        expertise_tags = set()
        role_expertise_mapping = {
            "developer": "tech",
            "dev": "tech",
            "engineer": "tech",
            "moderator": "community",
            "mod": "community",
            "admin": "community",
            "designer": "design",
            "artist": "design",
            "writer": "content",
            "content": "content",
        }
        for server in self.discord_data.servers:
            for role in server.roles:
                role_lower = role.lower()
                for keyword, tag in role_expertise_mapping.items():
                    if keyword in role_lower:
                        expertise_tags.add(tag)

        self.derived_insights.expertise_tags = list(expertise_tags)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "discriminator": self.discriminator,
            "avatar_url": self.avatar_url,
            "discord_data": self.discord_data.to_dict(),
            "behavioral_data": self.behavioral_data.to_dict(),
            "derived_insights": self.derived_insights.to_dict(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedMemberProfile":
        discord_data = DiscordData.from_dict(data.get("discord_data", {}))
        behavioral_data = BehavioralData.from_dict(data.get("behavioral_data", {}))
        derived_insights = DerivedInsights.from_dict(data.get("derived_insights", {}))

        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))

        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))

        return cls(
            user_id=data["user_id"],
            username=data["username"],
            display_name=data.get("display_name", data["username"]),
            discriminator=data.get("discriminator", "0"),
            avatar_url=data.get("avatar_url"),
            discord_data=discord_data,
            behavioral_data=behavioral_data,
            derived_insights=derived_insights,
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass
class ProfileIndex:
    """
    Index for fast lookup from user_id to profile filename.

    Storage: profiles/discord/index.yaml
    """
    updated_at: Optional[datetime] = None
    profile_count: int = 0
    index: dict[str, str] = field(default_factory=dict)  # user_id -> filename

    def add_profile(self, user_id: str, filename: str) -> None:
        """Add or update a profile in the index."""
        self.index[user_id] = filename
        self.profile_count = len(self.index)
        self.updated_at = datetime.now()

    def remove_profile(self, user_id: str) -> None:
        """Remove a profile from the index."""
        if user_id in self.index:
            del self.index[user_id]
            self.profile_count = len(self.index)
            self.updated_at = datetime.now()

    def get_filename(self, user_id: str) -> Optional[str]:
        """Get filename for a user_id."""
        return self.index.get(user_id)

    def to_dict(self) -> dict:
        return {
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "profile_count": self.profile_count,
            "index": self.index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProfileIndex":
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))

        return cls(
            updated_at=updated_at,
            profile_count=data.get("profile_count", 0),
            index=data.get("index", {}),
        )

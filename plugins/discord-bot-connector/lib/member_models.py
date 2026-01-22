"""
Member data models for Discord Bot plugin.

Self-contained models - no dependencies on other plugins.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class MemberBasic:
    """Basic member information from Discord Gateway."""

    user_id: str
    username: str
    display_name: str
    discriminator: str
    avatar_url: Optional[str]
    joined_at: Optional[datetime]
    roles: list[str] = field(default_factory=list)
    nickname: Optional[str] = None
    pending: bool = False
    is_bot: bool = False
    account_created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
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
            joined_at = datetime.fromisoformat(data["joined_at"])

        account_created_at = None
        if data.get("account_created_at"):
            account_created_at = datetime.fromisoformat(data["account_created_at"])

        return cls(
            user_id=data["user_id"],
            username=data["username"],
            display_name=data["display_name"],
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
class MemberList:
    """Complete member list from a server."""

    server_id: str
    server_name: str
    synced_at: datetime
    member_count: int
    members: list[MemberBasic] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "server_id": self.server_id,
            "server_name": self.server_name,
            "synced_at": self.synced_at.isoformat(),
            "member_count": self.member_count,
            "members": [m.to_dict() for m in self.members],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemberList":
        """Create from dictionary."""
        return cls(
            server_id=data["server_id"],
            server_name=data["server_name"],
            synced_at=datetime.fromisoformat(data["synced_at"]),
            member_count=data["member_count"],
            members=[MemberBasic.from_dict(m) for m in data.get("members", [])],
        )

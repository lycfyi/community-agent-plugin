"""Discord User Sync library modules."""

from .config import Config, ConfigError, get_config, reload_config
from .discord_client import (
    AuthenticationError,
    DiscordClientError,
    DiscordUserClient
)
from .markdown_formatter import (
    format_attachment,
    format_channel_header,
    format_date_header,
    format_embed,
    format_message,
    format_messages_markdown,
    format_reactions,
    format_reply_indicator,
    group_messages_by_date
)
from .rate_limiter import RateLimiter
from .storage import Storage, StorageError, get_storage
from .global_rate_limiter import GlobalRateLimiter
from .batched_writer import BatchedWriter
from .multi_server_sync import MultiServerSyncOrchestrator, MultiServerSyncSummary
from .slugify import slugify, make_hybrid_name, parse_hybrid_name, extract_id_from_hybrid
from .member_models import (
    EngagementTier,
    MemberBasic,
    ConnectedAccount,
    MemberRichProfile,
    MemberActivity,
    MemberSnapshot,
    CurrentMemberList,
    ChurnedMember,
    SyncOperation,
    ServerMetadata,
)
from .profile_models import (
    Observation,
    ServerMembership,
    DiscordData,
    BehavioralData,
    InferredInterest,
    DerivedInsights,
    UnifiedMemberProfile,
    ProfileIndex,
)
from .member_storage import MemberStorage, MemberStorageError, get_member_storage
from .profile_index import ProfileManager, ProfileIndexError, get_profile_manager
from .gateway_client import GatewayMemberFetcher, RichProfileFetcher, GatewayClientError
from .fuzzy_search import (
    MatchField,
    MatchReason,
    SearchResult,
    SearchQuery,
    FuzzySearchEngine,
    search_members,
    search_basic_members,
)

__all__ = [
    # Config
    "Config",
    "ConfigError",
    "get_config",
    "reload_config",
    # Discord Client
    "AuthenticationError",
    "DiscordClientError",
    "DiscordUserClient",
    # Markdown Formatter
    "format_attachment",
    "format_channel_header",
    "format_date_header",
    "format_embed",
    "format_message",
    "format_messages_markdown",
    "format_reactions",
    "format_reply_indicator",
    "group_messages_by_date",
    # Rate Limiter
    "RateLimiter",
    "GlobalRateLimiter",
    # Storage
    "Storage",
    "StorageError",
    "get_storage",
    # Batched Writer
    "BatchedWriter",
    # Multi-Server Sync
    "MultiServerSyncOrchestrator",
    "MultiServerSyncSummary",
    # Slugify
    "slugify",
    "make_hybrid_name",
    "parse_hybrid_name",
    "extract_id_from_hybrid",
    # Member Models
    "EngagementTier",
    "MemberBasic",
    "ConnectedAccount",
    "MemberRichProfile",
    "MemberActivity",
    "MemberSnapshot",
    "CurrentMemberList",
    "ChurnedMember",
    "SyncOperation",
    "ServerMetadata",
    # Profile Models
    "Observation",
    "ServerMembership",
    "DiscordData",
    "BehavioralData",
    "InferredInterest",
    "DerivedInsights",
    "UnifiedMemberProfile",
    "ProfileIndex",
    # Member Storage
    "MemberStorage",
    "MemberStorageError",
    "get_member_storage",
    # Profile Index
    "ProfileManager",
    "ProfileIndexError",
    "get_profile_manager",
    # Gateway Client
    "GatewayMemberFetcher",
    "RichProfileFetcher",
    "GatewayClientError",
    # Fuzzy Search
    "MatchField",
    "MatchReason",
    "SearchResult",
    "SearchQuery",
    "FuzzySearchEngine",
    "search_members",
    "search_basic_members",
]

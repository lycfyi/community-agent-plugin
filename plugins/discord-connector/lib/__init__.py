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
]

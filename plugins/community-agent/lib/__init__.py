"""Community Agent core library.

Shared utilities for all community agent plugins (Discord, Telegram, etc).
"""

from .config import (
    CommunityConfig,
    ConfigError,
    get_config,
    reload_config,
    DEFAULT_CONFIG,
)
from .storage_base import (
    StorageError,
    ensure_dir,
    sanitize_name,
    slugify,
    parse_last_n_messages,
    search_message_blocks,
)
from .markdown_base import (
    format_reply_indicator,
    format_date_header,
    group_messages_by_date,
    format_size_bytes,
)
from .rate_limiter_base import (
    format_duration,
    estimate_sync_time,
)

__all__ = [
    # Config
    "CommunityConfig",
    "ConfigError",
    "get_config",
    "reload_config",
    "DEFAULT_CONFIG",
    # Storage
    "StorageError",
    "ensure_dir",
    "sanitize_name",
    "slugify",
    "parse_last_n_messages",
    "search_message_blocks",
    # Markdown
    "format_reply_indicator",
    "format_date_header",
    "group_messages_by_date",
    "format_size_bytes",
    # Rate limiter
    "format_duration",
    "estimate_sync_time",
]

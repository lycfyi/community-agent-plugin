"""Community Agent core library.

Shared utilities for all community agent plugins (Discord, Telegram, etc).
"""

from .config import (
    CommunityConfig,
    ConfigError,
    SetupError,
    SetupState,
    get_config,
    reload_config,
    is_first_run,
    get_setup_state,
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
from .profile import (
    UserProfile,
    load_profile,
    ensure_profile,
    get_profile,
    PROFILE_TEMPLATE,
)

__all__ = [
    # Config
    "CommunityConfig",
    "ConfigError",
    "SetupError",
    "SetupState",
    "get_config",
    "reload_config",
    "is_first_run",
    "get_setup_state",
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
    # Profile
    "UserProfile",
    "load_profile",
    "ensure_profile",
    "get_profile",
    "PROFILE_TEMPLATE",
]

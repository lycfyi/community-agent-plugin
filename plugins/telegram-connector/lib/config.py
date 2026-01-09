"""Configuration loader for Telegram Agent.

Uses shared config from the plugin's community_agent/ symlink (points to ../community-agent).
When installed, Claude Code follows symlinks during copy, ensuring shared code is included.

Import Strategy:
- Tools add the plugin root to sys.path before importing lib.config
- This allows us to import from community_agent.lib.config directly
"""

from pathlib import Path
from typing import Optional

# Import from community-agent library via symlink
from community_agent.lib.config import (
    CommunityConfig,
    ConfigError,
    get_config as get_community_config,
    reload_config as reload_community_config,
)


class Config:
    """Telegram-specific configuration wrapper.

    Wraps CommunityConfig to provide backwards-compatible interface
    for Telegram agent tools.
    """

    def __init__(self):
        """Initialize by loading shared config."""
        self._community_config = get_community_config()

    @property
    def api_id(self) -> int:
        """Get Telegram API ID from environment."""
        return self._community_config.telegram_api_id

    @property
    def api_hash(self) -> str:
        """Get Telegram API hash from environment."""
        return self._community_config.telegram_api_hash

    @property
    def session_string(self) -> str:
        """Get Telegram session string from environment."""
        return self._community_config.telegram_session_string

    @property
    def default_group_id(self) -> Optional[int]:
        """Get default group ID from config (optional)."""
        return self._community_config.telegram_default_group_id

    @property
    def default_group_name(self) -> Optional[str]:
        """Get default group name from config (optional)."""
        return self._community_config.telegram_default_group_name

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return self._community_config.data_dir

    @property
    def retention_days(self) -> int:
        """Get message retention days (default 7)."""
        return self._community_config.telegram_retention_days

    @property
    def max_messages_per_group(self) -> int:
        """Get max messages to sync per group (default 2000)."""
        return self._community_config.telegram_max_messages_per_group

    @property
    def max_groups(self) -> int:
        """Get max groups to sync (default 10)."""
        return self._community_config.telegram_max_groups

    @property
    def rate_limit_min_interval_ms(self) -> int:
        """Get minimum interval between requests in ms (default 100)."""
        return self._community_config.telegram_rate_limit_min_interval_ms

    def set_default_group(self, group_id: int, group_name: str) -> None:
        """Set the default group for commands."""
        self._community_config.set_telegram_group(group_id, group_name)

    def save_config(self) -> None:
        """Save current configuration."""
        self._community_config.save_config()

    def get_group_data_dir(
        self, group_id: int, group_name: Optional[str] = None
    ) -> Path:
        """Get data directory for a specific group."""
        return self._community_config.get_telegram_group_data_dir(
            group_id, group_name
        )


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from files."""
    global _config
    reload_community_config()
    _config = Config()
    return _config


# Re-export ConfigError for backwards compatibility
__all__ = ["Config", "ConfigError", "get_config", "reload_config"]

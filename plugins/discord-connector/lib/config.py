"""Configuration loader for Discord Agent.

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
    """Discord-specific configuration wrapper.

    Wraps CommunityConfig to provide backwards-compatible interface
    for Discord agent tools.
    """

    def __init__(self):
        """Initialize by loading shared config."""
        self._community_config = get_community_config()

    @property
    def discord_token(self) -> str:
        """Get Discord user token from environment."""
        return self._community_config.discord_token

    @property
    def server_id(self) -> Optional[str]:
        """Get default server ID from config (optional)."""
        return self._community_config.discord_server_id

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return self._community_config.data_dir

    @property
    def retention_days(self) -> int:
        """Get message retention days (default 30)."""
        return self._community_config.discord_retention_days

    @property
    def profile(self) -> dict:
        """Get user profile settings."""
        # Profile is accessed directly from community config's discord section
        discord = self._community_config._config.get("discord", {})
        return discord.get("profile", {})

    @property
    def priority_servers(self) -> list:
        """Get priority servers list."""
        discord = self._community_config._config.get("discord", {})
        return discord.get("priority_servers", [])

    @property
    def max_messages_per_channel(self) -> int:
        """Get max messages to sync per channel (default 500)."""
        return self._community_config.discord_max_messages_per_channel

    @property
    def max_channels_per_server(self) -> int:
        """Get max channels to sync per server (default 10)."""
        return self._community_config.discord_max_channels_per_server

    @property
    def priority_channels(self) -> list:
        """Get list of priority channel names to sync first."""
        return self._community_config.discord_priority_channels

    @property
    def rate_limit_base_delay(self) -> float:
        """Get base delay between requests in seconds (default 1.0)."""
        return self._community_config.discord_rate_limit_base_delay

    @property
    def rate_limit_max_delay(self) -> float:
        """Get max backoff delay in seconds (default 60.0)."""
        return self._community_config.discord_rate_limit_max_delay

    @property
    def parallel_channels(self) -> int:
        """Get max concurrent channels to sync (default 5)."""
        return self._community_config.discord_parallel_channels

    def get_server_data_dir(self, server_id: str) -> Path:
        """Get data directory for a specific server."""
        return self._community_config.get_discord_server_data_dir(server_id)

    def get_channel_data_dir(self, server_id: str, channel_name: str) -> Path:
        """Get data directory for a specific channel."""
        return self._community_config.get_discord_channel_data_dir(
            server_id, channel_name
        )

    def set_default_server(self, server_id: str, server_name: str) -> None:
        """Set the default server for commands."""
        self._community_config.set_discord_server(server_id, server_name)


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

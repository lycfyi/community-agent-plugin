"""Shared configuration loader for all community agents.

Loads from config/agents.yaml with platform-specific sections.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration error."""
    pass


DEFAULT_CONFIG = """# Community Agent Configuration
# Shared settings for all platform connectors

# Shared storage directory
data_dir: "./data"

# Discord settings
discord:
  retention_days: 30
  default_server_id: null
  sync_limits:
    max_messages_per_channel: 500
    max_channels_per_server: 10
    priority_channels:
      - general
      - announcements
  rate_limits:
    base_delay: 1.0
    max_delay: 60.0
    parallel_channels: 5

# Telegram settings
telegram:
  retention_days: 7
  default_group_id: null
  sync_limits:
    max_messages_per_group: 2000
    max_groups: 10
  rate_limits:
    min_interval_ms: 100
"""


class CommunityConfig:
    """Shared configuration for all community agents."""

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        env_file: Optional[Path] = None
    ):
        """Initialize configuration.

        Args:
            config_dir: Directory containing config files. Defaults to ./config
            env_file: Path to .env file. Defaults to ./.env
        """
        self._base_dir = Path.cwd()
        self._config_dir = config_dir or self._base_dir / "config"
        self._env_file = env_file or self._base_dir / ".env"

        # Load environment variables
        load_dotenv(self._env_file)

        # Load unified config
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load config from agents.yaml, creating with defaults if missing."""
        filepath = self._config_dir / "agents.yaml"

        if not filepath.exists():
            self._create_default_config(filepath)

        with open(filepath, "r") as f:
            return yaml.safe_load(f) or {}

    def _create_default_config(self, filepath: Path) -> None:
        """Create default agents.yaml."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(DEFAULT_CONFIG)
        print(f"Created default config at {filepath}")

    def save_config(self) -> None:
        """Save current configuration to agents.yaml."""
        filepath = self._config_dir / "agents.yaml"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            yaml.safe_dump(self._config, f, default_flow_style=False)

    # -------------------------------------------------------------------------
    # Shared properties
    # -------------------------------------------------------------------------

    @property
    def data_dir(self) -> Path:
        """Get shared data directory path."""
        data_dir = self._config.get("data_dir", "./data")
        path = Path(data_dir)
        if not path.is_absolute():
            path = self._base_dir / path
        return path

    # -------------------------------------------------------------------------
    # Discord properties
    # -------------------------------------------------------------------------

    @property
    def discord_token(self) -> str:
        """Get Discord user token from environment."""
        token = os.getenv("DISCORD_USER_TOKEN")
        if not token:
            raise ConfigError(
                "DISCORD_USER_TOKEN not set. "
                "Add it to .env file or set as environment variable."
            )
        return token

    @property
    def discord_server_id(self) -> Optional[str]:
        """Get default Discord server ID."""
        discord = self._config.get("discord", {})
        server_id = discord.get("default_server_id")
        return str(server_id) if server_id else None

    @property
    def discord_retention_days(self) -> int:
        """Get Discord message retention days (default 30)."""
        discord = self._config.get("discord", {})
        return int(discord.get("retention_days", 30))

    @property
    def discord_max_messages_per_channel(self) -> int:
        """Get max messages to sync per Discord channel (default 500)."""
        discord = self._config.get("discord", {})
        sync_limits = discord.get("sync_limits", {})
        return int(sync_limits.get("max_messages_per_channel", 500))

    @property
    def discord_max_channels_per_server(self) -> int:
        """Get max channels to sync per Discord server (default 10)."""
        discord = self._config.get("discord", {})
        sync_limits = discord.get("sync_limits", {})
        return int(sync_limits.get("max_channels_per_server", 10))

    @property
    def discord_priority_channels(self) -> list:
        """Get list of priority Discord channel names to sync first."""
        discord = self._config.get("discord", {})
        sync_limits = discord.get("sync_limits", {})
        return sync_limits.get("priority_channels", ["general", "announcements"])

    @property
    def discord_rate_limit_base_delay(self) -> float:
        """Get base delay between Discord requests in seconds (default 1.0)."""
        discord = self._config.get("discord", {})
        rate_limits = discord.get("rate_limits", {})
        return float(rate_limits.get("base_delay", 1.0))

    @property
    def discord_rate_limit_max_delay(self) -> float:
        """Get max backoff delay for Discord in seconds (default 60.0)."""
        discord = self._config.get("discord", {})
        rate_limits = discord.get("rate_limits", {})
        return float(rate_limits.get("max_delay", 60.0))

    @property
    def discord_parallel_channels(self) -> int:
        """Get max concurrent Discord channels to sync (default 5)."""
        discord = self._config.get("discord", {})
        rate_limits = discord.get("rate_limits", {})
        return int(rate_limits.get("parallel_channels", 5))

    def set_discord_server(self, server_id: str, server_name: str) -> None:
        """Set the default Discord server."""
        if "discord" not in self._config:
            self._config["discord"] = {}
        self._config["discord"]["default_server_id"] = server_id
        self._config["discord"]["default_server_name"] = server_name
        self.save_config()

    def get_discord_server_data_dir(self, server_id: str) -> Path:
        """Get data directory for a specific Discord server."""
        return self.data_dir / server_id

    def get_discord_channel_data_dir(self, server_id: str, channel_name: str) -> Path:
        """Get data directory for a specific Discord channel."""
        safe_name = self._sanitize_filename(channel_name)
        return self.get_discord_server_data_dir(server_id) / safe_name

    # -------------------------------------------------------------------------
    # Telegram properties
    # -------------------------------------------------------------------------

    @property
    def telegram_api_id(self) -> int:
        """Get Telegram API ID from environment."""
        api_id = os.getenv("TELEGRAM_API_ID")
        if not api_id:
            raise ConfigError(
                "TELEGRAM_API_ID not set. "
                "Get it from https://my.telegram.org/apps and add to .env file."
            )
        try:
            return int(api_id)
        except ValueError:
            raise ConfigError("TELEGRAM_API_ID must be a number.")

    @property
    def telegram_api_hash(self) -> str:
        """Get Telegram API hash from environment."""
        api_hash = os.getenv("TELEGRAM_API_HASH")
        if not api_hash:
            raise ConfigError(
                "TELEGRAM_API_HASH not set. "
                "Get it from https://my.telegram.org/apps and add to .env file."
            )
        return api_hash

    @property
    def telegram_session_string(self) -> str:
        """Get Telegram session string from environment."""
        session = os.getenv("TELEGRAM_SESSION")
        if not session:
            raise ConfigError(
                "TELEGRAM_SESSION not set. "
                "Generate it using scripts/generate_session.py and add to .env file."
            )
        return session

    @property
    def telegram_default_group_id(self) -> Optional[int]:
        """Get default Telegram group ID."""
        telegram = self._config.get("telegram", {})
        group_id = telegram.get("default_group_id")
        return int(group_id) if group_id else None

    @property
    def telegram_default_group_name(self) -> Optional[str]:
        """Get default Telegram group name."""
        telegram = self._config.get("telegram", {})
        return telegram.get("default_group_name")

    @property
    def telegram_retention_days(self) -> int:
        """Get Telegram message retention days (default 7)."""
        telegram = self._config.get("telegram", {})
        return int(telegram.get("retention_days", 7))

    @property
    def telegram_max_messages_per_group(self) -> int:
        """Get max messages to sync per Telegram group (default 2000)."""
        telegram = self._config.get("telegram", {})
        sync_limits = telegram.get("sync_limits", {})
        return int(sync_limits.get("max_messages_per_group", 2000))

    @property
    def telegram_max_groups(self) -> int:
        """Get max Telegram groups to sync (default 10)."""
        telegram = self._config.get("telegram", {})
        sync_limits = telegram.get("sync_limits", {})
        return int(sync_limits.get("max_groups", 10))

    @property
    def telegram_rate_limit_min_interval_ms(self) -> int:
        """Get minimum interval between Telegram requests in ms (default 100)."""
        telegram = self._config.get("telegram", {})
        rate_limits = telegram.get("rate_limits", {})
        return int(rate_limits.get("min_interval_ms", 100))

    def set_telegram_group(self, group_id: int, group_name: str) -> None:
        """Set the default Telegram group."""
        if "telegram" not in self._config:
            self._config["telegram"] = {}
        self._config["telegram"]["default_group_id"] = group_id
        self._config["telegram"]["default_group_name"] = group_name
        self.save_config()

    def get_telegram_group_data_dir(
        self, group_id: int, group_name: Optional[str] = None
    ) -> Path:
        """Get data directory for a specific Telegram group."""
        if group_name:
            slug = self._slugify(group_name)
            return self.data_dir / f"{group_id}-{slug}"
        return self.data_dir / str(group_id)

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for use as filename."""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")
        return name.lower().strip()

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a name to a URL-friendly slug."""
        import re
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = slug.strip('-')
        return slug[:50]


# Global config instance
_config: Optional[CommunityConfig] = None


def get_config() -> CommunityConfig:
    """Get global config instance."""
    global _config
    if _config is None:
        _config = CommunityConfig()
    return _config


def reload_config() -> CommunityConfig:
    """Reload configuration from files."""
    global _config
    _config = CommunityConfig()
    return _config

"""Configuration loader with .env and YAML support."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration error."""
    pass


class Config:
    """Application configuration loaded from .env and YAML files."""

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

        # Load server config
        self._server_config = self._load_yaml("server.yaml")

    def _load_yaml(self, filename: str) -> dict:
        """Load a YAML config file."""
        filepath = self._config_dir / filename
        if not filepath.exists():
            return {}
        with open(filepath, "r") as f:
            return yaml.safe_load(f) or {}

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
    def server_id(self) -> str:
        """Get default server ID from config."""
        server_id = self._server_config.get("server_id")
        if not server_id:
            raise ConfigError(
                "server_id not set in config/server.yaml. "
                "Run discord-list to find your server ID."
            )
        return str(server_id)

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        data_dir = self._server_config.get("data_dir", "./data")
        path = Path(data_dir)
        if not path.is_absolute():
            path = self._base_dir / path
        return path

    @property
    def retention_days(self) -> int:
        """Get message retention days (default 30)."""
        return int(self._server_config.get("retention_days", 30))

    def get_server_data_dir(self, server_id: str) -> Path:
        """Get data directory for a specific server."""
        return self.data_dir / server_id

    def get_channel_data_dir(self, server_id: str, channel_name: str) -> Path:
        """Get data directory for a specific channel."""
        # Sanitize channel name for filesystem
        safe_name = self._sanitize_filename(channel_name)
        return self.get_server_data_dir(server_id) / safe_name

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for use as filename."""
        # Replace invalid characters with underscores
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")
        # Lowercase and strip
        return name.lower().strip()


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
    _config = Config()
    return _config

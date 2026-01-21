"""
Configuration for Discord Bot plugin.

Self-contained config loader - no dependencies on other plugins.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration error."""
    pass


class BotConfig:
    """Configuration for Discord bot operations."""

    def __init__(self, data_dir: str = "."):
        """
        Initialize bot configuration.

        Args:
            data_dir: Base data directory (default: current directory)
        """
        self._data_dir = Path(data_dir)
        self._load_env()
        self._config = self._load_config()

    def _load_env(self) -> None:
        """Load environment variables from .env file."""
        # Try multiple locations for .env
        env_locations = [
            Path.cwd() / ".env",
            self._data_dir / ".env",
        ]

        for env_path in env_locations:
            if env_path.exists():
                load_dotenv(env_path)
                break

    def _load_config(self) -> dict:
        """Load configuration from agents.yaml."""
        config_locations = [
            Path.cwd() / "config" / "agents.yaml",
            self._data_dir / "config" / "agents.yaml",
        ]

        for config_path in config_locations:
            if config_path.exists():
                with open(config_path) as f:
                    return yaml.safe_load(f) or {}

        return {}

    @property
    def bot_token(self) -> str:
        """Get Discord bot token.

        Returns:
            Bot token string

        Raises:
            ConfigError: If bot token is not set
        """
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            raise ConfigError(
                "No Discord bot token set. "
                "Add DISCORD_BOT_TOKEN to .env file."
            )
        return token

    def has_bot_token(self) -> bool:
        """Check if bot token is set (without throwing)."""
        return bool(os.getenv("DISCORD_BOT_TOKEN"))

    @property
    def data_dir(self) -> Path:
        """Get base data directory."""
        configured = self._config.get("data_dir", "./data")
        return Path(configured)

    @property
    def bot_data_dir(self) -> Path:
        """Get discord-bot specific data directory."""
        return self.data_dir / "discord-bot"

    def get_server_data_dir(self, server_id: str, server_name: str = "server") -> Path:
        """Get data directory for a specific server."""
        slug = self._slugify(server_name)
        return self.bot_data_dir / f"{server_id}_{slug}"

    def _slugify(self, text: str) -> str:
        """Convert text to filesystem-safe slug."""
        # Simple slugify - lowercase, replace spaces with dashes
        slug = text.lower().strip()
        slug = slug.replace(" ", "-")
        # Remove non-alphanumeric characters except dashes
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        # Collapse multiple dashes
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug[:50] or "server"


# Global config instance
_config: Optional[BotConfig] = None


def get_config(data_dir: str = ".") -> BotConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = BotConfig(data_dir)
    return _config

"""Shared configuration loader for all community agents.

Loads from config/agents.yaml with platform-specific sections.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration error."""
    pass


class SetupError(Exception):
    """Error with guided recovery steps.

    Provides actionable hints and optional documentation links
    to help users resolve configuration issues.
    """
    def __init__(self, message: str, hint: str, docs_url: Optional[str] = None):
        self.message = message
        self.hint = hint
        self.docs_url = docs_url
        super().__init__(message)

    def __str__(self) -> str:
        parts = [self.message, f"\nHint: {self.hint}"]
        if self.docs_url:
            parts.append(f"\nDocs: {self.docs_url}")
        return "".join(parts)


@dataclass
class SetupState:
    """Tracks setup state for onboarding detection.

    Used to determine if this is a first-run, what's configured,
    and whether to show QuickStart or returning user prompts.
    """
    # File existence
    config_exists: bool
    env_exists: bool
    profile_exists: bool

    # Platform-specific configuration
    discord_token_set: bool
    discord_server_configured: bool
    telegram_credentials_set: bool
    telegram_group_configured: bool

    # Persona configuration
    persona_configured: bool

    # Metadata from config
    setup_complete: bool
    setup_mode: Optional[str]  # "quickstart" or "advanced"
    last_run_at: Optional[datetime]
    version: Optional[str]

    @property
    def is_first_run(self) -> bool:
        """True if this appears to be a first-time setup."""
        return not self.config_exists or not self.setup_complete

    @property
    def discord_ready(self) -> bool:
        """True if Discord is fully configured and ready to use."""
        return self.discord_token_set and self.discord_server_configured

    @property
    def telegram_ready(self) -> bool:
        """True if Telegram is fully configured and ready to use."""
        return self.telegram_credentials_set and self.telegram_group_configured


DEFAULT_CONFIG = """# Community Agent Configuration
# Shared settings for all platform connectors

# Setup metadata (auto-managed, do not edit)
_meta:
  created_at: null
  last_run_at: null
  version: null
  setup_complete: false
  setup_mode: null

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

# Bot persona (shared across platforms)
persona:
  preset: community_manager
  name: Alex
  role: Community Manager
  personality: "Professional, organized, and helpful. Keeps discussions on track."
  tasks:
    - Welcome new members
    - Answer community questions
    - Summarize discussions
    - Highlight important announcements
  communication_style: "Clear and professional, uses bullet points for clarity"
  background: "Experienced community manager who knows the ins and outs"
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
        # Use CLAUDE_LOCAL_DIR if available (set by Claude Code to user's working dir)
        # Fall back to cwd for standalone usage
        local_dir = os.getenv("CLAUDE_LOCAL_DIR")
        self._base_dir = Path(local_dir) if local_dir else Path.cwd()
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
        # Set creation timestamp
        self._config = yaml.safe_load(DEFAULT_CONFIG) or {}
        self._config.setdefault("_meta", {})["created_at"] = datetime.now().isoformat()
        with open(filepath, "w") as f:
            yaml.safe_dump(self._config, f, default_flow_style=False)
        print(f"Created default config at {filepath}")

    def save_config(self) -> None:
        """Save current configuration to agents.yaml."""
        filepath = self._config_dir / "agents.yaml"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        # Update last_run_at timestamp
        self._config.setdefault("_meta", {})["last_run_at"] = datetime.now().isoformat()
        with open(filepath, "w") as f:
            yaml.safe_dump(self._config, f, default_flow_style=False)

    # -------------------------------------------------------------------------
    # Setup state detection
    # -------------------------------------------------------------------------

    def is_first_run(self) -> bool:
        """Check if this is a first-time setup.

        Returns True if config doesn't exist or setup hasn't been completed.
        """
        config_path = self._config_dir / "agents.yaml"
        if not config_path.exists():
            return True
        meta = self._config.get("_meta", {})
        return not meta.get("setup_complete", False)

    def has_discord_token(self) -> bool:
        """Check if Discord token is set (without throwing)."""
        return bool(os.getenv("DISCORD_USER_TOKEN"))

    def has_telegram_credentials(self) -> bool:
        """Check if all Telegram credentials are set (without throwing)."""
        return all([
            os.getenv("TELEGRAM_API_ID"),
            os.getenv("TELEGRAM_API_HASH"),
            os.getenv("TELEGRAM_SESSION"),
        ])

    def get_setup_state(self) -> SetupState:
        """Get detailed setup state for onboarding flow.

        Returns a SetupState dataclass with all configuration checks.
        """
        config_path = self._config_dir / "agents.yaml"
        profile_path = self._config_dir / "PROFILE.md"
        meta = self._config.get("_meta", {})

        # Parse last_run_at if present
        last_run_at = None
        if meta.get("last_run_at"):
            try:
                last_run_at = datetime.fromisoformat(meta["last_run_at"])
            except (ValueError, TypeError):
                pass

        return SetupState(
            config_exists=config_path.exists(),
            env_exists=self._env_file.exists(),
            profile_exists=profile_path.exists(),
            discord_token_set=self.has_discord_token(),
            discord_server_configured=bool(self.discord_server_id),
            telegram_credentials_set=self.has_telegram_credentials(),
            telegram_group_configured=bool(self.telegram_default_group_id),
            persona_configured=self.persona_configured,
            setup_complete=meta.get("setup_complete", False),
            setup_mode=meta.get("setup_mode"),
            last_run_at=last_run_at,
            version=meta.get("version"),
        )

    def mark_setup_complete(self, mode: str = "quickstart", version: str = "1.0.0") -> None:
        """Mark setup as complete after successful onboarding.

        Args:
            mode: Setup mode used ("quickstart" or "advanced")
            version: Version of the setup process
        """
        self._config.setdefault("_meta", {})
        self._config["_meta"]["setup_complete"] = True
        self._config["_meta"]["setup_mode"] = mode
        self._config["_meta"]["version"] = version
        self.save_config()

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

    @property
    def config_path(self) -> Path:
        """Get path to the agents.yaml config file."""
        return self._config_dir / "agents.yaml"

    @property
    def base_dir(self) -> Path:
        """Get base directory (user's working directory)."""
        return self._base_dir

    # -------------------------------------------------------------------------
    # Platform-specific data directories (v2 unified structure)
    # -------------------------------------------------------------------------

    @property
    def discord_data_dir(self) -> Path:
        """Get Discord data root directory (data/discord/)."""
        return self.data_dir / "discord"

    @property
    def discord_servers_dir(self) -> Path:
        """Get Discord servers directory (data/discord/servers/)."""
        return self.discord_data_dir / "servers"

    @property
    def discord_dms_dir(self) -> Path:
        """Get Discord DMs directory (data/discord/dms/)."""
        return self.discord_data_dir / "dms"

    @property
    def telegram_data_dir(self) -> Path:
        """Get Telegram data root directory (data/telegram/)."""
        return self.data_dir / "telegram"

    @property
    def telegram_groups_dir(self) -> Path:
        """Get Telegram groups directory (data/telegram/groups/)."""
        return self.telegram_data_dir / "groups"

    @property
    def telegram_dms_dir(self) -> Path:
        """Get Telegram DMs directory (data/telegram/dms/)."""
        return self.telegram_data_dir / "dms"

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

    def get_discord_server_data_dir(self, server_id: str, server_name: Optional[str] = None) -> Path:
        """Get data directory for a specific Discord server.

        Uses unified v2 structure: data/discord/servers/{server_id}-{slug}/
        """
        if server_name:
            slug = self._slugify(server_name)
            return self.discord_servers_dir / f"{server_id}-{slug}"
        return self.discord_servers_dir / server_id

    def get_discord_channel_data_dir(self, server_id: str, channel_name: str, server_name: Optional[str] = None) -> Path:
        """Get data directory for a specific Discord channel."""
        safe_name = self._sanitize_filename(channel_name)
        return self.get_discord_server_data_dir(server_id, server_name) / safe_name

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
        """Get data directory for a specific Telegram group.

        Uses unified v2 structure: data/telegram/groups/{group_id}-{slug}/
        """
        if group_name:
            slug = self._slugify(group_name)
            return self.telegram_groups_dir / f"{group_id}-{slug}"
        return self.telegram_groups_dir / str(group_id)

    # -------------------------------------------------------------------------
    # Persona properties
    # -------------------------------------------------------------------------

    @property
    def persona(self) -> dict:
        """Get persona configuration."""
        return self._config.get("persona", {})

    @property
    def persona_preset(self) -> str:
        """Get persona preset name."""
        return self.persona.get("preset", "community_manager")

    @property
    def persona_name(self) -> str:
        """Get persona name."""
        return self.persona.get("name", "Alex")

    @property
    def persona_role(self) -> str:
        """Get persona role."""
        return self.persona.get("role", "Community Manager")

    @property
    def persona_configured(self) -> bool:
        """Check if persona has been configured."""
        return bool(self.persona.get("name"))

    def set_persona(self, persona_data: dict) -> None:
        """Set the bot persona.

        Args:
            persona_data: Dictionary with persona fields
        """
        self._config["persona"] = persona_data
        self.save_config()

    # Note: Persona presets and prompt generation are handled by community-agent.
    # Connectors only do data IO - persona is a "brain" concern.

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


def is_first_run() -> bool:
    """Check if this is a first-time setup (module-level convenience)."""
    return get_config().is_first_run()


def get_setup_state() -> SetupState:
    """Get detailed setup state (module-level convenience)."""
    return get_config().get_setup_state()

"""Skill requirements checking and enforcement.

This module provides centralized requirement checking for skills.
Requirements are declared in plugin.json and enforced before skill execution.

Usage:
    from lib.requirements import RequirementChecker
    from lib.config import get_config

    config = get_config()
    checker = RequirementChecker(config)

    # Check single requirement
    is_met, check = checker.check("persona")

    # Check and enforce multiple requirements
    if checker.enforce(["discord_token", "persona"]):
        # Requirements met, proceed
        ...
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class Requirement(Enum):
    """Available requirement types."""

    PERSONA = "persona"
    DISCORD_TOKEN = "discord_token"
    TELEGRAM_SESSION = "telegram_session"
    SYNC_DATA = "sync_data"
    DISCORD_SERVER = "discord_server"
    TELEGRAM_GROUP = "telegram_group"


@dataclass
class RequirementCheck:
    """Definition of a requirement check."""

    name: Requirement
    description: str
    check_fn: Callable[[], bool]
    setup_hint: str
    setup_command: Optional[str]


class RequirementChecker:
    """Check and enforce skill requirements."""

    def __init__(self, config):
        """Initialize checker with config.

        Args:
            config: CommunityConfig instance
        """
        self.config = config
        self._checks = self._register_checks()

    def _register_checks(self) -> dict[Requirement, RequirementCheck]:
        """Register all requirement checks."""
        return {
            Requirement.PERSONA: RequirementCheck(
                name=Requirement.PERSONA,
                description="Bot persona configuration",
                check_fn=self._check_persona,
                setup_hint="The bot persona defines how the agent communicates.",
                setup_command="community-init",
            ),
            Requirement.DISCORD_TOKEN: RequirementCheck(
                name=Requirement.DISCORD_TOKEN,
                description="Discord authentication token",
                check_fn=self._check_discord_token,
                setup_hint="Discord token is required to connect to Discord.",
                setup_command="discord-init",
            ),
            Requirement.TELEGRAM_SESSION: RequirementCheck(
                name=Requirement.TELEGRAM_SESSION,
                description="Telegram session",
                check_fn=self._check_telegram_session,
                setup_hint="Telegram session is required to connect to Telegram.",
                setup_command="telegram-init",
            ),
            Requirement.SYNC_DATA: RequirementCheck(
                name=Requirement.SYNC_DATA,
                description="Synced message data",
                check_fn=self._check_sync_data,
                setup_hint="No synced messages found. Run discord-sync or telegram-sync first.",
                setup_command=None,
            ),
            Requirement.DISCORD_SERVER: RequirementCheck(
                name=Requirement.DISCORD_SERVER,
                description="Default Discord server",
                check_fn=self._check_discord_server,
                setup_hint="No default Discord server configured.",
                setup_command="discord-init",
            ),
            Requirement.TELEGRAM_GROUP: RequirementCheck(
                name=Requirement.TELEGRAM_GROUP,
                description="Default Telegram group",
                check_fn=self._check_telegram_group,
                setup_hint="No default Telegram group configured.",
                setup_command="telegram-init",
            ),
        }

    def _check_persona(self) -> bool:
        """Check if persona is configured."""
        persona = self.config.persona
        return persona is not None and bool(persona.get("name"))

    def _check_discord_token(self) -> bool:
        """Check if Discord token is available."""
        return bool(os.environ.get("DISCORD_USER_TOKEN"))

    def _check_telegram_session(self) -> bool:
        """Check if Telegram session exists."""
        data_dir = Path(self.config.data_dir)
        session_path = data_dir / "telegram" / "session.session"
        return session_path.exists()

    def _check_sync_data(self) -> bool:
        """Check if any synced data exists."""
        data_dir = Path(self.config.data_dir)
        # Check for any .md files in discord or telegram directories
        for platform in ["discord", "telegram"]:
            platform_dir = data_dir / platform
            if platform_dir.exists():
                if list(platform_dir.rglob("*.md")):
                    return True
        return False

    def _check_discord_server(self) -> bool:
        """Check if default Discord server is configured."""
        return bool(self.config.discord_server_id)

    def _check_telegram_group(self) -> bool:
        """Check if default Telegram group is configured."""
        return bool(self.config.telegram_default_group_id)

    def check(self, requirement: str | Requirement) -> tuple[bool, RequirementCheck]:
        """Check a single requirement.

        Args:
            requirement: Requirement name (string or Requirement enum)

        Returns:
            Tuple of (is_met, RequirementCheck)
        """
        if isinstance(requirement, str):
            requirement = Requirement(requirement)

        check = self._checks[requirement]
        return check.check_fn(), check

    def check_all(
        self, requirements: list[str]
    ) -> tuple[bool, list[RequirementCheck]]:
        """Check multiple requirements.

        Args:
            requirements: List of requirement names

        Returns:
            Tuple of (all_met, list of failed checks)
        """
        failed = []
        for req in requirements:
            is_met, check = self.check(req)
            if not is_met:
                failed.append(check)

        return len(failed) == 0, failed

    def enforce(
        self, requirements: list[str], interactive: bool = True
    ) -> bool:
        """Enforce requirements, prompting for setup if needed.

        Args:
            requirements: List of requirement names to enforce
            interactive: Whether to prompt for setup if requirements missing

        Returns:
            True if all requirements met (or user completed setup).
            False if requirements not met and user declined setup.
        """
        all_met, failed = self.check_all(requirements)

        if all_met:
            return True

        if not interactive:
            return False

        # Show what's missing
        print()
        print("Missing requirements:")
        print()
        for check in failed:
            print(f"  * {check.description}")
            print(f"    {check.setup_hint}")
            if check.setup_command:
                print(f"    Run: {check.setup_command}")
            print()

        # Offer to run setup for first missing requirement with a setup command
        for check in failed:
            if check.setup_command:
                response = input(
                    f"Run '{check.setup_command}' now? [Y/n]: "
                ).strip().lower()
                if response in ("", "y", "yes"):
                    success = self._run_setup(check.setup_command)
                    if success:
                        # Re-check all requirements after setup
                        return self.enforce(requirements, interactive=interactive)
                break

        return False

    def _run_setup(self, command: str) -> bool:
        """Run a setup command.

        Args:
            command: Setup command name (e.g., "community-init")

        Returns:
            True if setup completed successfully
        """
        workspace_root = self._get_workspace_root()

        # Map command to script path
        command_map = {
            "community-init": workspace_root
            / "plugins"
            / "community-agent"
            / "tools"
            / "community_init.py",
            "discord-init": workspace_root
            / "plugins"
            / "discord-user-connector"
            / "tools"
            / "discord_init.py",
            "telegram-init": workspace_root
            / "plugins"
            / "telegram-connector"
            / "tools"
            / "telegram_init.py",
        }

        script = command_map.get(command)
        if not script:
            print(f"Unknown setup command: {command}")
            return False

        if not script.exists():
            print(f"Setup script not found: {script}")
            return False

        # Run the setup script
        print()
        result = subprocess.run([sys.executable, str(script)], cwd=workspace_root)
        print()
        return result.returncode == 0

    def _get_workspace_root(self) -> Path:
        """Get workspace root directory."""
        # Walk up from config file to find workspace root
        config_path = Path(self.config.config_path)
        # config/agents.yaml -> workspace root is parent of config/
        return config_path.parent.parent


def get_checker():
    """Get a RequirementChecker instance with default config.

    Returns:
        RequirementChecker instance
    """
    from .config import get_config

    config = get_config()
    return RequirementChecker(config)

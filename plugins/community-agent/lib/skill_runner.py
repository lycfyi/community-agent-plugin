"""Skill runner with requirements enforcement.

This module provides utilities for running skills with automatic
requirements checking based on declarations in plugin.json.

Usage (Option A - Declarative, recommended):
    Requirements are read from plugin.json and enforced automatically.
    No code changes needed in skill scripts.

Usage (Option B - In-script wrapper):
    from lib.skill_runner import main_with_requirements

    def main():
        # actual skill logic
        ...

    if __name__ == "__main__":
        sys.exit(main_with_requirements(
            "discord-send",
            ["discord_token", "persona"],
            main
        ))
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from .config import get_config
from .requirements import RequirementChecker


def load_skill_requirements(plugin_dir: Path, skill_name: str) -> list[str]:
    """Load requirements for a skill from plugin.json.

    Args:
        plugin_dir: Path to the plugin directory
        skill_name: Name of the skill (e.g., "discord-send")

    Returns:
        List of requirement names, or empty list if not declared
    """
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"

    if not plugin_json.exists():
        return []

    with open(plugin_json) as f:
        data = json.load(f)

    skills = data.get("skills", {})
    skill_config = skills.get(skill_name, {})
    return skill_config.get("requires", [])


def run_skill(
    plugin_dir: Path,
    skill_name: str,
    script_path: Path,
    args: Optional[list[str]] = None,
    interactive: bool = True,
) -> int:
    """Run a skill with requirements enforcement.

    Args:
        plugin_dir: Path to the plugin directory
        skill_name: Name of the skill (e.g., "discord-send")
        script_path: Path to the skill's Python script
        args: Arguments to pass to the script
        interactive: Whether to prompt for setup if requirements missing

    Returns:
        Exit code (0 = success, 1 = requirements not met, etc.)
    """
    args = args or []

    # Load requirements from plugin.json
    requirements = load_skill_requirements(plugin_dir, skill_name)

    if requirements:
        # Check requirements
        config = get_config()
        checker = RequirementChecker(config)

        if not checker.enforce(requirements, interactive=interactive):
            print(f"\nCannot run '{skill_name}' - requirements not met.")
            return 1

    # Run the actual skill script
    result = subprocess.run(
        [sys.executable, str(script_path)] + args,
        cwd=plugin_dir,
    )
    return result.returncode


def main_with_requirements(
    skill_name: str,
    requirements: list[str],
    main_fn: Callable[[], int],
    interactive: bool = True,
) -> int:
    """Wrapper for skill main() that checks requirements first.

    Use this when you want to embed requirements checking directly
    in a skill script rather than relying on external enforcement.

    Args:
        skill_name: Name of the skill (for error messages)
        requirements: List of requirement names to check
        main_fn: The actual main function to run
        interactive: Whether to prompt for setup if requirements missing

    Returns:
        Exit code from main_fn, or 1 if requirements not met

    Example:
        def main():
            # actual skill logic
            return 0

        if __name__ == "__main__":
            sys.exit(main_with_requirements(
                "discord-send",
                ["discord_token", "persona"],
                main
            ))
    """
    config = get_config()
    checker = RequirementChecker(config)

    if not checker.enforce(requirements, interactive=interactive):
        print(f"\nCannot run '{skill_name}' - requirements not met.")
        return 1

    return main_fn()


def check_requirements(requirements: list[str]) -> bool:
    """Quick check if requirements are met (no prompts).

    Args:
        requirements: List of requirement names to check

    Returns:
        True if all requirements are met
    """
    config = get_config()
    checker = RequirementChecker(config)
    all_met, _ = checker.check_all(requirements)
    return all_met

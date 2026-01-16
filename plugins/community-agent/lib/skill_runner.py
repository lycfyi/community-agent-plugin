"""Skill runner with requirements enforcement.

This module provides utilities for running skills with automatic
requirements checking based on declarations in requirements.yaml.

Usage (Option A - Declarative, recommended):
    Requirements are read from requirements.yaml in the skill directory
    and enforced automatically. No code changes needed in skill scripts.

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

import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

import yaml

from .config import get_config
from .requirements import RequirementChecker


def load_skill_requirements(skill_dir: Path) -> list[str]:
    """Load requirements for a skill from requirements.yaml.

    Args:
        skill_dir: Path to the skill directory (e.g., skills/discord-send/)

    Returns:
        List of requirement names, or empty list if no requirements file exists.
    """
    requirements_file = skill_dir / "requirements.yaml"

    if not requirements_file.exists():
        return []

    with open(requirements_file) as f:
        data = yaml.safe_load(f)

    return data.get("requires", []) if data else []


def run_skill(
    skill_dir: Path,
    skill_name: str,
    script_path: Path,
    args: Optional[list[str]] = None,
    interactive: bool = True,
) -> int:
    """Run a skill with requirements enforcement.

    Args:
        skill_dir: Path to the skill directory (e.g., skills/discord-send/)
        skill_name: Name of the skill (e.g., "discord-send")
        script_path: Path to the skill's Python script
        args: Arguments to pass to the script
        interactive: Whether to prompt for setup if requirements missing

    Returns:
        Exit code (0 = success, 1 = requirements not met, etc.)
    """
    args = args or []

    # Load requirements from skill's requirements.yaml
    requirements = load_skill_requirements(skill_dir)

    if requirements:
        # Check requirements
        config = get_config()
        checker = RequirementChecker(config)

        if not checker.enforce(requirements, interactive=interactive):
            print(f"\nCannot run '{skill_name}' - requirements not met.")
            return 1

    # Run the actual skill script
    plugin_dir = skill_dir.parent.parent  # skills/discord-send/ -> plugin root
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

#!/usr/bin/env python3
"""Community Agent initialization - Central persona and settings setup.

Usage:
    python community_init.py                    # Interactive setup
    python community_init.py --mode quickstart  # Fast setup with defaults
    python community_init.py --mode advanced    # Full customization
    python community_init.py --persona friendly_helper  # Direct preset

This is the central initialization for the community agent (THE BRAIN).
Platform connectors (Discord, Telegram) should be configured separately.

Exit Codes:
    0 - Success
    1 - Setup error
    2 - Configuration error
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.persona import (
    select_persona_quickstart,
    select_persona_interactive,
    get_preset,
    get_default_persona,
    list_presets,
)
from lib.profile import ensure_profile


def print_welcome(is_first_run: bool, mode: str) -> None:
    """Print welcome message based on setup state."""
    print("=" * 60)
    if is_first_run:
        print("Community Agent Setup")
        print(f"Mode: {mode.upper()}")
    else:
        print("Community Agent Configuration Update")
    print("=" * 60)
    print()


def prompt_returning_user(config) -> str:
    """Prompt returning user for action.

    Returns:
        Action to take: 'keep', 'update', or 'reset'
    """
    persona = config.persona

    print("Existing configuration detected:")
    print(f"  Persona: {persona.get('name', 'Not set')} ({persona.get('role', 'N/A')})")
    print(f"  Preset: {persona.get('preset', 'custom')}")
    print()
    print("Options:")
    print("  1. Keep current persona")
    print("  2. Update persona")
    print("  3. Reset and reconfigure")
    print()

    # For non-interactive CLI, default to 'update'
    return "update"


def run_quickstart(config) -> int:
    """Run QuickStart mode - minimal prompts, sensible defaults."""
    print("QuickStart: Setting up community agent...")
    print()

    # Set default persona (community_manager)
    persona = select_persona_quickstart()
    config.set_persona(persona.to_dict())

    print(f"Bot Persona: {persona.name} ({persona.role})")
    print(f"  Personality: {persona.personality.split('.')[0]}.")
    print(f"  Tasks: {', '.join(persona.tasks[:3])}")
    print()
    print("Tip: Run with --mode advanced to customize persona")
    print()

    # Create profile template if it doesn't exist
    ensure_profile()

    print("Configuration saved to config/agents.yaml")
    print()
    print("Next steps:")
    print("  1. Connect Discord: Run 'discord-init'")
    print("  2. Connect Telegram: Run 'telegram-init'")

    return 0


def run_advanced(config, args) -> int:
    """Run Advanced mode - full customization."""
    print("Advanced: Configuring community agent...")
    print()

    # Show current persona if exists
    current = config.persona
    if current.get("name"):
        print("Current persona:")
        print(f"  Name: {current.get('name')}")
        print(f"  Role: {current.get('role')}")
        print(f"  Preset: {current.get('preset', 'custom')}")
        print()

    # Persona selection
    if args.persona:
        # Use specified persona preset
        persona = get_preset(args.persona)
        if persona is None:
            persona = get_default_persona()
        print(f"Using persona preset: {args.persona}")
    else:
        # Interactive persona selection
        persona = select_persona_interactive()

    config.set_persona(persona.to_dict())

    print()
    print(f"Bot Persona: {persona.name} ({persona.role})")
    print(f"  Personality: {persona.personality.split('.')[0]}.")
    print(f"  Style: {persona.communication_style}")
    if persona.tasks:
        print(f"  Tasks: {', '.join(persona.tasks[:3])}")
    print()

    # Create profile template if it doesn't exist
    ensure_profile()

    print("Configuration saved to config/agents.yaml")
    print()
    print("Next steps:")
    print("  1. Connect Discord: Run 'discord-init'")
    print("  2. Connect Telegram: Run 'telegram-init'")
    print("  3. View persona: Run 'python tools/persona_status.py'")

    return 0


def main(args: argparse.Namespace) -> int:
    """Main entry point."""
    try:
        config = get_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    # Determine mode
    is_first_run = config.is_first_run()

    # Auto-detect mode if not specified
    if args.mode:
        mode = args.mode
    elif is_first_run:
        mode = "quickstart"  # Default to quickstart for new users
    else:
        mode = "advanced"  # Returning users get advanced mode

    print_welcome(is_first_run, mode)

    # Handle returning user
    if not is_first_run and config.persona_configured:
        action = prompt_returning_user(config)
        if action == "keep":
            print("Keeping current configuration.")
            return 0

    try:
        if mode == "quickstart":
            return run_quickstart(config)
        else:
            return run_advanced(config, args)

    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        return 1


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Initialize Community Agent configuration",
        epilog="This sets up the agent persona. Run discord-init or telegram-init to connect platforms."
    )
    parser.add_argument(
        "--mode",
        choices=["quickstart", "advanced"],
        help="Setup mode: quickstart (defaults) or advanced (customize)"
    )
    parser.add_argument(
        "--persona",
        choices=["community_manager", "friendly_helper", "tech_expert"],
        help="Bot persona preset to use directly"
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available persona presets and exit"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Handle --list-presets
    if args.list_presets:
        print("Available Persona Presets:")
        print("-" * 50)
        for preset_id, persona in list_presets():
            print(f"\n{preset_id}:")
            print(f"  Name: {persona.name}")
            print(f"  Role: {persona.role}")
            print(f"  Personality: {persona.personality.split('.')[0]}.")
        sys.exit(0)

    exit_code = main(args)
    sys.exit(exit_code)

#!/usr/bin/env python3
"""Display and manage bot persona configuration.

Usage:
    python persona_status.py              # Human-readable output
    python persona_status.py --json       # JSON output
    python persona_status.py --prompt     # LLM prompt format

Exit Codes:
    0 - Success
    1 - Configuration error
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError


def print_human_readable(persona: dict) -> None:
    """Print persona in human-readable format."""
    print("Bot Persona Configuration")
    print("=" * 50)
    print()
    print(f"Preset: {persona.get('preset', 'N/A')}")
    print(f"Name: {persona.get('name', 'N/A')}")
    print(f"Role: {persona.get('role', 'N/A')}")
    print()
    print(f"Personality: {persona.get('personality', 'N/A')}")
    print()

    tasks = persona.get("tasks", [])
    if tasks:
        print("Tasks:")
        for task in tasks:
            print(f"  - {task}")
        print()

    style = persona.get("communication_style")
    if style:
        print(f"Communication Style: {style}")
        print()

    background = persona.get("background")
    if background:
        print(f"Background: {background}")
        print()

    print("-" * 50)
    print("To update persona, run: community-init --mode advanced")
    print("Or edit: config/agents.yaml")


def print_json_output(persona: dict, configured: bool) -> None:
    """Print persona as JSON with configured status."""
    output = {
        "configured": configured,
        "persona": persona if configured else None
    }
    print(json.dumps(output, indent=2))


def print_prompt_output(config) -> None:
    """Print persona as LLM-ready prompt."""
    prompt = config.get_persona_prompt()
    print(prompt)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Display bot persona configuration",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Output as LLM prompt"
    )

    args = parser.parse_args()

    try:
        config = get_config()
        persona = config.persona

        # Check if persona is actually configured (has at least a name)
        configured = bool(persona and persona.get("name"))

        if args.json:
            # JSON always returns, with configured status
            print_json_output(persona or {}, configured)
            return 0

        # Non-JSON outputs require persona to be configured
        if not configured:
            print("No persona configured.", file=sys.stderr)
            print("Run community-init to set up your agent identity.", file=sys.stderr)
            return 1

        if args.prompt:
            print_prompt_output(config)
        else:
            print_human_readable(persona)

        return 0

    except ConfigError as e:
        if args.json:
            # Return JSON even on config error
            print(json.dumps({"configured": False, "persona": None, "error": str(e)}, indent=2))
            return 0
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

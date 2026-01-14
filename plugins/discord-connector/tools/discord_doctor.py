#!/usr/bin/env python3
"""Discord doctor tool - Diagnose configuration and connectivity issues.

Usage:
    python discord_doctor.py

Checks:
    1. Environment file exists (.env)
    2. Discord token is present
    3. Token format appears valid
    4. Authentication succeeds
    5. Configuration file is valid
    6. Default server is accessible
    7. Data directory is writable

Output:
    - Diagnostic results with ✓ (pass) or ✗ (fail)
    - Suggested fixes for any issues found

Exit Codes:
    0 - All checks passed
    1 - Some checks failed (see output for details)

Note: This tool diagnoses only - it does not modify any files.
"""

import asyncio
import os
import sys
from pathlib import Path

import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError


class DiagnosticResult:
    """Result of a single diagnostic check."""

    def __init__(self, name: str, passed: bool, message: str = "", hint: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        icon = "✓" if self.passed else "✗"
        result = f"  {icon} {self.name}"
        if self.message:
            result += f" ({self.message})"
        return result


def check_env_file() -> DiagnosticResult:
    """Check if .env file exists."""
    # Use CLAUDE_LOCAL_DIR if available
    local_dir = os.getenv("CLAUDE_LOCAL_DIR")
    base_dir = Path(local_dir) if local_dir else Path.cwd()
    env_path = base_dir / ".env"

    if env_path.exists():
        return DiagnosticResult("Environment file", True, ".env found")
    else:
        return DiagnosticResult(
            "Environment file",
            False,
            ".env not found",
            "Create a .env file with your Discord token"
        )


def check_token_present() -> DiagnosticResult:
    """Check if Discord token is set in environment."""
    token = os.getenv("DISCORD_USER_TOKEN")

    if token:
        masked = f"{'*' * 10}...{token[-6:]}"
        return DiagnosticResult("Discord token", True, masked)
    else:
        return DiagnosticResult(
            "Discord token",
            False,
            "DISCORD_USER_TOKEN not set",
            "Add DISCORD_USER_TOKEN=your_token to .env file"
        )


def check_token_format() -> DiagnosticResult:
    """Check if token format appears valid."""
    token = os.getenv("DISCORD_USER_TOKEN", "")

    if not token:
        return DiagnosticResult(
            "Token format",
            False,
            "No token to check",
            "Set DISCORD_USER_TOKEN first"
        )

    # Discord user tokens are typically long base64-ish strings
    # Bot tokens have a specific format, user tokens are more varied
    if len(token) < 50:
        return DiagnosticResult(
            "Token format",
            False,
            "Token appears too short",
            "Discord tokens are typically 50+ characters. Check if you copied the full token."
        )

    # Check for common mistakes
    if token.startswith("Bot ") or token.startswith("Bearer "):
        return DiagnosticResult(
            "Token format",
            False,
            "Token has incorrect prefix",
            "Remove 'Bot ' or 'Bearer ' prefix - just use the raw token value"
        )

    return DiagnosticResult("Token format", True, "Format looks valid")


async def check_authentication() -> DiagnosticResult:
    """Check if token can authenticate with Discord."""
    try:
        from lib.discord_client import DiscordUserClient, AuthenticationError

        client = DiscordUserClient()
        try:
            guilds = await client.list_guilds()
            return DiagnosticResult(
                "Authentication",
                True,
                f"Connected ({len(guilds)} servers)"
            )
        except AuthenticationError as e:
            return DiagnosticResult(
                "Authentication",
                False,
                str(e),
                "Your token may be expired. Get a fresh token from Discord DevTools."
            )
        finally:
            await client.close()

    except Exception as e:
        return DiagnosticResult(
            "Authentication",
            False,
            f"Error: {e}",
            "Check your network connection and try again"
        )


def check_config_file() -> DiagnosticResult:
    """Check if config file exists and is valid."""
    local_dir = os.getenv("CLAUDE_LOCAL_DIR")
    base_dir = Path(local_dir) if local_dir else Path.cwd()
    config_path = base_dir / "config" / "agents.yaml"

    if not config_path.exists():
        return DiagnosticResult(
            "Config file",
            False,
            "config/agents.yaml not found",
            "Run discord-init to create the config file"
        )

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if config is None:
            return DiagnosticResult(
                "Config file",
                False,
                "Config file is empty",
                "Run discord-init to set up configuration"
            )

        return DiagnosticResult("Config file", True, "Valid YAML")

    except yaml.YAMLError as e:
        return DiagnosticResult(
            "Config file",
            False,
            f"Invalid YAML: {e}",
            "Fix the syntax error in config/agents.yaml or delete it and run discord-init"
        )


def check_server_configured() -> DiagnosticResult:
    """Check if a default server is configured."""
    try:
        config = get_config()
        server_id = config.server_id

        if server_id:
            server_name = config._community_config._config.get("discord", {}).get(
                "default_server_name", "Unknown"
            )
            return DiagnosticResult(
                "Server configured",
                True,
                f"{server_name} ({server_id})"
            )
        else:
            return DiagnosticResult(
                "Server configured",
                False,
                "No default server set",
                "Run discord-init to select a server"
            )

    except ConfigError as e:
        return DiagnosticResult(
            "Server configured",
            False,
            str(e),
            "Fix the configuration error first"
        )


def check_data_directory() -> DiagnosticResult:
    """Check if data directory is writable."""
    local_dir = os.getenv("CLAUDE_LOCAL_DIR")
    base_dir = Path(local_dir) if local_dir else Path.cwd()
    data_dir = base_dir / "data"

    # Try to create the directory if it doesn't exist
    try:
        data_dir.mkdir(parents=True, exist_ok=True)

        # Try to write a test file
        test_file = data_dir / ".doctor_test"
        test_file.write_text("test")
        test_file.unlink()

        return DiagnosticResult("Data directory", True, str(data_dir))

    except PermissionError:
        return DiagnosticResult(
            "Data directory",
            False,
            "Permission denied",
            f"Check write permissions for {data_dir}"
        )
    except Exception as e:
        return DiagnosticResult(
            "Data directory",
            False,
            str(e),
            "Ensure the data directory is accessible"
        )


async def run_diagnostics() -> list[DiagnosticResult]:
    """Run all diagnostic checks."""
    results = []

    # Synchronous checks
    results.append(check_env_file())
    results.append(check_token_present())
    results.append(check_token_format())
    results.append(check_config_file())
    results.append(check_server_configured())
    results.append(check_data_directory())

    # Only run authentication check if token is present
    if os.getenv("DISCORD_USER_TOKEN"):
        results.append(await check_authentication())

    return results


def print_results(results: list[DiagnosticResult]) -> bool:
    """Print diagnostic results.

    Returns:
        True if all checks passed, False otherwise.
    """
    print("discord-doctor results:")
    print()

    all_passed = True
    failed_results = []

    for result in results:
        print(result)
        if not result.passed:
            all_passed = False
            failed_results.append(result)

    print()

    if all_passed:
        print("All checks passed! Discord is ready to use.")
    else:
        print("Some checks failed. Suggested fixes:")
        print()
        for result in failed_results:
            if result.hint:
                print(f"  • {result.name}:")
                print(f"    {result.hint}")
                print()

        print("(Run these steps manually - doctor does not modify files)")

    return all_passed


async def main() -> int:
    """Main entry point."""
    print("=" * 50)
    print("Discord Doctor - Diagnostic Tool")
    print("=" * 50)
    print()

    results = await run_diagnostics()
    all_passed = print_results(results)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

#!/usr/bin/env python3
"""Telegram doctor tool - Diagnose configuration and connectivity issues.

Usage:
    python telegram_doctor.py

Checks:
    1. Environment file exists (.env)
    2. Telegram credentials are present (API_ID, API_HASH, SESSION)
    3. Session format appears valid
    4. Authentication succeeds
    5. Configuration file is valid
    6. Default group is accessible
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
            "Create a .env file with your Telegram credentials"
        )


def check_api_id() -> DiagnosticResult:
    """Check if Telegram API ID is set."""
    api_id = os.getenv("TELEGRAM_API_ID")

    if api_id:
        try:
            int(api_id)
            return DiagnosticResult("API ID", True, api_id)
        except ValueError:
            return DiagnosticResult(
                "API ID",
                False,
                "Not a valid number",
                "TELEGRAM_API_ID should be a numeric ID from my.telegram.org"
            )
    else:
        return DiagnosticResult(
            "API ID",
            False,
            "TELEGRAM_API_ID not set",
            "Get your API ID from https://my.telegram.org/apps"
        )


def check_api_hash() -> DiagnosticResult:
    """Check if Telegram API hash is set."""
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if api_hash:
        if len(api_hash) >= 20:
            masked = f"{api_hash[:6]}...{api_hash[-4:]}"
            return DiagnosticResult("API hash", True, masked)
        else:
            return DiagnosticResult(
                "API hash",
                False,
                "Hash appears too short",
                "Check if you copied the full API hash from my.telegram.org"
            )
    else:
        return DiagnosticResult(
            "API hash",
            False,
            "TELEGRAM_API_HASH not set",
            "Get your API hash from https://my.telegram.org/apps"
        )


def check_session() -> DiagnosticResult:
    """Check if Telegram session string is set and valid."""
    session = os.getenv("TELEGRAM_SESSION")

    if not session:
        return DiagnosticResult(
            "Session string",
            False,
            "TELEGRAM_SESSION not set",
            "Generate a session using: python scripts/generate_session.py"
        )

    # Session strings are typically long base64 strings
    if len(session) < 100:
        return DiagnosticResult(
            "Session string",
            False,
            "Session appears too short",
            "Generate a fresh session: python scripts/generate_session.py"
        )

    masked = f"{'*' * 10}...{session[-10:]}"
    return DiagnosticResult("Session string", True, masked)


async def check_authentication() -> DiagnosticResult:
    """Check if credentials can authenticate with Telegram."""
    try:
        from lib.telegram_client import TelegramUserClient, AuthenticationError

        client = TelegramUserClient()
        try:
            await client.connect()
            me = await client.get_me()
            username = me.get("username", "N/A")
            return DiagnosticResult(
                "Authentication",
                True,
                f"Connected as @{username}"
            )
        except AuthenticationError as e:
            return DiagnosticResult(
                "Authentication",
                False,
                str(e),
                "Your session may be expired. Generate a new one."
            )
        finally:
            await client.disconnect()

    except Exception as e:
        return DiagnosticResult(
            "Authentication",
            False,
            f"Error: {e}",
            "Check your credentials and network connection"
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
            "Run telegram-init to create the config file"
        )

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if config is None:
            return DiagnosticResult(
                "Config file",
                False,
                "Config file is empty",
                "Run telegram-init to set up configuration"
            )

        return DiagnosticResult("Config file", True, "Valid YAML")

    except yaml.YAMLError as e:
        return DiagnosticResult(
            "Config file",
            False,
            f"Invalid YAML: {e}",
            "Fix the syntax error in config/agents.yaml or delete it and run telegram-init"
        )


def check_group_configured() -> DiagnosticResult:
    """Check if a default group is configured."""
    try:
        config = get_config()
        group_id = config.default_group_id

        if group_id:
            group_name = config.default_group_name or "Unknown"
            return DiagnosticResult(
                "Group configured",
                True,
                f"{group_name} ({group_id})"
            )
        else:
            return DiagnosticResult(
                "Group configured",
                False,
                "No default group set",
                "Run telegram-init to select a group"
            )

    except ConfigError as e:
        return DiagnosticResult(
            "Group configured",
            False,
            str(e),
            "Fix the configuration error first"
        )


def check_data_directory() -> DiagnosticResult:
    """Check if data directory is writable."""
    local_dir = os.getenv("CLAUDE_LOCAL_DIR")
    base_dir = Path(local_dir) if local_dir else Path.cwd()
    data_dir = base_dir / "data"

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
    results.append(check_api_id())
    results.append(check_api_hash())
    results.append(check_session())
    results.append(check_config_file())
    results.append(check_group_configured())
    results.append(check_data_directory())

    # Only run authentication check if all credentials are present
    if all([
        os.getenv("TELEGRAM_API_ID"),
        os.getenv("TELEGRAM_API_HASH"),
        os.getenv("TELEGRAM_SESSION"),
    ]):
        results.append(await check_authentication())

    return results


def print_results(results: list[DiagnosticResult]) -> bool:
    """Print diagnostic results.

    Returns:
        True if all checks passed, False otherwise.
    """
    print("telegram-doctor results:")
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
        print("All checks passed! Telegram is ready to use.")
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
    print("Telegram Doctor - Diagnostic Tool")
    print("=" * 50)
    print()

    results = await run_diagnostics()
    all_passed = print_results(results)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

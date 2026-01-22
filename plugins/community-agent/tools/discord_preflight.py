#!/usr/bin/env python3
"""Discord sync preflight check - Detect tokens and permissions to route sync.

This tool checks:
1. Which tokens are configured in .env
2. For bot token: server access and required permissions
3. Returns routing recommendation

Usage:
    python tools/discord_preflight.py --server SERVER_ID
    python tools/discord_preflight.py --server SERVER_ID --json
    python tools/discord_preflight.py --check-tokens
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

# Load environment variables from current working directory
from dotenv import load_dotenv

# Find .env in current working directory
_env_path = Path.cwd() / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Fallback to default behavior
    load_dotenv()

try:
    import aiohttp
except ImportError:
    aiohttp = None


class SyncRecommendation(Enum):
    """Recommended sync connector."""
    BOT_CONNECTOR = "discord-bot-connector:discord-sync"
    USER_CONNECTOR = "discord-user-connector:discord-sync"
    NONE = "none"


@dataclass
class TokenStatus:
    """Status of a Discord token."""
    configured: bool
    valid: bool = False
    error: Optional[str] = None


@dataclass
class BotPermissions:
    """Bot permissions for a server."""
    server_id: str
    server_name: Optional[str] = None
    has_access: bool = False
    can_view_channels: bool = False
    can_read_history: bool = False
    error: Optional[str] = None


@dataclass
class PreflightResult:
    """Result of preflight check."""
    user_token: TokenStatus
    bot_token: TokenStatus
    bot_permissions: Optional[BotPermissions] = None
    wants_dms: bool = False
    recommendation: SyncRecommendation = SyncRecommendation.NONE
    reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        result = {
            "user_token": asdict(self.user_token),
            "bot_token": asdict(self.bot_token),
            "wants_dms": self.wants_dms,
            "recommendation": self.recommendation.value,
            "reason": self.reason,
        }
        if self.bot_permissions:
            result["bot_permissions"] = asdict(self.bot_permissions)
        return result


# Discord permission flags
# https://discord.com/developers/docs/topics/permissions
VIEW_CHANNEL = 1 << 10  # 1024
READ_MESSAGE_HISTORY = 1 << 16  # 65536


async def check_bot_token(token: str) -> TokenStatus:
    """Verify bot token is valid by calling /users/@me."""
    if not aiohttp:
        return TokenStatus(configured=True, valid=False, error="aiohttp not installed")

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bot {token}"}
            async with session.get(
                "https://discord.com/api/v10/users/@me",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return TokenStatus(configured=True, valid=True)
                elif resp.status == 401:
                    return TokenStatus(configured=True, valid=False, error="Invalid token")
                else:
                    return TokenStatus(configured=True, valid=False, error=f"HTTP {resp.status}")
    except Exception as e:
        return TokenStatus(configured=True, valid=False, error=str(e))


async def check_user_token(token: str) -> TokenStatus:
    """Verify user token is valid by calling /users/@me."""
    if not aiohttp:
        return TokenStatus(configured=True, valid=False, error="aiohttp not installed")

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": token}
            async with session.get(
                "https://discord.com/api/v10/users/@me",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return TokenStatus(configured=True, valid=True)
                elif resp.status == 401:
                    return TokenStatus(configured=True, valid=False, error="Invalid token")
                else:
                    return TokenStatus(configured=True, valid=False, error=f"HTTP {resp.status}")
    except Exception as e:
        return TokenStatus(configured=True, valid=False, error=str(e))


async def resolve_server_id(token: str, server_query: str, is_bot: bool = True) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve server ID from ID or name.

    Args:
        token: Discord token (bot or user)
        server_query: Server ID or name to look up
        is_bot: Whether token is a bot token

    Returns:
        Tuple of (server_id, server_name, error)
    """
    if not aiohttp:
        return None, None, "aiohttp not installed"

    try:
        async with aiohttp.ClientSession() as session:
            if is_bot:
                headers = {"Authorization": f"Bot {token}"}
            else:
                headers = {"Authorization": token}

            async with session.get(
                "https://discord.com/api/v10/users/@me/guilds",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return None, None, f"Failed to list servers: HTTP {resp.status}"

                guilds = await resp.json()

            # First try exact ID match
            for g in guilds:
                if g["id"] == server_query:
                    return g["id"], g["name"], None

            # Try name match (case-insensitive, partial)
            search_term = server_query.lower()
            matches = [g for g in guilds if search_term in g["name"].lower()]

            if len(matches) == 1:
                return matches[0]["id"], matches[0]["name"], None
            elif len(matches) > 1:
                names = ", ".join(f"'{m['name']}'" for m in matches[:3])
                return None, None, f"Multiple servers match '{server_query}': {names}"
            else:
                return None, None, f"Server '{server_query}' not found"

    except Exception as e:
        return None, None, str(e)


async def check_bot_permissions(token: str, server_id: str) -> BotPermissions:
    """Check bot permissions for a specific server."""
    if not aiohttp:
        return BotPermissions(
            server_id=server_id,
            error="aiohttp not installed"
        )

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bot {token}"}

            # Get bot's guild member info (includes permissions)
            async with session.get(
                f"https://discord.com/api/v10/guilds/{server_id}",
                headers=headers
            ) as resp:
                if resp.status == 404:
                    return BotPermissions(
                        server_id=server_id,
                        has_access=False,
                        error="Bot not in server"
                    )
                elif resp.status == 403:
                    return BotPermissions(
                        server_id=server_id,
                        has_access=False,
                        error="Bot lacks permissions to view server"
                    )
                elif resp.status != 200:
                    return BotPermissions(
                        server_id=server_id,
                        error=f"HTTP {resp.status}"
                    )

                guild_data = await resp.json()
                server_name = guild_data.get("name")

            # Get bot's own member info for this guild
            async with session.get(
                f"https://discord.com/api/v10/guilds/{server_id}/members/@me",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    # Fallback: bot is in server but can't get member info
                    return BotPermissions(
                        server_id=server_id,
                        server_name=server_name,
                        has_access=True,
                        can_view_channels=True,  # Assume yes if in server
                        can_read_history=True,   # Assume yes if in server
                    )

                member_data = await resp.json()

            # Get guild roles to calculate permissions
            async with session.get(
                f"https://discord.com/api/v10/guilds/{server_id}/roles",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    # Fallback: assume permissions if in server
                    return BotPermissions(
                        server_id=server_id,
                        server_name=server_name,
                        has_access=True,
                        can_view_channels=True,
                        can_read_history=True,
                    )

                roles_data = await resp.json()

            # Calculate permissions from roles
            member_roles = set(member_data.get("roles", []))
            permissions = 0

            for role in roles_data:
                # @everyone role or member has this role
                if role["id"] == server_id or role["id"] in member_roles:
                    permissions |= int(role.get("permissions", 0))

            # Check for admin (has all permissions)
            ADMINISTRATOR = 1 << 3
            if permissions & ADMINISTRATOR:
                return BotPermissions(
                    server_id=server_id,
                    server_name=server_name,
                    has_access=True,
                    can_view_channels=True,
                    can_read_history=True,
                )

            return BotPermissions(
                server_id=server_id,
                server_name=server_name,
                has_access=True,
                can_view_channels=bool(permissions & VIEW_CHANNEL),
                can_read_history=bool(permissions & READ_MESSAGE_HISTORY),
            )

    except Exception as e:
        return BotPermissions(
            server_id=server_id,
            error=str(e)
        )


def determine_recommendation(result: PreflightResult) -> PreflightResult:
    """Determine the best connector to use based on preflight results."""

    # Case 1: User wants DMs - must use user connector
    if result.wants_dms:
        if result.user_token.configured and result.user_token.valid:
            result.recommendation = SyncRecommendation.USER_CONNECTOR
            result.reason = "DM sync requires user token"
        else:
            result.recommendation = SyncRecommendation.NONE
            result.reason = "DM sync requires user token, but no valid user token configured"
        return result

    # Case 2: Bot token available with proper permissions - prefer bot
    if result.bot_token.configured and result.bot_token.valid:
        if result.bot_permissions:
            if result.bot_permissions.has_access:
                if result.bot_permissions.can_read_history:
                    result.recommendation = SyncRecommendation.BOT_CONNECTOR
                    result.reason = (
                        f"Bot has access to {result.bot_permissions.server_name or 'server'} "
                        "with required permissions (faster sync)"
                    )
                    return result
                else:
                    # Bot in server but lacks Read Message History
                    result.reason = (
                        f"Bot is in {result.bot_permissions.server_name or 'server'} "
                        "but lacks 'Read Message History' permission"
                    )
            else:
                # Bot not in server
                result.reason = f"Bot is not in server {result.bot_permissions.server_id}"
        else:
            # No server specified, but bot token is valid
            result.recommendation = SyncRecommendation.BOT_CONNECTOR
            result.reason = "Bot token valid (faster sync, but verify bot is in target server)"
            return result

    # Case 3: Fall back to user token
    if result.user_token.configured and result.user_token.valid:
        result.recommendation = SyncRecommendation.USER_CONNECTOR
        if result.reason:
            result.reason += " - falling back to user token"
        else:
            result.reason = "Using user token (bot token not available or lacks permissions)"
        return result

    # Case 4: No valid tokens
    result.recommendation = SyncRecommendation.NONE
    if not result.user_token.configured and not result.bot_token.configured:
        result.reason = "No Discord tokens configured in .env"
    elif result.user_token.error:
        result.reason = f"User token error: {result.user_token.error}"
    elif result.bot_token.error:
        result.reason = f"Bot token error: {result.bot_token.error}"
    else:
        result.reason = "No valid Discord tokens available"

    return result


async def run_preflight(
    server_query: Optional[str] = None,
    wants_dms: bool = False,
) -> PreflightResult:
    """Run preflight check for Discord sync.

    Args:
        server_query: Optional server ID or name to check bot permissions for.
        wants_dms: Whether user wants to sync DMs.

    Returns:
        PreflightResult with recommendation.
    """
    user_token = os.getenv("DISCORD_USER_TOKEN")
    bot_token = os.getenv("DISCORD_BOT_TOKEN")

    # Initialize result
    result = PreflightResult(
        user_token=TokenStatus(configured=bool(user_token)),
        bot_token=TokenStatus(configured=bool(bot_token)),
        wants_dms=wants_dms,
    )

    # Validate tokens in parallel
    tasks = []
    if user_token:
        tasks.append(("user", check_user_token(user_token)))
    if bot_token:
        tasks.append(("bot", check_bot_token(bot_token)))

    if tasks:
        results = await asyncio.gather(*[t[1] for t in tasks])
        for i, (token_type, _) in enumerate(tasks):
            if token_type == "user":
                result.user_token = results[i]
            else:
                result.bot_token = results[i]

    # Resolve server ID from name if needed, and check bot permissions
    if server_query and bot_token and result.bot_token.configured and result.bot_token.valid:
        # Resolve server ID (supports both ID and name)
        resolved_id, resolved_name, resolve_error = await resolve_server_id(
            bot_token, server_query, is_bot=True
        )

        if resolve_error:
            # Server not found in bot's guilds - still create permissions object with error
            result.bot_permissions = BotPermissions(
                server_id=server_query,
                has_access=False,
                error=resolve_error
            )
        elif resolved_id:
            # Check permissions with resolved ID
            result.bot_permissions = await check_bot_permissions(bot_token, resolved_id)
            # Update server name if we resolved it
            if resolved_name and not result.bot_permissions.server_name:
                result.bot_permissions.server_name = resolved_name

    # Determine recommendation
    return determine_recommendation(result)


def print_result(result: PreflightResult, as_json: bool = False) -> None:
    """Print preflight result."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2))
        return

    print("=" * 50)
    print("Discord Sync Preflight Check")
    print("=" * 50)
    print()

    # Token status
    print("Token Status:")
    user_status = "valid" if result.user_token.valid else (
        result.user_token.error or "not configured"
    )
    bot_status = "valid" if result.bot_token.valid else (
        result.bot_token.error or "not configured"
    )
    print(f"  User Token: {user_status}")
    print(f"  Bot Token:  {bot_status}")
    print()

    # Bot permissions (if checked)
    if result.bot_permissions:
        print("Bot Permissions:")
        print(f"  Server: {result.bot_permissions.server_name or result.bot_permissions.server_id}")
        if result.bot_permissions.error:
            print(f"  Error: {result.bot_permissions.error}")
        else:
            print(f"  Has Access: {'Yes' if result.bot_permissions.has_access else 'No'}")
            print(f"  View Channels: {'Yes' if result.bot_permissions.can_view_channels else 'No'}")
            print(f"  Read History: {'Yes' if result.bot_permissions.can_read_history else 'No'}")
        print()

    # Recommendation
    print("Recommendation:")
    if result.recommendation == SyncRecommendation.NONE:
        print(f"  Cannot sync: {result.reason}")
    else:
        print(f"  Use: {result.recommendation.value}")
        print(f"  Reason: {result.reason}")
    print()

    # Next steps
    if result.recommendation != SyncRecommendation.NONE:
        print("Next Step:")
        if result.recommendation == SyncRecommendation.BOT_CONNECTOR:
            print("  Invoke Skill: discord-bot-connector:discord-sync")
        else:
            print("  Invoke Skill: discord-user-connector:discord-sync")


def main():
    parser = argparse.ArgumentParser(
        description="Discord sync preflight check"
    )
    parser.add_argument(
        "--server",
        metavar="SERVER_ID",
        help="Server ID to check bot permissions for"
    )
    parser.add_argument(
        "--dms",
        action="store_true",
        help="Check for DM sync (requires user token)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--check-tokens",
        action="store_true",
        dest="check_tokens",
        help="Only check token validity (no server-specific checks)"
    )

    args = parser.parse_args()

    try:
        result = asyncio.run(run_preflight(
            server_query=args.server,
            wants_dms=args.dms,
        ))
        print_result(result, as_json=args.json)

        # Exit code based on recommendation
        if result.recommendation == SyncRecommendation.NONE:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()

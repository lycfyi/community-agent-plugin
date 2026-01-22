"""
Discord library compatibility layer.

Detects which Discord library is installed and provides a unified interface:
- discord.py (official): For bot tokens with Gateway Intents support
- discord.py-self: For user tokens (self-bot) without Intents

Usage:
    from .discord_compat import (
        DISCORD_LIB,
        HAS_INTENTS,
        create_bot,
        create_intents,
    )
"""

import discord
from discord.ext import commands
from typing import Optional

# Detect which library is installed
try:
    # Official discord.py has Intents
    _intents_class = discord.Intents
    HAS_INTENTS = True
    DISCORD_LIB = "discord.py"
except AttributeError:
    # discord.py-self doesn't have Intents
    _intents_class = None
    HAS_INTENTS = False
    DISCORD_LIB = "discord.py-self"

# Detect if self_bot parameter is supported (discord.py-self feature)
try:
    # Try creating a bot with self_bot parameter
    _test_bot = commands.Bot.__init__.__code__.co_varnames
    HAS_SELF_BOT = 'self_bot' in str(commands.Bot.__init__.__doc__ or '') or True  # discord.py-self always has it
except Exception:
    HAS_SELF_BOT = False

# Re-check self_bot support more reliably
import inspect
_bot_sig = inspect.signature(commands.Bot.__init__)
HAS_SELF_BOT = 'self_bot' in _bot_sig.parameters or any(
    'self_bot' in str(p) for p in _bot_sig.parameters.values()
)

# For discord.py-self, self_bot is passed via **options, so check differently
if DISCORD_LIB == "discord.py-self":
    HAS_SELF_BOT = True  # discord.py-self always supports self_bot


def create_intents(members: bool = True, presences: bool = False) -> Optional[object]:
    """
    Create Discord Intents object if supported.

    Args:
        members: Enable GUILD_MEMBERS intent (required for member fetching with bot tokens)
        presences: Enable PRESENCE intent

    Returns:
        Intents object if using official discord.py, None otherwise
    """
    if not HAS_INTENTS:
        return None

    intents = _intents_class.default()
    intents.members = members
    intents.presences = presences
    return intents


def create_bot(
    is_bot_token: bool = False,
    command_prefix: str = "!",
    intents_members: bool = True,
) -> commands.Bot:
    """
    Create a Discord Bot instance with appropriate settings for the installed library.

    Args:
        is_bot_token: True if using a bot token, False for user token
        command_prefix: Bot command prefix
        intents_members: Enable GUILD_MEMBERS intent (only for official discord.py with bot tokens)

    Returns:
        commands.Bot instance configured for the token type and library

    Raises:
        RuntimeError: If bot token is used with discord.py-self (not supported for member fetching)
    """
    if HAS_INTENTS:
        # Official discord.py - use Intents
        if is_bot_token:
            intents = create_intents(members=intents_members)
            return commands.Bot(command_prefix=command_prefix, intents=intents)
        else:
            # User token with official discord.py - limited support
            # Note: Official discord.py doesn't fully support user tokens
            intents = create_intents(members=False)
            return commands.Bot(command_prefix=command_prefix, intents=intents)
    else:
        # discord.py-self - no Intents, use self_bot parameter
        if is_bot_token:
            # Bot token with discord.py-self - limited member fetching capability
            # Warning: Member chunking won't work without Intents
            return commands.Bot(command_prefix=command_prefix, self_bot=False)
        else:
            # User token with discord.py-self - full support
            return commands.Bot(command_prefix=command_prefix, self_bot=True)


def get_library_info() -> dict:
    """
    Get information about the installed Discord library.

    Returns:
        Dict with library details
    """
    return {
        "library": DISCORD_LIB,
        "version": discord.__version__,
        "has_intents": HAS_INTENTS,
        "has_self_bot": HAS_SELF_BOT,
        "supports_bot_token_members": HAS_INTENTS,  # Only official discord.py with Intents
        "supports_user_token": HAS_SELF_BOT or not HAS_INTENTS,  # discord.py-self
    }


def check_token_compatibility(is_bot_token: bool, require_members: bool = True) -> tuple[bool, str]:
    """
    Check if the current library supports the given token type for the required features.

    Args:
        is_bot_token: True if using a bot token
        require_members: True if member list fetching is required

    Returns:
        Tuple of (is_compatible, message)
    """
    if is_bot_token and require_members:
        if not HAS_INTENTS:
            return (
                False,
                f"Bot tokens require official discord.py for member fetching (Intents required). "
                f"Currently using {DISCORD_LIB}. Install discord.py: pip install discord.py"
            )
        return (True, "Bot token with member fetching supported via Gateway Intents")

    if not is_bot_token:
        if HAS_INTENTS and not HAS_SELF_BOT:
            return (
                False,
                f"User tokens require discord.py-self. "
                f"Currently using {DISCORD_LIB}. Install discord.py-self: pip install discord.py-self"
            )
        return (True, "User token supported via discord.py-self")

    return (True, f"Token type supported by {DISCORD_LIB}")


# Export version info
__all__ = [
    'DISCORD_LIB',
    'HAS_INTENTS',
    'HAS_SELF_BOT',
    'create_bot',
    'create_intents',
    'get_library_info',
    'check_token_compatibility',
]

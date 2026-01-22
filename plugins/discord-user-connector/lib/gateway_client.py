"""
Gateway WebSocket client for fetching complete member lists.

Uses Discord Gateway API's REQUEST_GUILD_MEMBERS operation for
efficient retrieval of large member lists (100k+ members).

Supports both discord.py (official) and discord.py-self libraries:
- discord.py: For bot tokens with Gateway Intents
- discord.py-self: For user tokens (self-bot)
"""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

import discord
from discord.ext import commands

from .config import get_config
from .member_models import MemberBasic
from .discord_compat import (
    DISCORD_LIB,
    HAS_INTENTS,
    create_bot,
    check_token_compatibility,
    get_library_info,
)


class GatewayClientError(Exception):
    """Raised when Gateway operations fail."""
    pass


class GatewayMemberFetcher:
    """
    Fetches complete member lists via Discord Gateway.

    Uses chunked member fetching for efficient retrieval of large servers.

    Library Support:
    - discord.py (official): Bot tokens with GUILD_MEMBERS intent
    - discord.py-self: User tokens (self-bot mode)
    """

    def __init__(self):
        """Initialize the Gateway member fetcher."""
        self._config = get_config()
        self._bot: Optional[commands.Bot] = None
        self._ready = asyncio.Event()
        self._members: list[MemberBasic] = []
        self._chunk_complete = asyncio.Event()
        self._chunks_received = 0
        self._total_chunks = 0
        self._is_bot_token = self._config.is_bot_token

        # Check token compatibility with installed library
        is_compatible, message = check_token_compatibility(
            is_bot_token=self._is_bot_token,
            require_members=True
        )
        if not is_compatible:
            raise GatewayClientError(message)

    async def _ensure_connected(self) -> commands.Bot:
        """Ensure client is connected and return the bot instance."""
        if self._bot is not None and self._bot.is_ready():
            return self._bot

        # Create bot using compatibility layer
        # This handles the differences between discord.py and discord.py-self
        self._bot = create_bot(
            is_bot_token=self._is_bot_token,
            command_prefix="!",
            intents_members=True  # Request GUILD_MEMBERS intent if using official discord.py
        )

        @self._bot.event
        async def on_ready():
            self._ready.set()

        # Start bot in background
        token = self._config.discord_token
        try:
            asyncio.create_task(self._bot.start(token))
            # Wait for ready with timeout
            await asyncio.wait_for(self._ready.wait(), timeout=30.0)
        except discord.LoginFailure as e:
            raise GatewayClientError(f"Discord authentication failed: {e}") from e
        except asyncio.TimeoutError:
            raise GatewayClientError("Timed out connecting to Discord")

        return self._bot

    async def close(self):
        """Close the client connection."""
        if self._bot is not None:
            await self._bot.close()
            self._bot = None
            self._ready.clear()

    async def fetch_all_members(
        self,
        server_id: str,
        include_bots: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[MemberBasic]:
        """
        Fetch all members from a server using Gateway chunking.

        This method is optimized for large servers (100k+ members).

        Args:
            server_id: Discord server ID
            include_bots: Whether to include bot accounts
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of MemberBasic objects

        Raises:
            GatewayClientError: If fetching fails
        """
        bot = await self._ensure_connected()

        guild = bot.get_guild(int(server_id))
        if guild is None:
            raise GatewayClientError(f"Server {server_id} not found")

        members: list[MemberBasic] = []

        # Method 1: Use guild.chunk() if available (discord.py method)
        # This triggers the chunking process via Gateway
        try:
            if not guild.chunked:
                # Request all members via Gateway
                await guild.chunk(cache=True)
        except Exception as e:
            # If chunk fails, fall back to guild.members iteration
            pass

        # Now iterate over cached members
        total_estimate = guild.member_count or len(guild.members)
        current = 0

        for member in guild.members:
            # Skip bots if requested
            if not include_bots and member.bot:
                current += 1
                continue

            member_basic = self._member_to_basic(member)
            members.append(member_basic)
            current += 1

            # Progress callback
            if progress_callback and current % 1000 == 0:
                progress_callback(current, total_estimate)

        # Final progress update
        if progress_callback:
            progress_callback(len(members), len(members))

        return members

    async def fetch_members_chunked(
        self,
        server_id: str,
        include_bots: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[MemberBasic]:
        """
        Alternative method using fetch_members() if available.

        This provides finer control over the fetching process.

        Args:
            server_id: Discord server ID
            include_bots: Whether to include bot accounts
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of MemberBasic objects
        """
        bot = await self._ensure_connected()

        guild = bot.get_guild(int(server_id))
        if guild is None:
            raise GatewayClientError(f"Server {server_id} not found")

        members: list[MemberBasic] = []
        total_estimate = guild.member_count or 0
        current = 0

        # Use fetch_members if available (async generator)
        try:
            async for member in guild.fetch_members(limit=None):
                # Skip bots if requested
                if not include_bots and member.bot:
                    current += 1
                    continue

                member_basic = self._member_to_basic(member)
                members.append(member_basic)
                current += 1

                # Progress callback
                if progress_callback and current % 500 == 0:
                    progress_callback(current, total_estimate)

        except Exception as e:
            # Fall back to regular method if fetch_members fails
            return await self.fetch_all_members(
                server_id,
                include_bots=include_bots,
                progress_callback=progress_callback
            )

        # Final progress update
        if progress_callback:
            progress_callback(len(members), len(members))

        return members

    def _member_to_basic(self, member: discord.Member) -> MemberBasic:
        """Convert discord.Member to MemberBasic dataclass."""
        # Extract account creation time from snowflake ID
        account_created = discord.utils.snowflake_time(member.id)

        # Get roles (excluding @everyone)
        roles = [role.name for role in member.roles if role.name != "@everyone"]

        # Get avatar URL
        avatar_url = None
        if member.avatar:
            avatar_url = str(member.avatar.url)
        elif member.default_avatar:
            avatar_url = str(member.default_avatar.url)

        return MemberBasic(
            user_id=str(member.id),
            username=member.name,
            display_name=member.display_name,
            discriminator=str(member.discriminator) if hasattr(member, 'discriminator') else "0",
            avatar_url=avatar_url,
            joined_at=member.joined_at.replace(tzinfo=timezone.utc) if member.joined_at else None,
            roles=roles,
            nickname=member.nick,
            pending=member.pending if hasattr(member, 'pending') else False,
            is_bot=member.bot,
            account_created_at=account_created.replace(tzinfo=timezone.utc),
        )

    async def get_guild_info(self, server_id: str) -> dict:
        """
        Get basic guild information.

        Args:
            server_id: Discord server ID

        Returns:
            Dict with server info: id, name, icon_url, member_count
        """
        bot = await self._ensure_connected()

        guild = bot.get_guild(int(server_id))
        if guild is None:
            raise GatewayClientError(f"Server {server_id} not found")

        icon_url = None
        if guild.icon:
            icon_url = str(guild.icon.url)

        return {
            "id": str(guild.id),
            "name": guild.name,
            "icon_url": icon_url,
            "member_count": guild.member_count or len(guild.members),
        }


class RichProfileFetcher:
    """
    Fetches rich profile data using User Token REST API.

    Rich profile includes: bio, pronouns, connected accounts, badges.
    This data is only available via User Token (selfbot) with discord.py-self.
    """

    def __init__(self):
        """Initialize the rich profile fetcher."""
        self._config = get_config()
        self._bot: Optional[commands.Bot] = None
        self._ready = asyncio.Event()

        # Rich profiles require user token and discord.py-self
        if HAS_INTENTS and not hasattr(commands.Bot, 'self_bot'):
            raise GatewayClientError(
                "Rich profile fetching requires discord.py-self (user token). "
                "Install it with: pip install discord.py-self"
            )

    async def _ensure_connected(self) -> commands.Bot:
        """Ensure client is connected."""
        if self._bot is not None and self._bot.is_ready():
            return self._bot

        # Rich profiles always require user token with discord.py-self
        self._bot = create_bot(
            is_bot_token=False,  # Always use user token mode for rich profiles
            command_prefix="!",
        )

        @self._bot.event
        async def on_ready():
            self._ready.set()

        token = self._config.discord_token
        try:
            asyncio.create_task(self._bot.start(token))
            await asyncio.wait_for(self._ready.wait(), timeout=30.0)
        except Exception as e:
            raise GatewayClientError(f"Failed to connect: {e}") from e

        return self._bot

    async def close(self):
        """Close the client connection."""
        if self._bot is not None:
            await self._bot.close()
            self._bot = None
            self._ready.clear()

    async def fetch_user_profile(self, user_id: str, server_id: str) -> dict:
        """
        Fetch rich profile data for a user.

        Args:
            user_id: Discord user ID
            server_id: Discord server ID (for context)

        Returns:
            Dict with rich profile data: bio, pronouns, connected_accounts, badges

        Note:
            This requires User Token. Bot Token will return limited data.
        """
        bot = await self._ensure_connected()

        try:
            # Get user profile via REST API
            # discord.py-self provides access to profile endpoint
            user = await bot.fetch_user(int(user_id))

            profile_data = {
                "bio": None,
                "pronouns": None,
                "connected_accounts": [],
                "badges": [],
            }

            # Try to fetch profile if method exists
            if hasattr(user, 'profile'):
                try:
                    profile = await user.profile()
                    profile_data["bio"] = profile.bio if hasattr(profile, 'bio') else None
                    profile_data["pronouns"] = profile.pronouns if hasattr(profile, 'pronouns') else None

                    # Connected accounts
                    if hasattr(profile, 'connected_accounts'):
                        for account in profile.connected_accounts:
                            profile_data["connected_accounts"].append({
                                "platform": account.type.value if hasattr(account, 'type') else "unknown",
                                "name": account.name if hasattr(account, 'name') else "",
                                "verified": account.verified if hasattr(account, 'verified') else False,
                            })

                    # Badges
                    if hasattr(profile, 'badges'):
                        profile_data["badges"] = [str(badge) for badge in profile.badges]

                except Exception:
                    # Profile fetch failed, return basic data
                    pass

            # Extract public badges from user flags if available
            if hasattr(user, 'public_flags'):
                flags = user.public_flags
                if flags.hypesquad_bravery:
                    profile_data["badges"].append("HypeSquad Bravery")
                if flags.hypesquad_brilliance:
                    profile_data["badges"].append("HypeSquad Brilliance")
                if flags.hypesquad_balance:
                    profile_data["badges"].append("HypeSquad Balance")
                if flags.early_supporter:
                    profile_data["badges"].append("Early Supporter")
                if flags.verified_bot_developer:
                    profile_data["badges"].append("Verified Bot Developer")
                if flags.active_developer:
                    profile_data["badges"].append("Active Developer")

            return profile_data

        except Exception as e:
            raise GatewayClientError(f"Failed to fetch profile for user {user_id}: {e}") from e

    async def fetch_profiles_batch(
        self,
        user_ids: list[str],
        server_id: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        delay_between_requests: float = 0.5
    ) -> dict[str, dict]:
        """
        Fetch rich profiles for multiple users with rate limiting.

        Args:
            user_ids: List of user IDs to fetch
            server_id: Server ID for context
            progress_callback: Optional callback(current, total)
            delay_between_requests: Delay between requests to avoid rate limits

        Returns:
            Dict mapping user_id to profile data
        """
        results = {}
        total = len(user_ids)

        for i, user_id in enumerate(user_ids):
            try:
                profile = await self.fetch_user_profile(user_id, server_id)
                results[user_id] = profile
            except Exception:
                results[user_id] = None

            if progress_callback:
                progress_callback(i + 1, total)

            # Rate limit delay
            if i < total - 1:
                await asyncio.sleep(delay_between_requests)

        return results

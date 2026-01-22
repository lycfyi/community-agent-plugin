"""
HTTP API client for Discord Bot plugin.

Uses direct HTTP API calls via aiohttp to avoid discord.py library namespace conflicts.
This allows the plugin to work even when discord.py-self is installed.
"""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

import aiohttp

from .config import get_config
from .member_models import MemberBasic


# Discord API base URL
API_BASE = "https://discord.com/api/v10"


class GatewayClientError(Exception):
    """Raised when API operations fail."""
    pass


def _snowflake_to_datetime(snowflake_id: int) -> datetime:
    """Convert Discord snowflake ID to datetime."""
    # Discord epoch (2015-01-01T00:00:00.000Z)
    DISCORD_EPOCH = 1420070400000
    timestamp = ((snowflake_id >> 22) + DISCORD_EPOCH) / 1000.0
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


class GatewayMemberFetcher:
    """
    Fetches complete member lists via Discord HTTP API.

    Uses REST API pagination for reliable member fetching.
    Requires bot token with SERVER MEMBERS INTENT enabled.
    """

    def __init__(self, data_dir: str = "."):
        """Initialize the HTTP API member fetcher."""
        self._config = get_config(data_dir)
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_headers(self) -> dict:
        """Get authorization headers for API requests."""
        return {
            "Authorization": f"Bot {self._config.bot_token}",
            "Content-Type": "application/json",
        }

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _api_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an API request to Discord."""
        session = await self._ensure_session()
        url = f"{API_BASE}{endpoint}"

        async with session.request(method, url, headers=self._get_headers(), **kwargs) as resp:
            if resp.status == 401:
                raise GatewayClientError(
                    "Authentication failed. Check your bot token in .env"
                )
            if resp.status == 403:
                raise GatewayClientError(
                    "Forbidden. Bot may lack SERVER MEMBERS INTENT or permissions."
                )
            if resp.status == 404:
                raise GatewayClientError(
                    "Not found. Is the bot in the server?"
                )
            if resp.status == 429:
                # Rate limited - wait and retry
                retry_after = float(resp.headers.get("Retry-After", 1))
                await asyncio.sleep(retry_after)
                return await self._api_request(method, endpoint, **kwargs)

            if not resp.ok:
                text = await resp.text()
                raise GatewayClientError(f"API error {resp.status}: {text}")

            return await resp.json()

    async def fetch_all_members(
        self,
        server_id: str,
        include_bots: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[MemberBasic]:
        """
        Fetch all members from a server using HTTP API pagination.

        Args:
            server_id: Discord server ID
            include_bots: Whether to include bot accounts
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of MemberBasic objects

        Raises:
            GatewayClientError: If fetching fails
        """
        # First get guild info for member count estimate
        guild_info = await self.get_guild_info(server_id)
        total_estimate = guild_info.get("member_count", 0)

        members: list[MemberBasic] = []
        after = "0"  # Start from beginning (snowflake 0)

        while True:
            # Fetch batch of members (max 1000 per request)
            endpoint = f"/guilds/{server_id}/members?limit=1000&after={after}"

            try:
                batch = await self._api_request("GET", endpoint)
            except GatewayClientError as e:
                if "Forbidden" in str(e):
                    raise GatewayClientError(
                        f"Cannot fetch members. Make sure:\n"
                        f"  1. Bot has SERVER MEMBERS INTENT enabled in Developer Portal\n"
                        f"  2. Bot has 'Read Members' permission in the server"
                    ) from e
                raise

            if not batch:
                break

            # Process members
            for member_data in batch:
                user_data = member_data.get("user", {})
                is_bot = user_data.get("bot", False)

                # Skip bots if not requested
                if not include_bots and is_bot:
                    continue

                member_basic = self._member_from_api(member_data)
                members.append(member_basic)

            # Progress callback
            if progress_callback:
                progress_callback(len(members), total_estimate)

            # Get next page cursor
            if len(batch) < 1000:
                # No more members
                break

            # Use last member's ID as cursor for next page
            last_user_id = batch[-1]["user"]["id"]
            after = last_user_id

        # Final progress update
        if progress_callback:
            progress_callback(len(members), len(members))

        return members

    def _member_from_api(self, member_data: dict) -> MemberBasic:
        """Convert API member response to MemberBasic dataclass."""
        user_data = member_data.get("user", {})
        user_id = user_data.get("id", "")

        # Parse joined_at
        joined_at = None
        if member_data.get("joined_at"):
            try:
                joined_at = datetime.fromisoformat(
                    member_data["joined_at"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Get avatar URL
        avatar_hash = user_data.get("avatar")
        avatar_url = None
        if avatar_hash:
            ext = "gif" if avatar_hash.startswith("a_") else "png"
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}"

        # Get roles
        roles = member_data.get("roles", [])

        # Account creation from snowflake
        account_created = _snowflake_to_datetime(int(user_id)) if user_id else None

        return MemberBasic(
            user_id=user_id,
            username=user_data.get("username", ""),
            display_name=user_data.get("global_name") or user_data.get("username", ""),
            discriminator=user_data.get("discriminator", "0"),
            avatar_url=avatar_url,
            joined_at=joined_at,
            roles=roles,  # Note: these are role IDs, not names
            nickname=member_data.get("nick"),
            pending=member_data.get("pending", False),
            is_bot=user_data.get("bot", False),
            account_created_at=account_created,
        )

    async def get_guild_info(self, server_id: str) -> dict:
        """
        Get basic guild information.

        Args:
            server_id: Discord server ID

        Returns:
            Dict with server info: id, name, icon_url, member_count
        """
        endpoint = f"/guilds/{server_id}?with_counts=true"
        data = await self._api_request("GET", endpoint)

        icon_hash = data.get("icon")
        icon_url = None
        if icon_hash:
            ext = "gif" if icon_hash.startswith("a_") else "png"
            icon_url = f"https://cdn.discordapp.com/icons/{server_id}/{icon_hash}.{ext}"

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "icon_url": icon_url,
            "member_count": data.get("approximate_member_count", 0),
        }

    async def list_guilds(self) -> list[dict]:
        """
        List all guilds the bot is in.

        Returns:
            List of dicts with guild info
        """
        # Use /users/@me/guilds to list bot's guilds
        endpoint = "/users/@me/guilds"
        guilds_data = await self._api_request("GET", endpoint)

        guilds = []
        for guild in guilds_data:
            # Get full guild info for member count
            try:
                full_info = await self.get_guild_info(guild["id"])
                guilds.append({
                    "id": guild["id"],
                    "name": guild["name"],
                    "member_count": full_info.get("member_count", 0),
                })
            except GatewayClientError:
                # Fallback if can't get full info
                guilds.append({
                    "id": guild["id"],
                    "name": guild["name"],
                    "member_count": 0,
                })

        return guilds

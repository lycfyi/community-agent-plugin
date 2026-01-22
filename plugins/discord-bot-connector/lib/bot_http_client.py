"""
HTTP API client for Discord Bot token message syncing.

Uses direct HTTP API calls via aiohttp for message fetching with bot tokens.
This provides higher rate limits and official API compliance compared to user tokens.

Works alongside discord.py-self - uses aiohttp for direct API calls to avoid
library namespace conflicts.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, List, Optional

import aiohttp


# Discord API base URL
API_BASE = "https://discord.com/api/v10"

# Discord epoch (2015-01-01T00:00:00.000Z) in milliseconds
DISCORD_EPOCH = 1420070400000


class BotHttpClientError(Exception):
    """Raised when API operations fail."""
    pass


class BotAuthenticationError(BotHttpClientError):
    """Raised when authentication fails."""
    pass


def _datetime_to_snowflake(dt: datetime) -> int:
    """Convert datetime to Discord snowflake ID."""
    timestamp_ms = int(dt.timestamp() * 1000)
    return (timestamp_ms - DISCORD_EPOCH) << 22


class BotHttpClient:
    """
    HTTP-based Discord client using bot token.

    Provides message syncing with higher rate limits than user tokens.
    Uses direct aiohttp calls to Discord REST API.

    Capabilities:
    - list_guilds(): List servers the bot is in
    - list_channels(): List text channels in a server
    - fetch_messages(): Fetch messages from a channel (async iterator)

    Limitations:
    - Cannot access DMs (bots can't read user DMs)
    - Requires bot to be added to server with appropriate permissions
    """

    def __init__(self, bot_token: Optional[str] = None):
        """Initialize the bot HTTP client.

        Args:
            bot_token: Discord bot token. If not provided, reads from
                       DISCORD_BOT_TOKEN environment variable.

        Raises:
            BotAuthenticationError: If no bot token is available.
        """
        self._token = bot_token or os.getenv("DISCORD_BOT_TOKEN")
        if not self._token:
            raise BotAuthenticationError(
                "No bot token available. Set DISCORD_BOT_TOKEN in .env"
            )
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_headers(self) -> dict:
        """Get authorization headers for API requests."""
        return {
            "Authorization": f"Bot {self._token}",
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

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """Make an API request to Discord.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            max_retries: Maximum number of retries for rate limits
            **kwargs: Additional arguments to pass to aiohttp

        Returns:
            JSON response from API

        Raises:
            BotAuthenticationError: If authentication fails
            BotHttpClientError: For other API errors
        """
        session = await self._ensure_session()
        url = f"{API_BASE}{endpoint}"
        retries = 0

        while retries <= max_retries:
            async with session.request(
                method, url, headers=self._get_headers(), **kwargs
            ) as resp:
                if resp.status == 401:
                    raise BotAuthenticationError(
                        "Bot token authentication failed. Check DISCORD_BOT_TOKEN in .env"
                    )
                if resp.status == 403:
                    raise BotHttpClientError(
                        "Forbidden. Bot may lack required permissions in this server."
                    )
                if resp.status == 404:
                    raise BotHttpClientError(
                        "Not found. Is the bot in the server?"
                    )
                if resp.status == 429:
                    # Rate limited - wait and retry
                    retry_after = float(resp.headers.get("Retry-After", 1))
                    if retries < max_retries:
                        await asyncio.sleep(retry_after)
                        retries += 1
                        continue
                    raise BotHttpClientError(
                        f"Rate limited. Retry after {retry_after}s"
                    )

                if not resp.ok:
                    text = await resp.text()
                    raise BotHttpClientError(f"API error {resp.status}: {text}")

                return await resp.json()

        raise BotHttpClientError("Max retries exceeded")

    async def list_guilds(self) -> List[dict]:
        """List all guilds (servers) the bot is in.

        Returns:
            List of guild info dicts with id, name, icon, member_count
        """
        # Use /users/@me/guilds to list bot's guilds
        guilds_data = await self._api_request("GET", "/users/@me/guilds")

        guilds = []
        for guild in guilds_data:
            # Get full guild info for member count
            try:
                full_info = await self._get_guild_info(guild["id"])
                guilds.append({
                    "id": guild["id"],
                    "name": guild["name"],
                    "icon": full_info.get("icon_url"),
                    "member_count": full_info.get("member_count", 0),
                })
            except BotHttpClientError:
                # Fallback if can't get full info
                guilds.append({
                    "id": guild["id"],
                    "name": guild["name"],
                    "icon": None,
                    "member_count": 0,
                })

        return guilds

    async def _get_guild_info(self, server_id: str) -> dict:
        """Get basic guild information.

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

    async def list_channels(self, server_id: str) -> List[dict]:
        """List text channels in a server.

        Args:
            server_id: Discord server/guild ID

        Returns:
            List of channel info dicts with id, name, type, category, position
        """
        endpoint = f"/guilds/{server_id}/channels"
        channels_data = await self._api_request("GET", endpoint)

        # Filter to text channels only (type 0)
        # Also include news channels (type 5) which can contain messages
        text_types = {0, 5}

        channels = []
        # Build category map for looking up parent names
        category_map = {
            c["id"]: c["name"]
            for c in channels_data
            if c.get("type") == 4  # Category type
        }

        for channel in channels_data:
            if channel.get("type") in text_types:
                parent_id = channel.get("parent_id")
                channels.append({
                    "id": channel["id"],
                    "name": channel["name"],
                    "type": "text" if channel["type"] == 0 else "news",
                    "category": category_map.get(parent_id) if parent_id else None,
                    "position": channel.get("position", 999),
                })

        # Sort by position
        channels.sort(key=lambda c: c["position"])
        return channels

    async def fetch_messages(
        self,
        server_id: str,
        channel_id: str,
        after_id: Optional[str] = None,
        days: int = 30,
        limit: Optional[int] = None
    ) -> AsyncIterator[dict]:
        """Fetch messages from a channel.

        Args:
            server_id: Discord server ID (required for API compatibility,
                       but not used in REST API calls)
            channel_id: Discord channel ID
            after_id: Only fetch messages after this message ID
            days: Number of days of history to fetch (if no after_id)
            limit: Maximum number of messages to fetch

        Yields:
            Message dicts with full metadata matching DiscordUserClient format
        """
        # Determine starting point
        if after_id:
            after = after_id
        else:
            # Calculate snowflake for N days ago
            after_time = datetime.now(timezone.utc) - timedelta(days=days)
            after = str(_datetime_to_snowflake(after_time))

        count = 0
        batch_limit = min(100, limit) if limit else 100  # API max is 100

        while True:
            # Fetch batch of messages
            endpoint = f"/channels/{channel_id}/messages?limit={batch_limit}&after={after}"
            try:
                batch = await self._api_request("GET", endpoint)
            except BotHttpClientError as e:
                if "403" in str(e) or "Forbidden" in str(e):
                    raise BotHttpClientError(
                        f"Cannot read messages from channel {channel_id}. "
                        f"Bot needs 'Read Message History' permission."
                    )
                raise

            if not batch:
                break

            # API returns newest first, we want oldest first
            batch.reverse()

            for msg_data in batch:
                yield self._message_to_dict(msg_data)
                count += 1

                if limit and count >= limit:
                    return

            # If we got fewer than requested, we've reached the end
            if len(batch) < batch_limit:
                break

            # Use last message ID as cursor for next page (oldest in original order)
            # Since we reversed, the last message is actually the newest
            after = batch[-1]["id"]

    def _message_to_dict(self, msg_data: dict) -> dict:
        """Convert API message response to dict matching DiscordUserClient format.

        Args:
            msg_data: Raw message data from Discord API

        Returns:
            Message dict with standardized fields
        """
        author = msg_data.get("author", {})

        # Extract reply info
        reply_to_id = None
        reply_to_author = None
        ref = msg_data.get("message_reference")
        if ref:
            reply_to_id = ref.get("message_id")
            # Try to get author from referenced_message if available
            ref_msg = msg_data.get("referenced_message")
            if ref_msg and ref_msg.get("author"):
                reply_to_author = ref_msg["author"].get("global_name") or ref_msg["author"].get("username")

        # Extract attachments
        attachments = []
        for att in msg_data.get("attachments", []):
            attachments.append({
                "id": att.get("id"),
                "filename": att.get("filename"),
                "url": att.get("url"),
                "size": att.get("size"),
                "content_type": att.get("content_type"),
            })

        # Extract embeds
        embeds = []
        for embed in msg_data.get("embeds", []):
            thumbnail = embed.get("thumbnail", {})
            embeds.append({
                "type": embed.get("type"),
                "title": embed.get("title"),
                "description": embed.get("description"),
                "url": embed.get("url"),
                "thumbnail": thumbnail.get("url") if thumbnail else None,
            })

        # Extract reactions
        reactions = []
        for reaction in msg_data.get("reactions", []):
            emoji = reaction.get("emoji", {})
            # Format emoji as string (custom emoji format: <:name:id>)
            if emoji.get("id"):
                emoji_str = f"<:{emoji.get('name')}:{emoji.get('id')}>"
            else:
                emoji_str = emoji.get("name", "")
            reactions.append({
                "emoji": emoji_str,
                "count": reaction.get("count", 0),
            })

        # Get avatar URL
        avatar_hash = author.get("avatar")
        avatar_url = None
        if avatar_hash:
            user_id = author.get("id")
            ext = "gif" if avatar_hash.startswith("a_") else "png"
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}"

        return {
            "id": msg_data.get("id"),
            "channel_id": msg_data.get("channel_id"),
            "author_id": author.get("id"),
            "author_name": author.get("global_name") or author.get("username"),
            "author_avatar": avatar_url,
            "content": msg_data.get("content", ""),
            "timestamp": msg_data.get("timestamp"),
            "edited_at": msg_data.get("edited_timestamp"),
            "reply_to_id": reply_to_id,
            "reply_to_author": reply_to_author,
            "attachments": attachments,
            "embeds": embeds,
            "reactions": reactions,
        }

    async def check_channel_access(self, server_id: str, channel_id: str) -> bool:
        """Check if bot has read access to a specific channel.

        Args:
            server_id: Discord server ID
            channel_id: Discord channel ID

        Returns:
            True if bot can read messages from the channel
        """
        try:
            # Try to fetch 1 message - if it works, we have access
            endpoint = f"/channels/{channel_id}/messages?limit=1"
            await self._api_request("GET", endpoint)
            return True
        except BotHttpClientError:
            return False

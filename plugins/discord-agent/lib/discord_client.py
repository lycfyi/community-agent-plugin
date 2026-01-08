"""Discord user token client with self_bot=True."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, List, Optional

import discord
from discord.ext import commands

from .config import get_config
from .rate_limiter import RateLimiter


class DiscordClientError(Exception):
    """Discord client error."""
    pass


class AuthenticationError(DiscordClientError):
    """Authentication failed - token may be invalid or expired."""
    pass


class DiscordUserClient:
    """Discord client using user token authentication."""

    def __init__(self):
        """Initialize the Discord user client."""
        self._config = get_config()
        self._rate_limiter = RateLimiter()
        self._bot: Optional[commands.Bot] = None
        self._ready = asyncio.Event()

    async def _ensure_connected(self) -> commands.Bot:
        """Ensure client is connected and return the bot instance."""
        if self._bot is not None and self._bot.is_ready():
            return self._bot

        # Create new bot instance for user token (discord.py-self)
        self._bot = commands.Bot(
            command_prefix="!",
            self_bot=True
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
            raise AuthenticationError(
                f"Failed to authenticate with Discord. "
                f"Your token may be invalid or expired.\n"
                f"To get a new token:\n"
                f"1. Open Discord in your browser\n"
                f"2. Press F12 for Developer Tools\n"
                f"3. Go to Network tab\n"
                f"4. Perform any action in Discord\n"
                f"5. Find a request to discord.com/api\n"
                f"6. Copy the 'Authorization' header value\n"
                f"Original error: {e}"
            ) from e
        except asyncio.TimeoutError:
            raise DiscordClientError(
                "Timed out connecting to Discord. Check your network connection."
            )

        return self._bot

    async def close(self):
        """Close the client connection."""
        if self._bot is not None:
            await self._bot.close()
            self._bot = None
            self._ready.clear()

    async def list_guilds(self) -> List[dict]:
        """List all accessible servers (guilds).

        Returns:
            List of guild info dicts with id, name, icon, member_count
        """
        bot = await self._ensure_connected()

        guilds = []
        for guild in bot.guilds:
            guilds.append({
                "id": str(guild.id),
                "name": guild.name,
                "icon": str(guild.icon.url) if guild.icon else None,
                "member_count": guild.member_count or 0
            })

        return guilds

    async def list_channels(self, server_id: str, check_access: bool = False) -> List[dict]:
        """List text channels in a server.

        Args:
            server_id: Discord server/guild ID
            check_access: If True, include 'accessible' field indicating read permission

        Returns:
            List of channel info dicts with id, name, type, category, position
            If check_access=True, also includes 'accessible' boolean field
        """
        bot = await self._ensure_connected()

        guild = bot.get_guild(int(server_id))
        if guild is None:
            raise DiscordClientError(
                f"Server {server_id} not found. "
                f"Make sure your account has access to this server."
            )

        channels = []
        for channel in guild.text_channels:
            channel_info = {
                "id": str(channel.id),
                "name": channel.name,
                "type": "text",
                "category": channel.category.name if channel.category else None,
                "position": channel.position
            }

            if check_access:
                # Check if we can read message history
                perms = channel.permissions_for(guild.me)
                channel_info["accessible"] = perms.read_message_history and perms.read_messages

            channels.append(channel_info)

        # Sort by position
        channels.sort(key=lambda c: c["position"])
        return channels

    async def check_channel_access(self, server_id: str, channel_id: str) -> bool:
        """Check if we have read access to a specific channel.

        Args:
            server_id: Discord server ID
            channel_id: Discord channel ID

        Returns:
            True if we can read messages from the channel
        """
        bot = await self._ensure_connected()

        guild = bot.get_guild(int(server_id))
        if guild is None:
            return False

        channel = guild.get_channel(int(channel_id))
        if channel is None:
            return False

        perms = channel.permissions_for(guild.me)
        return perms.read_message_history and perms.read_messages

    async def check_send_permission(self, channel_id: str) -> tuple[bool, str]:
        """Check if we have permission to send messages to a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Tuple of (can_send: bool, reason: str)
            If can_send is False, reason explains why
        """
        bot = await self._ensure_connected()

        channel = bot.get_channel(int(channel_id))
        if channel is None:
            return False, f"Channel {channel_id} not found"

        # Get the guild for the channel
        if not hasattr(channel, 'guild') or channel.guild is None:
            return False, "Could not determine channel's server"

        guild = channel.guild
        member = guild.me
        if member is None:
            return False, "Could not get bot member info"

        perms = channel.permissions_for(member)

        if not perms.send_messages:
            return False, f"Missing permission to send messages in #{channel.name}"

        if not perms.view_channel:
            return False, f"Cannot view channel #{channel.name}"

        return True, f"OK - can send to #{channel.name}"

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
            server_id: Discord server ID
            channel_id: Discord channel ID
            after_id: Only fetch messages after this message ID
            days: Number of days of history to fetch (if no after_id)
            limit: Maximum number of messages to fetch

        Yields:
            Message dicts with full metadata
        """
        bot = await self._ensure_connected()

        guild = bot.get_guild(int(server_id))
        if guild is None:
            raise DiscordClientError(f"Server {server_id} not found")

        channel = guild.get_channel(int(channel_id))
        if channel is None:
            raise DiscordClientError(
                f"Channel {channel_id} not found in server {server_id}"
            )

        # Determine fetch parameters
        after = None
        if after_id:
            after = discord.Object(id=int(after_id))
        else:
            # Fetch from N days ago
            after_time = datetime.now(timezone.utc) - timedelta(days=days)
            after = discord.Object(
                id=int((after_time.timestamp() * 1000 - 1420070400000) * 4194304)
            )

        count = 0
        async for message in channel.history(
            limit=limit,
            after=after,
            oldest_first=True
        ):
            # discord.py handles rate limiting internally via HTTPClient
            yield self._message_to_dict(message)
            count += 1

            if limit and count >= limit:
                break

    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to_id: Optional[str] = None
    ) -> dict:
        """Send a message to a channel.

        Args:
            channel_id: Target channel ID
            content: Message content
            reply_to_id: Optional message ID to reply to

        Returns:
            Sent message info dict
        """
        bot = await self._ensure_connected()

        channel = bot.get_channel(int(channel_id))
        if channel is None:
            raise DiscordClientError(f"Channel {channel_id} not found")

        await self._rate_limiter.wait()

        reference = None
        if reply_to_id:
            reference = discord.MessageReference(
                message_id=int(reply_to_id),
                channel_id=int(channel_id)
            )

        message = await channel.send(content, reference=reference)
        return self._message_to_dict(message)

    def _message_to_dict(self, message: discord.Message) -> dict:
        """Convert a discord.Message to a dict with all metadata."""
        # Extract reply info
        reply_to_id = None
        reply_to_author = None
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if isinstance(ref, discord.Message):
                reply_to_id = str(ref.id)
                reply_to_author = ref.author.display_name

        # Extract attachments
        attachments = []
        for att in message.attachments:
            attachments.append({
                "id": str(att.id),
                "filename": att.filename,
                "url": att.url,
                "size": att.size,
                "content_type": att.content_type
            })

        # Extract embeds
        embeds = []
        for embed in message.embeds:
            embeds.append({
                "type": embed.type,
                "title": embed.title,
                "description": embed.description,
                "url": embed.url,
                "thumbnail": str(embed.thumbnail.url) if embed.thumbnail else None
            })

        # Extract reactions
        reactions = []
        for reaction in message.reactions:
            reactions.append({
                "emoji": str(reaction.emoji),
                "count": reaction.count
            })

        return {
            "id": str(message.id),
            "channel_id": str(message.channel.id),
            "author_id": str(message.author.id),
            "author_name": message.author.display_name,
            "author_avatar": str(message.author.avatar.url) if message.author.avatar else None,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "reply_to_id": reply_to_id,
            "reply_to_author": reply_to_author,
            "attachments": attachments,
            "embeds": embeds,
            "reactions": reactions
        }

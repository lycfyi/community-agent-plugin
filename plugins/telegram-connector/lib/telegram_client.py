"""Telegram client implementation using Telethon.

Implements ITelegramClient contract from specs/003-telegram-integrate/contracts/telegram_client.py
"""

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator, List, Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionExpiredError,
    AuthKeyUnregisteredError,
    FloodWaitError,
    ChatAdminRequiredError,
    ChannelPrivateError,
    UserBannedInChannelError,
)
from telethon.tl.types import (
    User,
    Chat,
    Channel,
    Message,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    DocumentAttributeFilename,
    DocumentAttributeAudio,
    DocumentAttributeVideo,
    DocumentAttributeSticker,
    DocumentAttributeAnimated,
    PeerUser,
    PeerChat,
    PeerChannel,
)

from .config import get_config
from .rate_limiter import get_rate_limiter


class TelegramClientError(Exception):
    """Base exception for Telegram client errors."""
    pass


class AuthenticationError(TelegramClientError):
    """Session invalid or expired."""
    pass


class RateLimitError(TelegramClientError):
    """Rate limited by Telegram API."""
    def __init__(self, wait_seconds: int):
        self.wait_seconds = wait_seconds
        super().__init__(f"Rate limited. Wait {wait_seconds} seconds.")


class PermissionError(TelegramClientError):
    """No permission to access resource."""
    pass


class TelegramUserClient:
    """Telegram client implementation using user account authentication."""

    def __init__(self):
        """Initialize the Telegram client (not connected yet)."""
        self._client: Optional[TelegramClient] = None
        self._config = get_config()
        self._rate_limiter = get_rate_limiter()
        self._me: Optional[dict] = None

    async def connect(self) -> None:
        """Connect to Telegram using session string.

        Raises:
            AuthenticationError: If session is invalid or expired.
            TelegramClientError: For other connection failures.
        """
        try:
            session = StringSession(self._config.session_string)
            self._client = TelegramClient(
                session,
                self._config.api_id,
                self._config.api_hash
            )
            await self._client.connect()

            if not await self._client.is_user_authorized():
                raise AuthenticationError(
                    "Session is not authorized. "
                    "Generate a new session string using scripts/generate_session.py"
                )

            # Cache user info
            me = await self._client.get_me()
            self._me = {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "last_name": me.last_name,
            }

        except (SessionExpiredError, AuthKeyUnregisteredError) as e:
            raise AuthenticationError(
                f"Session expired or revoked: {e}. "
                "Generate a new session string using scripts/generate_session.py"
            )
        except Exception as e:
            raise TelegramClientError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """Disconnect from Telegram gracefully."""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    def _ensure_connected(self) -> None:
        """Ensure client is connected."""
        if not self._client or not self._client.is_connected():
            raise TelegramClientError("Not connected to Telegram. Call connect() first.")

    def _get_entity_type(self, entity) -> str:
        """Determine the type of a Telegram entity."""
        if isinstance(entity, User):
            return "private"
        elif isinstance(entity, Chat):
            return "group"
        elif isinstance(entity, Channel):
            if entity.broadcast:
                return "channel"
            return "supergroup"
        return "unknown"

    async def list_dialogs(self) -> List[dict]:
        """List all accessible groups/channels/chats.

        Returns:
            List of GroupInfo dicts with id, name, type, member_count.

        Raises:
            TelegramClientError: If not connected.
        """
        self._ensure_connected()

        await self._rate_limiter.wait()

        groups = []
        async for dialog in self._client.iter_dialogs():
            entity = dialog.entity

            # Skip private chats for now (can be enabled later)
            if isinstance(entity, User):
                continue

            entity_type = self._get_entity_type(entity)

            # Get member count (may require additional API call for some entities)
            member_count = 0
            if hasattr(entity, "participants_count"):
                member_count = entity.participants_count or 0

            # Check for forum topics (supergroups only)
            has_topics = False
            if isinstance(entity, Channel) and hasattr(entity, "forum"):
                has_topics = entity.forum or False

            groups.append({
                "id": entity.id,
                "name": getattr(entity, "title", str(entity.id)),
                "type": entity_type,
                "username": getattr(entity, "username", None),
                "member_count": member_count,
                "has_topics": has_topics,
            })

        return groups

    async def _resolve_entity_from_dialogs(self, entity_id: int):
        """Try to resolve entity by scanning dialogs.

        This is more reliable than get_entity() for groups/channels
        because iter_dialogs() properly resolves all entity types.

        Args:
            entity_id: The entity ID to find (can be positive or negative)

        Returns:
            The resolved entity, or None if not found
        """
        try:
            # Normalize ID for comparison (some APIs return negative IDs for channels)
            target_id = abs(entity_id)

            async for dialog in self._client.iter_dialogs():
                dialog_id = abs(dialog.entity.id)
                if dialog_id == target_id:
                    return dialog.entity
        except Exception:
            pass
        return None

    async def get_group(self, group_id: int, entity_type: str = None) -> dict:
        """Get information about a specific group.

        Args:
            group_id: Telegram entity ID.
            entity_type: Optional type hint ('group', 'supergroup', 'channel')
                        to help resolve the entity correctly.

        Returns:
            GroupInfo dict.

        Raises:
            PermissionError: If no access to group.
            TelegramClientError: If group not found.
        """
        self._ensure_connected()

        await self._rate_limiter.wait()

        try:
            entity = None

            # Strategy 1: If entity_type is known, use proper Peer type
            if entity_type == "group":
                try:
                    entity = await self._client.get_entity(PeerChat(abs(group_id)))
                except Exception:
                    pass
            elif entity_type in ("supergroup", "channel"):
                try:
                    entity = await self._client.get_entity(PeerChannel(abs(group_id)))
                except Exception:
                    pass

            # Strategy 2: Try to resolve from dialog cache (most reliable)
            if not entity:
                entity = await self._resolve_entity_from_dialogs(group_id)

            # Strategy 3: Fallback to raw get_entity (may fail for uncached entities)
            if not entity:
                entity = await self._client.get_entity(group_id)

            entity_type = self._get_entity_type(entity)
            member_count = 0
            if hasattr(entity, "participants_count"):
                member_count = entity.participants_count or 0

            has_topics = False
            if isinstance(entity, Channel) and hasattr(entity, "forum"):
                has_topics = entity.forum or False

            return {
                "id": entity.id,
                "name": getattr(entity, "title", str(entity.id)),
                "type": entity_type,
                "username": getattr(entity, "username", None),
                "member_count": member_count,
                "has_topics": has_topics,
            }

        except ChannelPrivateError:
            raise PermissionError(f"No access to group {group_id}. It may be private or you're no longer a member.")
        except ChatAdminRequiredError:
            raise PermissionError(f"Admin access required for group {group_id}.")
        except Exception as e:
            raise TelegramClientError(f"Failed to get group {group_id}: {e}")

    async def list_topics(self, group_id: int) -> List[dict]:
        """List forum topics in a supergroup.

        Args:
            group_id: Supergroup ID with topics enabled.

        Returns:
            List of topic dicts with id, name, icon_color, message_count.
            Empty list if group has no topics.

        Raises:
            PermissionError: If no access to group.
        """
        self._ensure_connected()

        await self._rate_limiter.wait()

        try:
            # Get the group first to check if it has topics
            group = await self.get_group(group_id)
            if not group.get("has_topics"):
                return []

            # Get forum topics
            topics = []
            result = await self._client.get_forum_topics(group_id)

            for topic in result:
                topics.append({
                    "id": topic.id,
                    "name": topic.title,
                    "icon_color": getattr(topic, "icon_color", None),
                    "message_count": getattr(topic, "read_inbox_max_id", 0),
                })

            return topics

        except AttributeError:
            # Telethon version may not support forum topics
            return []
        except Exception as e:
            raise TelegramClientError(f"Failed to list topics: {e}")

    def _parse_message(self, msg: Message, group_id: int) -> dict:
        """Parse a Telegram message into our format.

        Args:
            msg: Telethon Message object
            group_id: Parent group ID

        Returns:
            MessageInfo dict
        """
        # Get sender info
        sender_id = 0
        sender_name = "Unknown"
        sender_username = None

        if msg.sender:
            sender_id = msg.sender.id
            if isinstance(msg.sender, User):
                sender_name = msg.sender.first_name or ""
                if msg.sender.last_name:
                    sender_name += f" {msg.sender.last_name}"
                sender_username = msg.sender.username
            elif hasattr(msg.sender, "title"):
                sender_name = msg.sender.title
                sender_username = getattr(msg.sender, "username", None)

        # Get reply info
        reply_to_id = None
        reply_to_author = None
        if msg.reply_to:
            reply_to_id = msg.reply_to.reply_to_msg_id
            # We'd need another API call to get the author, skip for now

        # Get forward info
        forward_from = None
        if msg.forward:
            if msg.forward.sender:
                if isinstance(msg.forward.sender, User):
                    forward_from = f"@{msg.forward.sender.username}" if msg.forward.sender.username else msg.forward.sender.first_name
                elif hasattr(msg.forward.sender, "title"):
                    forward_from = msg.forward.sender.title
            elif msg.forward.chat:
                forward_from = getattr(msg.forward.chat, "title", "Unknown")

        # Parse attachments
        attachments = []
        if msg.media:
            att = self._parse_media(msg.media)
            if att:
                attachments.append(att)

        # Parse reactions
        reactions = []
        if hasattr(msg, "reactions") and msg.reactions:
            for reaction_count in msg.reactions.results:
                emoji = getattr(reaction_count.reaction, "emoticon", "?")
                reactions.append({
                    "emoji": emoji,
                    "count": reaction_count.count,
                })

        # Get topic ID for forum messages
        topic_id = None
        if msg.reply_to and hasattr(msg.reply_to, "forum_topic"):
            if msg.reply_to.forum_topic:
                topic_id = msg.reply_to.reply_to_msg_id

        return {
            "id": msg.id,
            "group_id": group_id,
            "topic_id": topic_id,
            "sender_id": sender_id,
            "sender_name": sender_name.strip() or "Unknown",
            "sender_username": sender_username,
            "content": msg.text or "",
            "timestamp": msg.date.isoformat() if msg.date else "",
            "edited_at": msg.edit_date.isoformat() if msg.edit_date else None,
            "reply_to_id": reply_to_id,
            "reply_to_author": reply_to_author,
            "forward_from": forward_from,
            "attachments": attachments,
            "reactions": reactions,
        }

    def _parse_media(self, media) -> Optional[dict]:
        """Parse media attachment.

        Args:
            media: Telethon media object

        Returns:
            Attachment dict or None
        """
        if isinstance(media, MessageMediaPhoto):
            return {
                "type": "photo",
                "filename": None,
                "size": getattr(media.photo, "size", 0) if media.photo else 0,
            }

        elif isinstance(media, MessageMediaDocument):
            doc = media.document
            if not doc:
                return None

            # Determine document type from attributes
            doc_type = "document"
            filename = None
            duration = None
            emoji = None

            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    filename = attr.file_name
                elif isinstance(attr, DocumentAttributeAudio):
                    doc_type = "voice" if attr.voice else "audio"
                    duration = attr.duration
                elif isinstance(attr, DocumentAttributeVideo):
                    doc_type = "video"
                    duration = attr.duration
                elif isinstance(attr, DocumentAttributeSticker):
                    doc_type = "sticker"
                    emoji = attr.alt
                elif isinstance(attr, DocumentAttributeAnimated):
                    doc_type = "animation"

            return {
                "type": doc_type,
                "filename": filename,
                "size": doc.size,
                "mime_type": doc.mime_type,
                "duration": duration,
                "emoji": emoji,
            }

        return None

    async def fetch_messages(
        self,
        group_id: int,
        topic_id: Optional[int] = None,
        min_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset_date: Optional[datetime] = None
    ) -> AsyncIterator[dict]:
        """Fetch messages from a group/topic.

        Args:
            group_id: Target group ID.
            topic_id: Optional topic ID for forum groups.
            min_id: Only fetch messages newer than this ID (incremental sync).
            limit: Maximum number of messages to fetch.
            offset_date: Only fetch messages after this date.

        Yields:
            MessageInfo dicts in chronological order (oldest first).

        Raises:
            PermissionError: If no access to group.
            RateLimitError: If rate limited (includes wait time).
        """
        self._ensure_connected()

        messages = []

        try:
            await self._rate_limiter.wait()

            # Build iter_messages kwargs
            kwargs = {
                "limit": limit or 2000,
                "reverse": True,  # Oldest first
            }

            if min_id:
                kwargs["min_id"] = min_id

            if offset_date:
                kwargs["offset_date"] = offset_date

            if topic_id:
                kwargs["reply_to"] = topic_id

            async for msg in self._client.iter_messages(group_id, **kwargs):
                if isinstance(msg, Message):
                    parsed = self._parse_message(msg, group_id)
                    messages.append(parsed)

                # Rate limit check periodically
                if len(messages) % 100 == 0:
                    await self._rate_limiter.wait()

        except FloodWaitError as e:
            await self._rate_limiter.handle_flood_wait(e.seconds)
            raise RateLimitError(e.seconds)
        except ChannelPrivateError:
            raise PermissionError(f"No access to group {group_id}.")
        except UserBannedInChannelError:
            raise PermissionError(f"You are banned from group {group_id}.")
        except ChatAdminRequiredError:
            raise PermissionError(f"Admin access required for group {group_id}.")
        except Exception as e:
            raise TelegramClientError(f"Failed to fetch messages: {e}")

        # Yield messages in order
        for msg in messages:
            yield msg

    async def send_message(
        self,
        group_id: int,
        content: str,
        reply_to_id: Optional[int] = None,
        topic_id: Optional[int] = None
    ) -> dict:
        """Send a message to a group.

        Args:
            group_id: Target group ID.
            content: Message text content.
            reply_to_id: Optional message ID to reply to.
            topic_id: Optional topic ID for forum groups.

        Returns:
            Sent message info.

        Raises:
            PermissionError: If no permission to post.
            RateLimitError: If rate limited.
        """
        self._ensure_connected()

        try:
            await self._rate_limiter.wait()

            # Build send_message kwargs
            kwargs = {"message": content}

            if reply_to_id:
                kwargs["reply_to"] = reply_to_id
            elif topic_id:
                # For forum topics, reply_to is used to specify the topic
                kwargs["reply_to"] = topic_id

            msg = await self._client.send_message(group_id, **kwargs)

            return self._parse_message(msg, group_id)

        except FloodWaitError as e:
            await self._rate_limiter.handle_flood_wait(e.seconds)
            raise RateLimitError(e.seconds)
        except ChannelPrivateError:
            raise PermissionError(f"No access to group {group_id}.")
        except UserBannedInChannelError:
            raise PermissionError(f"You are banned from group {group_id}.")
        except ChatAdminRequiredError:
            raise PermissionError(f"You don't have permission to post in group {group_id}.")
        except Exception as e:
            raise TelegramClientError(f"Failed to send message: {e}")

    async def get_me(self) -> dict:
        """Get current user information.

        Returns:
            Dict with id, username, first_name, last_name.
        """
        if self._me:
            return self._me

        self._ensure_connected()
        me = await self._client.get_me()
        self._me = {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
        }
        return self._me


# Global client instance
_client: Optional[TelegramUserClient] = None


def get_client() -> TelegramUserClient:
    """Get global Telegram client instance."""
    global _client
    if _client is None:
        _client = TelegramUserClient()
    return _client

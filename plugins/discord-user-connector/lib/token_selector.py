"""
Token selection for Discord operations.

Selects optimal Discord connector based on available tokens and operation type.
Prefers bot token for sync operations (higher rate limits, official API compliance),
falls back to user token when bot token is unavailable.
"""

import os
from enum import Enum
from typing import Optional, Tuple


class Operation(Enum):
    """Discord operation types for token selection."""

    MEMBER_SYNC = "member_sync"
    MESSAGE_SYNC = "message_sync"
    MESSAGE_SEND = "message_send"
    DM_ACCESS = "dm_access"
    RICH_PROFILES = "rich_profiles"


class TokenSelector:
    """
    Select optimal token for Discord operations.

    Preferences:
    - MEMBER_SYNC: bot > user (bot has complete member list via intents)
    - MESSAGE_SYNC: bot > user (bot has higher rate limits)
    - MESSAGE_SEND: user only (must send as user)
    - DM_ACCESS: user only (DMs only accessible via user token)
    - RICH_PROFILES: user only (bio, pronouns only via user token)
    """

    def __init__(self):
        self.user_token = os.getenv("DISCORD_USER_TOKEN")
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")

    @property
    def has_user_token(self) -> bool:
        """Check if user token is configured."""
        return bool(self.user_token)

    @property
    def has_bot_token(self) -> bool:
        """Check if bot token is configured."""
        return bool(self.bot_token)

    @property
    def has_both_tokens(self) -> bool:
        """Check if both tokens are configured."""
        return self.has_user_token and self.has_bot_token

    def select(self, operation: Operation) -> Tuple[str, str, bool]:
        """
        Select token for operation.

        Args:
            operation: The type of Discord operation

        Returns:
            Tuple of (connector_name, token, fallback_used)

        Raises:
            ValueError: If no token is available for the operation
        """
        # Define preferences: (preferred, fallback)
        preferences = {
            Operation.MEMBER_SYNC: ("bot", "user"),
            Operation.MESSAGE_SYNC: ("bot", "user"),
            Operation.MESSAGE_SEND: ("user", None),
            Operation.DM_ACCESS: ("user", None),
            Operation.RICH_PROFILES: ("user", None),
        }

        preferred, fallback = preferences.get(operation, ("user", None))

        # Try preferred token first
        if preferred == "bot" and self.bot_token:
            return ("discord-bot-connector", self.bot_token, False)
        elif preferred == "user" and self.user_token:
            return ("discord-user-connector", self.user_token, False)

        # Try fallback token
        if fallback == "user" and self.user_token:
            return ("discord-user-connector", self.user_token, True)
        elif fallback == "bot" and self.bot_token:
            return ("discord-bot-connector", self.bot_token, True)

        # No token available
        raise ValueError(f"No token available for {operation.value}")

    def get_fallback_message(
        self,
        operation: Operation,
        preferred: str,
        fallback: str
    ) -> str:
        """
        Generate a user-friendly fallback notification message.

        Args:
            operation: The operation being performed
            preferred: The preferred connector name
            fallback: The fallback connector name

        Returns:
            A notification message explaining the fallback
        """
        reasons = {
            Operation.MEMBER_SYNC: (
                "Bot token provides complete member list via Gateway Intents"
            ),
            Operation.MESSAGE_SYNC: (
                "Bot token has higher rate limits and official API compliance"
            ),
        }

        reason = reasons.get(
            operation,
            f"Preferred token for {operation.value} not available"
        )

        return (
            f"Using {fallback} instead of {preferred}: {reason}. "
            f"Configure DISCORD_BOT_TOKEN in .env for optimal performance."
        )


def notify_fallback(
    operation: Operation,
    fallback_used: bool,
    connector: str
) -> Optional[str]:
    """
    Generate notification if fallback was used.

    Args:
        operation: The operation being performed
        fallback_used: Whether fallback was used
        connector: The connector that was selected

    Returns:
        Notification message if fallback was used, None otherwise
    """
    if not fallback_used:
        return None

    messages = {
        Operation.MEMBER_SYNC: (
            f"Using {connector} for member sync. "
            "For faster sync with complete member lists, configure DISCORD_BOT_TOKEN "
            "and enable SERVER MEMBERS INTENT in Discord Developer Portal."
        ),
        Operation.MESSAGE_SYNC: (
            f"Using {connector} for message sync. "
            "For higher rate limits and official API compliance, configure DISCORD_BOT_TOKEN."
        ),
    }

    return messages.get(
        operation,
        f"Using {connector} (fallback) for {operation.value}."
    )


def check_and_select(operation: Operation) -> Tuple[str, str, Optional[str]]:
    """
    Convenience function to select token and generate any notifications.

    Args:
        operation: The operation being performed

    Returns:
        Tuple of (connector_name, token, notification_message)
        notification_message is None if no fallback was used
    """
    selector = TokenSelector()
    connector, token, fallback_used = selector.select(operation)
    notification = notify_fallback(operation, fallback_used, connector)
    return (connector, token, notification)

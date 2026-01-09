"""Base rate limiting utilities for community agent plugins.

Shared timing and estimation functions for Discord, Telegram, and other platforms.
"""


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string (e.g., "5s", "2m 30s", "1h 15m")
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


def estimate_sync_time(
    message_count: int,
    messages_per_second: float = 100.0,
) -> float:
    """Estimate time to sync a given number of messages.

    Args:
        message_count: Number of messages to sync
        messages_per_second: Expected throughput (default 100)

    Returns:
        Estimated time in seconds
    """
    if message_count <= 0:
        return 0.0
    return message_count / messages_per_second

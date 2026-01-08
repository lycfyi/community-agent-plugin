"""API rate limiting with random delay and exponential backoff."""

import asyncio
import random
from datetime import datetime, timezone
from typing import Callable, Optional

from .storage import SyncProgress


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format.

    Args:
        seconds: Duration in seconds.

    Returns:
        Human-readable duration string.
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
        message_count: Number of messages to sync.
        messages_per_second: Expected throughput.

    Returns:
        Estimated time in seconds.
    """
    if message_count <= 0:
        return 0.0
    return message_count / messages_per_second


class RateLimiter:
    """Rate limiter with random delay and exponential backoff.

    Uses random delays between requests to avoid detection patterns.
    Implements exponential backoff when rate limits are hit.
    """

    def __init__(
        self,
        base_delay: float = 0.02,  # 50 req/sec
        max_delay: float = 60.0,
        jitter_factor: float = 0.3
    ):
        """Initialize rate limiter.

        Args:
            base_delay: Base delay between requests in seconds
            max_delay: Maximum delay after backoff in seconds
            jitter_factor: Random jitter factor (0.5 = ±50% of delay)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor

        self._current_delay = base_delay
        self._consecutive_errors = 0
        self._last_request: Optional[float] = None

    async def wait(self):
        """Wait the appropriate amount of time before the next request."""
        # Add random jitter to the delay
        jitter = random.uniform(
            1 - self.jitter_factor,
            1 + self.jitter_factor
        )
        delay = self._current_delay * jitter

        await asyncio.sleep(delay)

    def on_success(self):
        """Called after a successful request."""
        # Reset to base delay on success
        self._current_delay = self.base_delay
        self._consecutive_errors = 0

    def on_rate_limit(self, retry_after: Optional[float] = None):
        """Called when a rate limit is hit.

        Args:
            retry_after: Optional server-specified retry delay in seconds
        """
        self._consecutive_errors += 1

        if retry_after:
            # Use server-specified delay
            self._current_delay = min(retry_after, self.max_delay)
        else:
            # Exponential backoff: delay = base * 2^errors
            self._current_delay = min(
                self.base_delay * (2 ** self._consecutive_errors),
                self.max_delay
            )

    def on_error(self):
        """Called on other errors (not rate limits)."""
        self._consecutive_errors += 1

        # Smaller backoff for non-rate-limit errors
        self._current_delay = min(
            self.base_delay * (1.5 ** self._consecutive_errors),
            self.max_delay
        )

    @property
    def current_delay(self) -> float:
        """Get current delay value (without jitter)."""
        return self._current_delay

    def reset(self):
        """Reset the rate limiter to initial state."""
        self._current_delay = self.base_delay
        self._consecutive_errors = 0
        self._last_request = None


class EnhancedProgressTracker:
    """Enhanced progress tracker with ETA calculation and parallel channel support."""

    def __init__(
        self,
        total_channels: int,
        progress_callback: Optional[Callable[[str], None]] = None,
        update_interval_seconds: float = 5.0,
    ) -> None:
        """Initialize the enhanced progress tracker.

        Args:
            total_channels: Total number of channels to sync.
            progress_callback: Optional callback for progress updates.
            update_interval_seconds: Minimum seconds between progress updates.
        """
        self.progress_callback = progress_callback
        self.update_interval = update_interval_seconds
        self.last_update_time: Optional[datetime] = None

        # Initialize progress state
        self.progress = SyncProgress(
            total_channels=total_channels,
            start_time=datetime.now(timezone.utc),
        )

    def start_channel(self, channel_name: str) -> None:
        """Mark a channel as started."""
        self.progress.current_channel = channel_name
        self.progress.channel_status[channel_name] = "syncing"
        self._maybe_log_progress()

    def update_channel_progress(self, channel_name: str, messages: int) -> None:
        """Update progress for a channel."""
        self.progress.channel_progress[channel_name] = messages
        self.progress.messages_fetched = sum(self.progress.channel_progress.values())
        self._maybe_log_progress()

    def complete_channel(self, channel_name: str, messages: int) -> None:
        """Mark a channel as complete."""
        self.progress.channel_progress[channel_name] = messages
        self.progress.channel_status[channel_name] = "complete"
        self.progress.completed_channels += 1
        self.progress.messages_fetched = sum(self.progress.channel_progress.values())
        self._log(f"  #{channel_name}: {messages} messages")

    def skip_channel(self, channel_name: str, reason: str) -> None:
        """Mark a channel as skipped."""
        self.progress.channel_status[channel_name] = f"skipped: {reason}"
        self.progress.completed_channels += 1
        self._log(f"  #{channel_name}: skipped ({reason})")

    def report_rate_limit(self, channel_name: str, retry_after: float) -> None:
        """Report a rate limit hit."""
        self.progress.channel_status[channel_name] = f"rate limited ({retry_after:.1f}s)"
        self._log(f"  #{channel_name}: rate limited, retrying in {retry_after:.1f}s")

    def get_summary_line(self) -> str:
        """Get a summary line for the current progress."""
        pct = self.progress.percentage
        elapsed = format_duration(self.progress.elapsed_seconds)
        eta = self.progress.eta_seconds
        eta_str = format_duration(eta) if eta else "calculating..."

        channels_done = self.progress.completed_channels
        total_channels = self.progress.total_channels
        total_msgs = self.progress.messages_fetched

        return (
            f"Progress: {pct:.0f}% ({channels_done}/{total_channels} channels, "
            f"{total_msgs:,} messages) | Elapsed: {elapsed} | ETA: {eta_str}"
        )

    def _maybe_log_progress(self) -> None:
        """Log progress if enough time has passed since last update."""
        now = datetime.now(timezone.utc)
        if self.last_update_time is not None:
            elapsed = (now - self.last_update_time).total_seconds()
            if elapsed < self.update_interval:
                return

        self.last_update_time = now
        self._log(self.get_summary_line())

    def _log(self, message: str) -> None:
        """Log a message via the callback or print."""
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)

    def get_progress(self) -> SyncProgress:
        """Get the current progress state."""
        return self.progress

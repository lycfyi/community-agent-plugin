"""API rate limiting with random delay and exponential backoff."""

import asyncio
import random
from typing import Optional


class RateLimiter:
    """Rate limiter with random delay and exponential backoff.

    Uses random delays between requests to avoid detection patterns.
    Implements exponential backoff when rate limits are hit.
    """

    def __init__(
        self,
        base_delay: float = 0.5,
        max_delay: float = 60.0,
        jitter_factor: float = 0.5
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

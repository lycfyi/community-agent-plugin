"""Rate limiter for Telegram API with FloodWait handling."""

import asyncio
import time
from typing import Optional


class RateLimiter:
    """Rate limiter with exponential backoff for Telegram API.

    Implements conservative rate limiting to avoid FloodWait errors.
    Telegram doesn't publish exact limits, but community suggests ~30 req/s is safe.
    We use a more conservative 100ms minimum interval.
    """

    def __init__(self, min_interval: float = 0.1):
        """Initialize rate limiter.

        Args:
            min_interval: Minimum seconds between requests (default 100ms)
        """
        self.min_interval = min_interval
        self._last_request: float = 0
        self._flood_wait_until: Optional[float] = None

    async def wait(self) -> None:
        """Wait for rate limit before making a request.

        Call this before each API request to ensure we don't exceed rate limits.
        """
        now = time.time()

        # Check if we're in a flood wait period
        if self._flood_wait_until and now < self._flood_wait_until:
            wait_time = self._flood_wait_until - now
            await asyncio.sleep(wait_time)
            now = time.time()

        # Enforce minimum interval
        elapsed = now - self._last_request
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)

        self._last_request = time.time()

    async def handle_flood_wait(self, wait_seconds: int) -> None:
        """Handle a FloodWait error by waiting the required time.

        Args:
            wait_seconds: Seconds to wait (from FloodWaitError.seconds)
        """
        # Add a small buffer to the wait time
        total_wait = wait_seconds + 5
        self._flood_wait_until = time.time() + total_wait
        await asyncio.sleep(total_wait)
        self._flood_wait_until = None

    def reset(self) -> None:
        """Reset the rate limiter state."""
        self._last_request = 0
        self._flood_wait_until = None


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

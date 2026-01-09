"""Global rate limiter for concurrent multi-server sync operations.

Provides shared rate limiting across all concurrent Discord API requests,
using semaphore-based concurrency control and token bucket pacing.
"""

import asyncio
import time
from typing import Optional


class GlobalRateLimiter:
    """Global rate limiter shared across all concurrent operations.

    Uses a combination of:
    - Semaphore for max concurrent requests
    - Token bucket for request pacing (~40 req/sec, under Discord's 50 limit)
    - Exponential backoff tracking for rate limit errors
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        requests_per_second: float = 40.0,
    ) -> None:
        """Initialize the global rate limiter.

        Args:
            max_concurrent: Maximum number of concurrent API requests.
            requests_per_second: Target requests per second (should be < 50).
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._min_interval = 1.0 / requests_per_second  # ~25ms between requests
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

        # Backoff tracking
        self._consecutive_errors = 0
        self._global_backoff_until: float = 0.0

    async def acquire(self) -> None:
        """Acquire a rate limit slot with global pacing.

        Blocks until:
        1. A semaphore slot is available
        2. Enough time has passed since the last request
        3. Any global backoff period has elapsed
        """
        await self._semaphore.acquire()

        async with self._lock:
            now = time.monotonic()

            # Wait for global backoff if active
            if now < self._global_backoff_until:
                wait_time = self._global_backoff_until - now
                await asyncio.sleep(wait_time)
                now = time.monotonic()

            # Ensure minimum interval between requests
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)

            self._last_request_time = time.monotonic()

    def release(self) -> None:
        """Release the rate limit slot."""
        self._semaphore.release()

    async def __aenter__(self) -> "GlobalRateLimiter":
        """Context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.release()

    def on_success(self) -> None:
        """Called after a successful request to reset backoff."""
        self._consecutive_errors = 0

    def on_rate_limit(self, retry_after: Optional[float] = None) -> None:
        """Called when a rate limit is hit.

        Args:
            retry_after: Server-specified retry delay in seconds.
        """
        self._consecutive_errors += 1

        if retry_after:
            # Use server-specified delay
            backoff_duration = min(retry_after, 60.0)
        else:
            # Exponential backoff: 1s, 2s, 4s, 8s, ... max 60s
            backoff_duration = min(
                1.0 * (2 ** self._consecutive_errors),
                60.0
            )

        self._global_backoff_until = time.monotonic() + backoff_duration

    def on_error(self) -> None:
        """Called on non-rate-limit errors."""
        self._consecutive_errors += 1
        # Smaller backoff for general errors
        backoff_duration = min(
            0.5 * (1.5 ** self._consecutive_errors),
            30.0
        )
        self._global_backoff_until = time.monotonic() + backoff_duration

    @property
    def is_in_backoff(self) -> bool:
        """Check if currently in a backoff period."""
        return time.monotonic() < self._global_backoff_until

    def reset(self) -> None:
        """Reset the rate limiter to initial state."""
        self._consecutive_errors = 0
        self._global_backoff_until = 0.0
        self._last_request_time = 0.0

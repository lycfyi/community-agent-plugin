"""Parallel sync orchestrator for concurrent channel syncing."""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, List, Optional

import discord

from .config import get_config
from .discord_client import DiscordUserClient, DiscordClientError
from .rate_limiter import EnhancedProgressTracker, format_duration
from .storage import Storage, SyncMode, get_storage


@dataclass
class ChannelSyncResult:
    """Result of syncing a single channel."""

    channel_id: str
    channel_name: str
    messages_fetched: int
    success: bool
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    oldest_date: Optional[date] = None
    newest_date: Optional[date] = None


@dataclass
class SyncSummary:
    """Summary of a sync operation."""

    total_messages: int
    channels_processed: int
    channels_skipped: int
    sync_mode: SyncMode
    duration_seconds: float
    estimated_full_sync_seconds: Optional[float] = None
    channels_with_new_messages: List[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.channels_with_new_messages is None:
            self.channels_with_new_messages = []
        if self.errors is None:
            self.errors = []


class ParallelSyncOrchestrator:
    """Orchestrates parallel channel syncing with progress tracking."""

    def __init__(
        self,
        client: DiscordUserClient,
        storage: Storage,
        server_id: str,
        server_name: str,
        quick_mode: bool = False,
        quick_limit: int = 200,
        days: int = 7,
        incremental: bool = True,
        fill_gaps: bool = False,
        since_date: Optional[date] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the parallel sync orchestrator.

        Args:
            client: Discord client instance.
            storage: Storage service.
            server_id: Discord server ID.
            server_name: Server display name.
            quick_mode: If True, limit messages for fast initial sync.
            quick_limit: Max messages per channel in quick mode.
            days: Number of days of history to fetch.
            incremental: Whether to do incremental sync.
            fill_gaps: If True, fill missing date ranges.
            since_date: If set, fetch messages from this date onward.
            progress_callback: Optional callback for progress updates.
        """
        self.client = client
        self.storage = storage
        self.server_id = server_id
        self.server_name = server_name
        self.quick_mode = quick_mode
        self.quick_limit = quick_limit
        self.days = days
        self.incremental = incremental
        self.fill_gaps = fill_gaps
        self.since_date = since_date
        self.progress_callback = progress_callback

        self._progress_tracker: Optional[EnhancedProgressTracker] = None
        self._start_time: Optional[datetime] = None
        self._results: List[ChannelSyncResult] = []
        self._lock = asyncio.Lock()

    async def sync_all_channels(
        self,
        channels: List[dict],
        max_messages_per_channel: int = 200,
    ) -> SyncSummary:
        """Sync all channels in parallel.

        Args:
            channels: List of channel info dicts.
            max_messages_per_channel: Max messages per channel.

        Returns:
            SyncSummary with results of the sync operation.
        """
        self._start_time = datetime.now(timezone.utc)
        self._results = []

        # Initialize progress tracker
        self._progress_tracker = EnhancedProgressTracker(
            total_channels=len(channels),
            progress_callback=self.progress_callback,
        )

        self._log(f"Starting parallel sync of {len(channels)} channels...")

        # Determine effective limit
        limit = self.quick_limit if self.quick_mode else max_messages_per_channel

        # Create tasks for parallel execution
        tasks = [
            self._sync_channel_with_retry(channel, limit)
            for channel in channels
        ]

        # Execute all channels in parallel
        await asyncio.gather(*tasks, return_exceptions=True)

        # Calculate duration
        duration = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        # Determine sync mode
        if self.quick_mode:
            sync_mode = SyncMode.QUICK
        elif self.fill_gaps:
            sync_mode = SyncMode.GAP_FILL
        elif self.incremental:
            sync_mode = SyncMode.INCREMENTAL
        else:
            sync_mode = SyncMode.FULL

        # Build summary
        total_messages = sum(r.messages_fetched for r in self._results if r.success)
        channels_processed = sum(1 for r in self._results if r.success and not r.skipped)
        channels_skipped = sum(1 for r in self._results if r.skipped)
        channels_with_new = [r.channel_name for r in self._results if r.success and r.messages_fetched > 0]
        errors = [r.error for r in self._results if r.error]

        summary = SyncSummary(
            total_messages=total_messages,
            channels_processed=channels_processed,
            channels_skipped=channels_skipped,
            sync_mode=sync_mode,
            duration_seconds=duration,
            channels_with_new_messages=channels_with_new,
            errors=errors,
        )

        self._log(f"\nSync complete: {total_messages:,} messages from {channels_processed} channels in {duration:.1f}s")

        return summary

    async def _sync_channel_with_retry(
        self,
        channel: dict,
        limit: int,
        max_retries: int = 3,
    ) -> ChannelSyncResult:
        """Sync a single channel with retry logic.

        Args:
            channel: Channel info dict.
            limit: Max messages to fetch.
            max_retries: Maximum number of retry attempts.

        Returns:
            ChannelSyncResult with the outcome.
        """
        retries = 0
        last_error = None

        while retries <= max_retries:
            try:
                result = await self._sync_channel(channel, limit)
                async with self._lock:
                    self._results.append(result)
                return result

            except discord.errors.RateLimited as e:
                retry_after = e.retry_after
                if self._progress_tracker:
                    self._progress_tracker.report_rate_limit(channel["name"], retry_after)
                await asyncio.sleep(retry_after)
                retries += 1
                last_error = str(e)

            except Exception as e:
                last_error = str(e)
                retries += 1
                if retries <= max_retries:
                    await asyncio.sleep(1.0 * retries)

        # All retries exhausted
        result = ChannelSyncResult(
            channel_id=channel["id"],
            channel_name=channel["name"],
            messages_fetched=0,
            success=False,
            error=f"Failed after {max_retries} retries: {last_error}",
        )
        async with self._lock:
            self._results.append(result)

        if self._progress_tracker:
            self._progress_tracker.complete_channel(channel["name"], 0)

        return result

    async def _sync_channel(
        self,
        channel: dict,
        limit: int,
    ) -> ChannelSyncResult:
        """Sync a single channel.

        Args:
            channel: Channel info dict.
            limit: Max messages to fetch.

        Returns:
            ChannelSyncResult with the outcome.
        """
        channel_id = channel["id"]
        channel_name = channel["name"]

        if self._progress_tracker:
            self._progress_tracker.start_channel(channel_name)

        # Check if already up to date
        if self.incremental and self.storage.is_channel_up_to_date(
            self.server_id, channel_name
        ):
            result = ChannelSyncResult(
                channel_id=channel_id,
                channel_name=channel_name,
                messages_fetched=0,
                success=True,
                skipped=True,
                skip_reason="already up to date",
            )
            if self._progress_tracker:
                self._progress_tracker.skip_channel(channel_name, "already synced")
            return result

        # Get last message ID for incremental sync
        after_id = None
        if self.incremental:
            after_id = self.storage.get_last_message_id(self.server_id, channel_name)

        # Fetch messages
        messages = []
        oldest_date = None
        newest_date = None

        try:
            count = 0
            async for msg in self.client.fetch_messages(
                server_id=self.server_id,
                channel_id=channel_id,
                after_id=after_id,
                days=self.days,
                limit=limit,
            ):
                messages.append(msg)

                # Track date range
                msg_date = datetime.fromisoformat(msg["timestamp"]).date()
                if oldest_date is None or msg_date < oldest_date:
                    oldest_date = msg_date
                if newest_date is None or msg_date > newest_date:
                    newest_date = msg_date

                count += 1
                if count % 50 == 0 and self._progress_tracker:
                    self._progress_tracker.update_channel_progress(channel_name, count)

                if count >= limit:
                    break

        except DiscordClientError as e:
            result = ChannelSyncResult(
                channel_id=channel_id,
                channel_name=channel_name,
                messages_fetched=0,
                success=False,
                error=str(e),
            )
            if self._progress_tracker:
                self._progress_tracker.complete_channel(channel_name, 0)
            return result

        # Save messages if any
        if messages:
            self.storage.append_messages(
                server_id=self.server_id,
                server_name=self.server_name,
                channel_id=channel_id,
                channel_name=channel_name,
                messages=messages,
            )

            # Update sync state with date range
            sync_mode = SyncMode.QUICK if self.quick_mode else SyncMode.INCREMENTAL
            last_msg = messages[-1]
            first_msg = messages[0]

            self.storage.update_channel_sync_state(
                server_id=self.server_id,
                server_name=self.server_name,
                channel_name=channel_name,
                channel_id=channel_id,
                last_message_id=last_msg["id"],
                message_count=len(messages),
                sync_mode=sync_mode,
                oldest_synced_date=oldest_date,
                newest_synced_date=newest_date,
                oldest_message_id=first_msg["id"],
            )

        if self._progress_tracker:
            self._progress_tracker.complete_channel(channel_name, len(messages))

        return ChannelSyncResult(
            channel_id=channel_id,
            channel_name=channel_name,
            messages_fetched=len(messages),
            success=True,
            oldest_date=oldest_date,
            newest_date=newest_date,
        )

    def _log(self, message: str) -> None:
        """Log a message via the callback or print."""
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)

    def get_results(self) -> List[ChannelSyncResult]:
        """Get the results of all channel syncs."""
        return self._results

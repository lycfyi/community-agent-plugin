"""Multi-server parallel sync orchestrator.

Coordinates parallel syncing across multiple Discord servers with:
- Concurrent server processing (configurable limit)
- Global rate limiting across all operations
- Batched file I/O for performance
- Error isolation per server
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Callable, List, Optional

from .batched_writer import BatchedWriter
from .config import get_config
from .discord_client import DiscordUserClient, DiscordClientError
from .global_rate_limiter import GlobalRateLimiter
from .rate_limiter import format_duration
from .storage import Storage, SyncMode, get_storage


@dataclass
class ServerSyncResult:
    """Result of syncing a single server."""

    server_id: str
    server_name: str
    success: bool
    messages_fetched: int = 0
    channels_synced: int = 0
    channels_failed: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None


@dataclass
class MultiServerSyncSummary:
    """Summary of multi-server sync operation."""

    total_servers: int
    servers_synced: int
    servers_failed: int
    total_messages: int
    total_channels: int
    duration_seconds: float
    server_results: List[ServerSyncResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_servers == 0:
            return 100.0
        return (self.servers_synced / self.total_servers) * 100


class MultiServerSyncOrchestrator:
    """Orchestrates parallel syncing across multiple servers.

    Uses:
    - Semaphore to limit concurrent servers (default 5)
    - Global rate limiter for API request pacing
    - Batched writer for efficient file I/O
    - Error isolation per server
    """

    def __init__(
        self,
        client: DiscordUserClient,
        storage: Optional[Storage] = None,
        global_rate_limiter: Optional[GlobalRateLimiter] = None,
        max_servers_parallel: int = 5,
        max_channels_parallel: int = 10,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the multi-server orchestrator.

        Args:
            client: Discord client instance.
            storage: Storage service (uses global if not provided).
            global_rate_limiter: Global rate limiter (creates new if not provided).
            max_servers_parallel: Max concurrent servers to sync.
            max_channels_parallel: Max concurrent channels per server.
            progress_callback: Optional callback for progress updates.
        """
        self._client = client
        self._storage = storage or get_storage()
        self._rate_limiter = global_rate_limiter or GlobalRateLimiter()
        self._max_servers = max_servers_parallel
        self._max_channels = max_channels_parallel
        self._progress_callback = progress_callback

        # Initialize batched writer
        self._batch_writer = BatchedWriter(
            storage=self._storage,
            batch_size=100,
            flush_interval_seconds=5.0,
            progress_callback=progress_callback,
        )

        # Track results
        self._results: List[ServerSyncResult] = []
        self._lock = asyncio.Lock()
        self._start_time: Optional[datetime] = None

    async def sync_all_servers(
        self,
        servers: List[dict],
        days: int = 7,
        limit: Optional[int] = 200,
        incremental: bool = True,
    ) -> MultiServerSyncSummary:
        """Sync all servers in parallel with controlled concurrency.

        Args:
            servers: List of server info dicts.
            days: Number of days of history to fetch.
            limit: Max messages per channel (None for unlimited).
            incremental: Whether to do incremental sync.

        Returns:
            MultiServerSyncSummary with results.
        """
        self._start_time = datetime.now(timezone.utc)
        self._results = []

        # Start background flush for progressive availability
        await self._batch_writer.start_background_flush()

        try:
            self._log(f"Starting parallel sync of {len(servers)} servers...")
            self._log(f"  Max concurrent servers: {self._max_servers}")
            self._log(f"  Limit: {limit}/channel" if limit else "  Limit: unlimited")
            self._log("")

            # Create semaphore for server concurrency
            server_semaphore = asyncio.Semaphore(self._max_servers)

            async def sync_with_semaphore(server: dict) -> ServerSyncResult:
                async with server_semaphore:
                    return await self._sync_server(
                        server=server,
                        days=days,
                        limit=limit,
                        incremental=incremental,
                    )

            # Create tasks for all servers
            tasks = [sync_with_semaphore(server) for server in servers]

            # Execute all servers in parallel (with semaphore limiting)
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Handle unexpected exceptions
                    server = servers[i]
                    error_result = ServerSyncResult(
                        server_id=server.get("id", "unknown"),
                        server_name=server.get("name", "Unknown"),
                        success=False,
                        error=str(result),
                    )
                    self._results.append(error_result)
                else:
                    self._results.append(result)

        finally:
            # Stop background flush and flush remaining data
            await self._batch_writer.stop_background_flush()

        # Calculate summary
        duration = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        summary = MultiServerSyncSummary(
            total_servers=len(servers),
            servers_synced=sum(1 for r in self._results if r.success),
            servers_failed=sum(1 for r in self._results if not r.success),
            total_messages=sum(r.messages_fetched for r in self._results),
            total_channels=sum(r.channels_synced for r in self._results),
            duration_seconds=duration,
            server_results=self._results,
        )

        self._print_summary(summary)

        return summary

    async def _sync_server(
        self,
        server: dict,
        days: int,
        limit: Optional[int],
        incremental: bool,
    ) -> ServerSyncResult:
        """Sync a single server with error isolation.

        Args:
            server: Server info dict.
            days: Days of history to fetch.
            limit: Max messages per channel (None for unlimited).
            incremental: Whether to do incremental sync.

        Returns:
            ServerSyncResult with outcome.
        """
        server_id = server["id"]
        server_name = server["name"]
        server_start = datetime.now(timezone.utc)

        self._log(f"[{server_name}] Starting sync...")

        try:
            # Save server metadata
            self._storage.save_server_metadata(
                server_id=server_id,
                server_name=server_name,
                icon=server.get("icon"),
                member_count=server.get("member_count", 0)
            )

            # Get channels to sync
            config = get_config()
            all_channels = await self._client.list_channels(server_id)

            # Sort and limit channels
            max_channels = config.max_channels_per_server
            priority_channels = config.priority_channels

            def channel_sort_key(ch):
                name = ch.get("name", "").lower()
                if name in [p.lower() for p in priority_channels]:
                    return -1000 + [p.lower() for p in priority_channels].index(name)
                return ch.get("position", 999)

            sorted_channels = sorted(all_channels, key=channel_sort_key)
            channels_to_sync = sorted_channels[:max_channels]

            if len(all_channels) > max_channels:
                self._log(f"[{server_name}] Limiting to {max_channels} of {len(all_channels)} channels")

            # Sync channels in parallel (within this server)
            channel_semaphore = asyncio.Semaphore(self._max_channels)
            messages_fetched = 0
            channels_synced = 0
            channels_failed = 0
            channel_results = []

            async def sync_channel(channel: dict) -> dict:
                async with channel_semaphore:
                    return await self._sync_channel(
                        server_id=server_id,
                        server_name=server_name,
                        channel=channel,
                        days=days,
                        limit=limit,
                        incremental=incremental,
                    )

            channel_tasks = [sync_channel(ch) for ch in channels_to_sync]
            channel_result_list = await asyncio.gather(*channel_tasks, return_exceptions=True)

            for ch_result in channel_result_list:
                if isinstance(ch_result, Exception):
                    channels_failed += 1
                elif ch_result.get("success"):
                    channels_synced += 1
                    messages_fetched += ch_result.get("message_count", 0)
                    channel_results.append(ch_result)
                else:
                    channels_failed += 1

            # Finalize sync states for this server
            await self._batch_writer.finalize_sync_states(
                channel_results=channel_results,
                sync_mode=SyncMode.INCREMENTAL if limit else SyncMode.FULL,
            )

            duration = (datetime.now(timezone.utc) - server_start).total_seconds()

            self._log(
                f"[{server_name}] Done: {messages_fetched} messages, "
                f"{channels_synced} channels in {format_duration(duration)}"
            )

            return ServerSyncResult(
                server_id=server_id,
                server_name=server_name,
                success=True,
                messages_fetched=messages_fetched,
                channels_synced=channels_synced,
                channels_failed=channels_failed,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.now(timezone.utc) - server_start).total_seconds()
            self._log(f"[{server_name}] Error: {e}")

            return ServerSyncResult(
                server_id=server_id,
                server_name=server_name,
                success=False,
                duration_seconds=duration,
                error=str(e),
            )

    async def _sync_channel(
        self,
        server_id: str,
        server_name: str,
        channel: dict,
        days: int,
        limit: Optional[int],
        incremental: bool,
    ) -> dict:
        """Sync a single channel.

        Args:
            server_id: Server ID.
            server_name: Server name.
            channel: Channel info dict.
            days: Days of history.
            limit: Max messages (None for unlimited).
            incremental: Whether incremental.

        Returns:
            Dict with channel sync result.
        """
        channel_id = channel["id"]
        channel_name = channel["name"]

        # Check if already up to date
        if incremental and self._storage.is_channel_up_to_date(server_id, channel_name):
            return {
                "success": True,
                "server_id": server_id,
                "server_name": server_name,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "message_count": 0,
                "skipped": True,
            }

        # Get last message ID for incremental sync
        after_id = None
        if incremental:
            after_id = self._storage.get_last_message_id(server_id, channel_name)

        # Use provided limit or no limit
        effective_limit = limit if limit else None

        # Fetch messages with rate limiting
        messages = []
        oldest_date: Optional[date] = None
        newest_date: Optional[date] = None

        try:
            async for msg in self._client.fetch_messages(
                server_id=server_id,
                channel_id=channel_id,
                after_id=after_id,
                days=days,
                limit=effective_limit,
            ):
                # Apply global rate limiting
                async with self._rate_limiter:
                    self._rate_limiter.on_success()

                messages.append(msg)

                # Track date range
                msg_date = datetime.fromisoformat(msg["timestamp"]).date()
                if oldest_date is None or msg_date < oldest_date:
                    oldest_date = msg_date
                if newest_date is None or msg_date > newest_date:
                    newest_date = msg_date

                if effective_limit and len(messages) >= effective_limit:
                    break

        except DiscordClientError as e:
            return {
                "success": False,
                "server_id": server_id,
                "server_name": server_name,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "message_count": 0,
                "error": str(e),
            }

        # Queue messages for batched writing
        if messages:
            await self._batch_writer.queue_messages(
                server_id=server_id,
                server_name=server_name,
                channel_id=channel_id,
                channel_name=channel_name,
                messages=messages,
            )

        return {
            "success": True,
            "server_id": server_id,
            "server_name": server_name,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "message_count": len(messages),
            "last_message_id": messages[-1]["id"] if messages else None,
            "oldest_message_id": messages[0]["id"] if messages else None,
            "oldest_date": oldest_date,
            "newest_date": newest_date,
        }

    def _print_summary(self, summary: MultiServerSyncSummary) -> None:
        """Print formatted summary of sync operation."""
        self._log("")
        self._log("=" * 60)
        self._log("MULTI-SERVER SYNC COMPLETE")
        self._log("=" * 60)
        self._log("")
        self._log(f"  Servers synced:   {summary.servers_synced}/{summary.total_servers}")
        self._log(f"  Total channels:   {summary.total_channels}")
        self._log(f"  Total messages:   {summary.total_messages:,}")
        self._log(f"  Duration:         {format_duration(summary.duration_seconds)}")
        self._log("")

        # Show failed servers if any
        failed = [r for r in summary.server_results if not r.success]
        if failed:
            self._log(f"  Failed servers ({len(failed)}):")
            for result in failed[:5]:
                self._log(f"    - {result.server_name}: {result.error}")
            if len(failed) > 5:
                self._log(f"    ... and {len(failed) - 5} more")
            self._log("")

        # Show top servers by message count
        successful = sorted(
            [r for r in summary.server_results if r.success],
            key=lambda r: r.messages_fetched,
            reverse=True
        )
        if successful:
            self._log("  Top servers by messages:")
            for result in successful[:5]:
                self._log(
                    f"    - {result.server_name}: "
                    f"{result.messages_fetched:,} msgs, "
                    f"{result.channels_synced} channels"
                )
            self._log("")

        self._log("=" * 60)

    def _log(self, message: str) -> None:
        """Log a message via callback or print."""
        if self._progress_callback:
            self._progress_callback(message)
        else:
            print(message)

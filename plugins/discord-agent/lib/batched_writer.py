"""Batched file writer for efficient concurrent I/O.

Accumulates messages and writes in batches to reduce file operations,
with periodic flush for progressive data availability.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Callable, Dict, List, Optional

from .storage import Storage, SyncMode


@dataclass
class ChannelBuffer:
    """Buffer for a single channel's pending messages."""

    server_id: str
    server_name: str
    channel_id: str
    channel_name: str
    messages: List[dict] = field(default_factory=list)
    oldest_date: Optional[date] = None
    newest_date: Optional[date] = None

    def add_messages(self, msgs: List[dict]) -> None:
        """Add messages to the buffer and track date range."""
        self.messages.extend(msgs)

        for msg in msgs:
            msg_date = datetime.fromisoformat(msg["timestamp"]).date()
            if self.oldest_date is None or msg_date < self.oldest_date:
                self.oldest_date = msg_date
            if self.newest_date is None or msg_date > self.newest_date:
                self.newest_date = msg_date

    @property
    def message_count(self) -> int:
        """Get count of buffered messages."""
        return len(self.messages)

    def get_last_message_id(self) -> Optional[str]:
        """Get the ID of the last message in buffer."""
        if not self.messages:
            return None
        return self.messages[-1]["id"]

    def get_oldest_message_id(self) -> Optional[str]:
        """Get the ID of the oldest message in buffer."""
        if not self.messages:
            return None
        return self.messages[0]["id"]


class BatchedWriter:
    """Batched file writer for efficient concurrent I/O.

    Accumulates writes and flushes in batches:
    - Buffer messages per channel (batch_size threshold)
    - Periodic flush every N seconds (progressive availability)
    - Deferred sync state updates (single write per server at end)
    """

    def __init__(
        self,
        storage: Storage,
        batch_size: int = 100,
        flush_interval_seconds: float = 5.0,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the batched writer.

        Args:
            storage: Storage service instance.
            batch_size: Max messages per channel before auto-flush.
            flush_interval_seconds: Periodic flush interval.
            progress_callback: Optional callback for status updates.
        """
        self._storage = storage
        self._batch_size = batch_size
        self._flush_interval = flush_interval_seconds
        self._progress_callback = progress_callback

        # Per-channel message buffers: key = "server_id:channel_name"
        self._buffers: Dict[str, ChannelBuffer] = {}
        self._buffer_lock = asyncio.Lock()

        # Background flush task
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    def _buffer_key(self, server_id: str, channel_name: str) -> str:
        """Generate buffer key for a channel."""
        return f"{server_id}:{channel_name}"

    async def queue_messages(
        self,
        server_id: str,
        server_name: str,
        channel_id: str,
        channel_name: str,
        messages: List[dict],
    ) -> None:
        """Queue messages for batched writing.

        Args:
            server_id: Discord server ID.
            server_name: Server display name.
            channel_id: Channel ID.
            channel_name: Channel name.
            messages: List of messages to queue.
        """
        if not messages:
            return

        key = self._buffer_key(server_id, channel_name)

        async with self._buffer_lock:
            if key not in self._buffers:
                self._buffers[key] = ChannelBuffer(
                    server_id=server_id,
                    server_name=server_name,
                    channel_id=channel_id,
                    channel_name=channel_name,
                )

            buffer = self._buffers[key]
            buffer.add_messages(messages)

            # Auto-flush if buffer exceeds threshold
            if buffer.message_count >= self._batch_size:
                await self._flush_channel(key)

    async def _flush_channel(self, key: str) -> None:
        """Flush a single channel's buffer to disk.

        Args:
            key: Buffer key ("server_id:channel_name").
        """
        buffer = self._buffers.pop(key, None)
        if not buffer or not buffer.messages:
            return

        # Write messages to file (without sync state update)
        self._write_messages_only(buffer)

        self._log(f"  Flushed {buffer.message_count} messages for #{buffer.channel_name}")

    def _write_messages_only(self, buffer: ChannelBuffer) -> None:
        """Write messages to file without updating sync state.

        This is a simplified version of storage.append_messages that
        doesn't call update_channel_sync_state (we batch those).
        """
        if not buffer.messages:
            return

        # Use storage's internal methods for file writing
        safe_name = self._storage._sanitize_name(buffer.channel_name)
        server_dir = self._storage._get_server_dir(buffer.server_id, buffer.server_name)
        channel_dir = server_dir / safe_name
        self._storage._ensure_dir(channel_dir)

        messages_file = channel_dir / "messages.md"

        # Import formatters
        from .markdown_formatter import (
            format_channel_header,
            format_date_header,
            format_message,
            group_messages_by_date
        )

        # Group messages by date
        date_groups = group_messages_by_date(buffer.messages)

        # Create file with header if it doesn't exist
        if not messages_file.exists():
            now = datetime.now(timezone.utc).isoformat()
            header = format_channel_header(
                channel_name=buffer.channel_name,
                channel_id=buffer.channel_id,
                server_name=buffer.server_name,
                server_id=buffer.server_id,
                last_sync=now
            )
            with open(messages_file, "w") as f:
                f.write(header)

        # Build content to append
        new_lines = []
        sorted_dates = sorted(date_groups.keys())

        for date_str in sorted_dates:
            date_header = format_date_header(date_str)
            new_lines.append("")
            new_lines.append(date_header)
            new_lines.append("")

            # Sort messages by timestamp
            day_messages = sorted(
                date_groups[date_str],
                key=lambda m: m.get("timestamp", "")
            )

            for msg in day_messages:
                new_lines.append(format_message(msg))
                new_lines.append("")

        # Append to file
        with open(messages_file, "a") as f:
            f.write("\n".join(new_lines))

    async def flush_all(self) -> Dict[str, int]:
        """Flush all pending buffers and return flush summary.

        Returns:
            Dict mapping buffer keys to message counts flushed.
        """
        flushed = {}

        async with self._buffer_lock:
            keys = list(self._buffers.keys())
            for key in keys:
                buffer = self._buffers.get(key)
                if buffer and buffer.messages:
                    flushed[key] = buffer.message_count
                    await self._flush_channel(key)

        return flushed

    async def finalize_sync_states(
        self,
        channel_results: List[dict],
        sync_mode: SyncMode = SyncMode.INCREMENTAL,
    ) -> None:
        """Finalize sync state updates for all channels.

        Should be called once at the end of sync to batch all
        sync state updates.

        Args:
            channel_results: List of dicts with channel sync results:
                - server_id, server_name, channel_id, channel_name
                - last_message_id, oldest_message_id
                - message_count
                - oldest_date, newest_date
            sync_mode: The sync mode used.
        """
        for result in channel_results:
            self._storage.update_channel_sync_state(
                server_id=result["server_id"],
                server_name=result["server_name"],
                channel_name=result["channel_name"],
                channel_id=result["channel_id"],
                last_message_id=result["last_message_id"],
                message_count=result["message_count"],
                sync_mode=sync_mode,
                oldest_synced_date=result.get("oldest_date"),
                newest_synced_date=result.get("newest_date"),
                oldest_message_id=result.get("oldest_message_id"),
            )

    async def start_background_flush(self) -> None:
        """Start background flush task for progressive data availability."""
        if self._running:
            return

        self._running = True

        async def flush_loop():
            while self._running:
                await asyncio.sleep(self._flush_interval)
                if self._running:  # Check again after sleep
                    flushed = await self.flush_all()
                    if flushed:
                        total = sum(flushed.values())
                        self._log(f"  Background flush: {total} messages across {len(flushed)} channels")

        self._flush_task = asyncio.create_task(flush_loop())

    async def stop_background_flush(self) -> None:
        """Stop background flush and perform final flush."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Final flush of any remaining data
        await self.flush_all()

    def _log(self, message: str) -> None:
        """Log a message via callback or print."""
        if self._progress_callback:
            self._progress_callback(message)
        else:
            print(message)

    @property
    def pending_count(self) -> int:
        """Get total count of pending messages across all buffers."""
        return sum(b.message_count for b in self._buffers.values())

    @property
    def pending_channels(self) -> int:
        """Get count of channels with pending messages."""
        return len(self._buffers)

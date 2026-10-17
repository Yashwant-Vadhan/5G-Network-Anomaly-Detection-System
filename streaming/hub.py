"""Bounded pub/sub live fan-out hub for dashboard client subscriptions (T11-013).

Broadcasts real-time events, scored samples, connection status transitions,
and alert notifications to connected dashboard WebSocket clients with bounded
subscriber queues and drop-oldest backpressure mitigation.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from streaming.schema import DroppedEvent

logger = logging.getLogger(__name__)


class Subscriber:
    """Represents a connected subscriber with a bounded queue and drop accounting."""

    def __init__(self, sub_id: str, queue_size: int) -> None:
        self.sub_id = sub_id
        try:
            self.loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None
        self.queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=queue_size)
        self.dropped_count: int = 0
        self.has_pending_drop_event: bool = False

    def _do_push(self, message: Any, session_id: str | None = None) -> None:
        """Internal bounded queue push logic."""
        if self.queue.full():
            # Slow subscriber backpressure: drop oldest item
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

            self.dropped_count += 1
            logger.warning(
                "Subscriber %s queue full; dropped oldest message (total_dropped=%d)",
                self.sub_id,
                self.dropped_count,
            )

            # Insert DroppedEvent to alert client of drop and request state resync
            now_iso = datetime.now(UTC).isoformat()
            drop_ev = DroppedEvent(
                server_time=now_iso,
                session_id=session_id,
                count=self.dropped_count,
            )

            try:
                # If room after dropping, push the DroppedEvent
                self.queue.put_nowait(drop_ev)
            except asyncio.QueueFull:
                pass

        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull:
            # If still full, drop another to make room for newest telemetry
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.dropped_count += 1
            try:
                self.queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    def push(self, message: Any, session_id: str | None = None) -> None:
        """Push message to subscriber queue, thread-safely waking its event loop."""
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            cur_loop = None

        if self.loop is None or cur_loop == self.loop or not self.loop.is_running():
            self._do_push(message, session_id)
        else:
            self.loop.call_soon_threadsafe(self._do_push, message, session_id)


class LiveHub:
    """Async fan-out pub/sub hub with bounded per-subscriber queues."""

    def __init__(self, default_queue_size: int = 100) -> None:
        self.default_queue_size = default_queue_size
        self._subscribers: dict[str, Subscriber] = {}
        self._lock = asyncio.Lock()

    @property
    def subscriber_count(self) -> int:
        """Return number of currently registered active subscribers."""
        return len(self._subscribers)

    async def subscribe(self, queue_size: int | None = None) -> tuple[str, asyncio.Queue[Any]]:
        """Register a new subscriber and return its unique ID and message queue.

        Args:
            queue_size: Optional custom queue capacity (defaults to default_queue_size).

        Returns:
            Tuple of (subscriber_id, message_queue).
        """
        sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        q_size = queue_size or self.default_queue_size
        sub = Subscriber(sub_id=sub_id, queue_size=q_size)

        async with self._lock:
            self._subscribers[sub_id] = sub

        logger.info("Subscriber %s registered (total=%d)", sub_id, len(self._subscribers))
        return sub_id, sub.queue

    async def unsubscribe(self, sub_id: str) -> bool:
        """Remove subscriber and clean up its resources.

        Args:
            sub_id: Unique subscriber ID.

        Returns:
            True if subscriber was found and removed; False otherwise.
        """
        async with self._lock:
            sub = self._subscribers.pop(sub_id, None)

        if sub is not None:
            logger.info("Subscriber %s unsubscribed (remaining=%d)", sub_id, len(self._subscribers))
            return True
        return False

    async def broadcast(self, message: Any, session_id: str | None = None) -> None:
        """Broadcast message to all subscribers without blocking the publisher.

        Args:
            message: Telemetry model, dict, or message string to broadcast.
            session_id: Active session ID associated with the message.
        """
        # Convert Pydantic models to dict if needed for consistent JSON delivery
        msg = message
        if isinstance(message, BaseModel):
            msg = message.model_dump()

        async with self._lock:
            current_subs = list(self._subscribers.values())

        for sub in current_subs:
            sub.push(msg, session_id=session_id)

    async def close_all(self) -> None:
        """Unsubscribe all clients and clear registry."""
        async with self._lock:
            self._subscribers.clear()

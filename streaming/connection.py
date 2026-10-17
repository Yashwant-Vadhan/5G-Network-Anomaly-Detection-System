"""Connection and freshness state machine (T11-020, Contract C8).

Tracks server-authoritative client connection states (LIVE, STALE, RECONNECTING, WAITING)
from socket lifecycle and sample age using STALE_AFTER_SECONDS, and detects clock skew
between sent_at and received_at against CLOCK_SKEW_WARN_SECONDS without altering timestamps.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ml.config import (
    CLOCK_SKEW_WARN_SECONDS,
    SESSION_RESUME_WINDOW_SECONDS,
    STALE_AFTER_SECONDS,
)
from streaming.schema import ConnectionEvent, ConnectionState, StreamSource

if TYPE_CHECKING:
    from streaming.hub import LiveHub

logger = logging.getLogger(__name__)


@dataclass
class SessionConnectionInfo:
    """Connection state tracking record for a single session."""

    session_id: str
    client_id: str
    source: StreamSource = "phone"
    connected: bool = True
    last_sample_time: float | None = None
    disconnect_time: float | None = None
    current_state: ConnectionState = "WAITING"
    clock_skew_flag: bool = False
    latest_skew_s: float | None = None
    samples_count: int = 0


class ConnectionTracker:
    """Server-side connection and data freshness state machine.

    Evaluates authoritative state (LIVE / STALE / RECONNECTING / WAITING / REPLAY-SOURCE)
    per session and broadcasts transition ConnectionEvents to the live fan-out hub.
    Supports dependency-injected monotonic and wall clocks for deterministic testing.
    """

    def __init__(
        self,
        hub: LiveHub | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        stale_after_seconds: float = STALE_AFTER_SECONDS,
        resume_window_seconds: float = SESSION_RESUME_WINDOW_SECONDS,
        clock_skew_warn_seconds: float = CLOCK_SKEW_WARN_SECONDS,
    ) -> None:
        self.hub = hub
        self.clock = clock
        self.wall_clock = wall_clock
        self.stale_after_seconds = float(stale_after_seconds)
        self.resume_window_seconds = float(resume_window_seconds)
        self.clock_skew_warn_seconds = float(clock_skew_warn_seconds)

        self._sessions: dict[str, SessionConnectionInfo] = {}
        self._client_to_session: dict[str, str] = {}

    def on_connect(
        self,
        client_id: str,
        session_id: str,
        source: StreamSource = "phone",
    ) -> ConnectionEvent:
        """Handle new client socket connection or resumption."""
        now = self.clock()
        info = self._sessions.get(session_id)
        if info is None:
            info = SessionConnectionInfo(
                session_id=session_id,
                client_id=client_id,
                source=source,
                connected=True,
                last_sample_time=None,
                disconnect_time=None,
                current_state="WAITING",
            )
            self._sessions[session_id] = info
        else:
            info.client_id = client_id
            info.connected = True
            info.disconnect_time = None
            info.source = source

        self._client_to_session[client_id] = session_id

        # Determine new state
        new_state = self._evaluate_state(info, now)
        event = self._build_event(info, new_state, now)
        info.current_state = new_state
        return event

    def on_sample(
        self,
        session_id: str,
        sent_at: str | None = None,
        received_at: str | datetime | None = None,
    ) -> tuple[ConnectionEvent | None, bool]:
        """Record sample receipt, compute clock skew, and update connection freshness.

        Returns (ConnectionEvent if state transitioned else None, clock_skew_flag_raised).
        """
        now = self.clock()
        info = self._sessions.get(session_id)
        if info is None:
            info = SessionConnectionInfo(
                session_id=session_id,
                client_id="unknown",
                connected=True,
                last_sample_time=now,
            )
            self._sessions[session_id] = info

        info.last_sample_time = now
        info.samples_count += 1

        # Clock skew estimate between sent_at and received_at
        skew_flag_raised = False
        if sent_at is not None:
            try:
                dt_sent = datetime.fromisoformat(sent_at)
                if isinstance(received_at, datetime):
                    dt_rec = received_at
                elif isinstance(received_at, str):
                    dt_rec = datetime.fromisoformat(received_at)
                else:
                    dt_rec = self.wall_clock()

                if dt_sent.tzinfo is None and dt_rec.tzinfo is not None:
                    dt_sent = dt_sent.replace(tzinfo=UTC)
                elif dt_sent.tzinfo is not None and dt_rec.tzinfo is None:
                    dt_rec = dt_rec.replace(tzinfo=UTC)

                skew_s = (dt_rec - dt_sent).total_seconds()
                info.latest_skew_s = round(skew_s, 3)

                if abs(skew_s) > self.clock_skew_warn_seconds:
                    skew_flag_raised = True
                    info.clock_skew_flag = True
                    logger.warning(
                        "Clock skew flag raised for session %s: |skew|=%.3fs > threshold=%.1fs",
                        session_id,
                        abs(skew_s),
                        self.clock_skew_warn_seconds,
                    )
            except Exception as e:
                logger.debug("Failed to calculate clock skew: %s", e)

        old_state = info.current_state
        new_state = self._evaluate_state(info, now)
        info.current_state = new_state

        event = None
        if new_state != old_state or info.samples_count == 1:
            event = self._build_event(info, new_state, now)

        return event, skew_flag_raised

    def on_disconnect(self, client_id: str, session_id: str | None = None) -> ConnectionEvent:
        """Handle client socket disconnection."""
        now = self.clock()
        sid = session_id or self._client_to_session.get(client_id)
        if sid and sid in self._sessions:
            info = self._sessions[sid]
            info.connected = False
            info.disconnect_time = now
            new_state = self._evaluate_state(info, now)
            info.current_state = new_state
            return self._build_event(info, new_state, now)

        # Fallback event
        return ConnectionEvent(
            server_time=self.wall_clock().isoformat(),
            session_id=sid,
            state="RECONNECTING",
            last_sample_age_s=None,
        )

    def on_session_close(self, session_id: str) -> ConnectionEvent:
        """Explicit session termination (e.g. client bye)."""
        now = self.clock()
        info = self._sessions.get(session_id)
        if info is not None:
            info.connected = False
            info.current_state = "WAITING"
            return self._build_event(info, "WAITING", now)

        return ConnectionEvent(
            server_time=self.wall_clock().isoformat(),
            session_id=session_id,
            state="WAITING",
            last_sample_age_s=None,
        )

    def get_state(self, session_id: str | None) -> tuple[ConnectionState, float | None]:
        """Compute authoritative state and sample age for a session."""
        if not session_id or session_id not in self._sessions:
            return "WAITING", None

        now = self.clock()
        info = self._sessions[session_id]
        state = self._evaluate_state(info, now)
        age = (now - info.last_sample_time) if info.last_sample_time is not None else None
        return state, round(age, 2) if age is not None else None

    def check_stale(self) -> list[ConnectionEvent]:
        """Periodic tick evaluating all active sessions for state transitions.

        Emits and returns ConnectionEvents for sessions whose state changed (e.g. LIVE -> STALE).
        """
        now = self.clock()
        events: list[ConnectionEvent] = []
        for info in self._sessions.values():
            new_state = self._evaluate_state(info, now)
            if new_state != info.current_state:
                info.current_state = new_state
                evt = self._build_event(info, new_state, now)
                events.append(evt)
        return events

    def _evaluate_state(self, info: SessionConnectionInfo, now: float) -> ConnectionState:
        """Pure evaluation of session state based on socket and timing."""
        if info.source == "replay":
            return "REPLAY-SOURCE"

        if info.connected:
            if info.last_sample_time is None:
                return "LIVE"
            age = now - info.last_sample_time
            if age <= self.stale_after_seconds:
                return "LIVE"
            return "STALE"

        # Disconnected socket
        if info.disconnect_time is not None:
            disc_age = now - info.disconnect_time
            if disc_age <= self.resume_window_seconds:
                return "RECONNECTING"
            return "WAITING"

        return "WAITING"

    def _build_event(
        self,
        info: SessionConnectionInfo,
        state: ConnectionState,
        now: float,
    ) -> ConnectionEvent:
        age = (now - info.last_sample_time) if info.last_sample_time is not None else None
        return ConnectionEvent(
            server_time=self.wall_clock().isoformat(),
            session_id=info.session_id,
            state=state,
            last_sample_age_s=round(age, 2) if age is not None else None,
            source=info.source,
        )

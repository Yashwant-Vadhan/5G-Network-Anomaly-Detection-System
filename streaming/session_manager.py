"""In-memory session buffer and state tracking for active client connections (T11-002).

Implements SessionBuffer and SessionManager per TECH_RULES_v2:
- Bounded in-memory buffer of Contract C2 rows per (client_id, session).
- Ignores duplicate sequence numbers without adding rows.
- Maintains strict device-timestamp ordering even when samples arrive out of order.
- Enforces SESSION_MAX_ROWS rollover, closing the full session and opening a new one.
- Pure, synchronous, and accepts an injectable clock.
"""

from __future__ import annotations

import bisect
import logging
import time
from collections.abc import Callable
from typing import Any

import pandas as pd

from ml.config import SESSION_MAX_ROWS

logger = logging.getLogger(__name__)


def slugify_device(val: str) -> str:
    """Standard device slugifier matching batch preprocessing logic."""
    return "".join(c.lower() if c.isalnum() else "-" for c in str(val)).strip("-") or "device"


class SessionBuffer:
    """In-memory bounded buffer for a single active streaming session.

    Maintains rows in strict device-timestamp order, tracks sequence numbers,
    and handles duplicate detection and cap enforcement.
    """

    def __init__(
        self,
        client_id: str,
        session_id: str,
        device: str,
        max_rows: int = SESSION_MAX_ROWS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.client_id = client_id
        self.session_id = session_id
        self.device = device
        self.max_rows = max_rows
        self.clock = clock

        self.created_at: float = clock()
        self.last_active_at: float = self.created_at
        self.last_seq: int | None = None
        self.is_closed: bool = False

        self._seen_seqs: set[int] = set()
        self._timestamps: list[Any] = []
        self._rows: list[dict[str, Any]] = []

    @property
    def seen_seqs(self) -> set[int]:
        """Set of sequence numbers observed by this session buffer."""
        return set(self._seen_seqs)

    def is_full(self) -> bool:
        """Return True if the buffer has reached or exceeded max_rows."""
        return len(self._rows) >= self.max_rows

    def has_seq(self, seq: int) -> bool:
        """Check if a sequence number has already been seen in this session."""
        return seq in self._seen_seqs

    def append(self, row: dict[str, Any] | pd.Series, seq: int) -> bool:
        """Append a validated C2 row to the session buffer.

        Args:
            row: Dictionary or pandas Series representing a validated Contract C2 row.
            seq: Positive sequence number from IngestSample message.

        Returns:
            True if row was successfully appended; False if duplicate seq or session closed.
        """
        if self.is_closed:
            logger.warning(
                "Attempted to append to closed session %s (client=%s, seq=%d)",
                self.session_id,
                self.client_id,
                seq,
            )
            return False

        if seq in self._seen_seqs:
            logger.debug(
                "Ignoring duplicate sequence %d in session %s (client=%s)",
                seq,
                self.session_id,
                self.client_id,
            )
            return False

        row_dict = row.to_dict() if isinstance(row, pd.Series) else dict(row)

        ts = row_dict.get("timestamp")
        # Ensure timestamp is comparable
        if isinstance(ts, str):
            ts_val = pd.to_datetime(ts, errors="coerce")
        else:
            ts_val = ts

        # Insert maintaining timestamp order
        idx = bisect.bisect_right(self._timestamps, ts_val)
        self._timestamps.insert(idx, ts_val)
        self._rows.insert(idx, row_dict)

        self._seen_seqs.add(seq)
        if self.last_seq is None or seq > self.last_seq:
            self.last_seq = seq

        self.last_active_at = self.clock()
        return True

    def close(self) -> None:
        """Mark this session buffer as closed."""
        self.is_closed = True

    def to_dataframe(self) -> pd.DataFrame:
        """Export buffered rows as a sorted pandas DataFrame with recalculated sample_idx.

        Returns:
            DataFrame containing all buffered rows ordered by device timestamp.
        """
        if not self._rows:
            return pd.DataFrame()

        df = pd.DataFrame(self._rows)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.sort_values(by="timestamp", kind="stable", ignore_index=True)

        df["session_id"] = self.session_id
        df["sample_idx"] = range(len(df))
        return df

    def get_latest_row(self) -> dict[str, Any] | None:
        """Return the most recent sample by timestamp, or None if buffer is empty."""
        if not self._rows:
            return None
        return dict(self._rows[-1])

    def __len__(self) -> int:
        return len(self._rows)


class SessionManager:
    """Manages active streaming sessions per client connection.

    Coordinates session creation, sequence tracking, sample routing, and
    automatic rollover when a session reaches SESSION_MAX_ROWS.
    """

    def __init__(
        self,
        max_rows: int = SESSION_MAX_ROWS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.max_rows = max_rows
        self.clock = clock
        self._active_sessions: dict[str, SessionBuffer] = {}
        self._session_counters: dict[str, int] = {}

    def _next_session_id(self, device: str) -> str:
        slug = slugify_device(device)
        count = self._session_counters.get(slug, 0) + 1
        self._session_counters[slug] = count
        return f"{slug}-{count}"

    def get_or_create_session(
        self,
        client_id: str,
        device: str,
        session_id: str | None = None,
    ) -> SessionBuffer:
        """Retrieve existing active session for client or create a new session buffer."""
        buffer = self._active_sessions.get(client_id)
        if buffer is not None and not buffer.is_closed:
            if session_id is None or buffer.session_id == session_id:
                return buffer

        if session_id is None:
            session_id = self._next_session_id(device)
        else:
            slug = slugify_device(device)
            # Track counter if session_id matches slug-N format
            if session_id.startswith(f"{slug}-"):
                try:
                    num = int(session_id.split("-")[-1])
                    self._session_counters[slug] = max(self._session_counters.get(slug, 0), num)
                except ValueError:
                    pass

        new_buffer = SessionBuffer(
            client_id=client_id,
            session_id=session_id,
            device=device,
            max_rows=self.max_rows,
            clock=self.clock,
        )
        self._active_sessions[client_id] = new_buffer
        return new_buffer

    def roll_session(self, client_id: str, device: str) -> SessionBuffer:
        """Close current session for client and create a new session buffer."""
        old_buffer = self._active_sessions.get(client_id)
        if old_buffer is not None:
            old_buffer.close()
            logger.warning(
                "Session %s reached cap (%d rows); rolling over for client %s",
                old_buffer.session_id,
                self.max_rows,
                client_id,
            )

        new_session_id = self._next_session_id(device)
        new_buffer = SessionBuffer(
            client_id=client_id,
            session_id=new_session_id,
            device=device,
            max_rows=self.max_rows,
            clock=self.clock,
        )
        self._active_sessions[client_id] = new_buffer
        return new_buffer

    def append_sample(
        self,
        client_id: str,
        row: dict[str, Any] | pd.Series,
        seq: int,
        device: str | None = None,
    ) -> tuple[SessionBuffer, bool]:
        """Append sample to active session, rolling over if buffer capacity is reached.

        Args:
            client_id: Unique client identifier.
            row: Validated Contract C2 sample row.
            seq: Ingest message sequence number.
            device: Device name (defaults to row['device'] if omitted).

        Returns:
            Tuple of (active_session_buffer, appended_bool).
        """
        row_dict = row.to_dict() if isinstance(row, pd.Series) else row
        dev = device or str(row_dict.get("device", "device"))

        buffer = self.get_or_create_session(client_id=client_id, device=dev)

        if buffer.has_seq(seq):
            return buffer, False

        if buffer.is_full():
            buffer = self.roll_session(client_id=client_id, device=dev)

        appended = buffer.append(row_dict, seq)
        return buffer, appended

    def get_session(self, client_id: str) -> SessionBuffer | None:
        """Get the active session buffer for a client ID."""
        return self._active_sessions.get(client_id)

    def close_session(self, client_id: str) -> SessionBuffer | None:
        """Close and deactivate the session for a given client ID."""
        buffer = self._active_sessions.pop(client_id, None)
        if buffer is not None:
            buffer.close()
        return buffer

    def list_active_sessions(self) -> list[SessionBuffer]:
        """Return list of all currently active session buffers."""
        return [b for b in self._active_sessions.values() if not b.is_closed]

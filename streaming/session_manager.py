"""In-memory session buffer and state tracking for active client connections (T11-002, T11-004).

Implements SessionBuffer and SessionManager per TECH_RULES_v2:
- Bounded in-memory buffer of Contract C2 rows per (client_id, session).
- Ignores duplicate sequence numbers without adding rows.
- Maintains strict device-timestamp ordering even when samples arrive out of order.
- Applies batch session-gap rule (SESSION_GAP_SECONDS=30) and source_file changes
  to delimit sessions identically to batch preprocessing.
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

from ml.config import (
    SESSION_GAP_SECONDS,
    SESSION_MAX_ROWS,
    SESSION_RESUME_WINDOW_SECONDS,
)
from ml.preprocessing import add_sessions

logger = logging.getLogger(__name__)


def slugify_device(val: str) -> str:
    """Standard device slugifier matching batch preprocessing logic."""
    return "".join(c.lower() if c.isalnum() else "-" for c in str(val)).strip("-") or "device"


def apply_session_gap(
    df: pd.DataFrame,
    gap_seconds: int = SESSION_GAP_SECONDS,
) -> pd.DataFrame:
    """Apply the batch session-gap rule directly to a DataFrame.

    Calls ml.preprocessing.add_sessions to ensure byte-for-byte identical session
    partitioning between stream and batch pipelines.
    """
    return add_sessions(df, gap_seconds=gap_seconds)


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
        source_file: str | None = None,
    ) -> None:
        self.client_id = client_id
        self.session_id = session_id
        self.device = device
        self.max_rows = max_rows
        self.clock = clock
        self.source_file = source_file

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

    Coordinates session creation, sequence tracking, sample routing, session-gap
    break detection (>30s gap), source_file changes, and automatic rollover.
    """

    def __init__(
        self,
        max_rows: int = SESSION_MAX_ROWS,
        gap_seconds: int = SESSION_GAP_SECONDS,
        clock: Callable[[], float] = time.time,
        resume_window_seconds: int = SESSION_RESUME_WINDOW_SECONDS,
    ) -> None:
        self.max_rows = max_rows
        self.gap_seconds = gap_seconds
        self.clock = clock
        self.resume_window_seconds = resume_window_seconds
        self._active_sessions: dict[str, SessionBuffer] = {}
        self._session_counters: dict[str, int] = {}

    def _next_session_id(self, device: str) -> str:
        slug = slugify_device(device)
        count = self._session_counters.get(slug, 0) + 1
        self._session_counters[slug] = count
        return f"{slug}-{count}"

    def get_or_resume_session(
        self,
        client_id: str,
        device: str,
        resume_from_seq: int = 0,
        source_file: str | None = None,
    ) -> SessionBuffer:
        """Retrieve active session or resume within SESSION_RESUME_WINDOW_SECONDS."""
        buffer = self._active_sessions.get(client_id)
        if buffer is not None:
            now = self.clock()
            age = now - buffer.last_active_at
            if age <= self.resume_window_seconds:
                if buffer.is_closed and resume_from_seq > 0:
                    buffer.is_closed = False
                return buffer
            # Expired past window -> roll session
            return self.roll_session(
                client_id=client_id,
                device=device,
                reason="resume_window_expired",
                source_file=source_file,
            )

        return self.get_or_create_session(client_id, device, source_file=source_file)

    def get_or_create_session(
        self,
        client_id: str,
        device: str,
        session_id: str | None = None,
        source_file: str | None = None,
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
            source_file=source_file,
        )
        self._active_sessions[client_id] = new_buffer
        return new_buffer

    def roll_session(
        self,
        client_id: str,
        device: str,
        reason: str = "cap",
        source_file: str | None = None,
    ) -> SessionBuffer:
        """Close current session for client and create a new session buffer."""
        old_buffer = self._active_sessions.get(client_id)
        if old_buffer is not None:
            old_buffer.close()
            if reason in ("cap", "buffer_cap"):
                logger.warning(
                    "Session %s reached cap (%d rows); rolling over for client %s (reason: %s)",
                    old_buffer.session_id,
                    old_buffer.max_rows,
                    client_id,
                    reason,
                )
            else:
                logger.warning(
                    "Session %s closed (reason: %s); rolling over for client %s",
                    old_buffer.session_id,
                    reason,
                    client_id,
                )

        new_session_id = self._next_session_id(device)
        new_buffer = SessionBuffer(
            client_id=client_id,
            session_id=new_session_id,
            device=device,
            max_rows=self.max_rows,
            clock=self.clock,
            source_file=source_file,
        )
        self._active_sessions[client_id] = new_buffer
        return new_buffer

    def start_new_session(
        self,
        client_id: str,
        device: str,
        source_file: str | None = None,
    ) -> SessionBuffer:
        """Explicitly open a new session (e.g. hello without resume_from_seq)."""
        return self.roll_session(
            client_id=client_id,
            device=device,
            reason="new_connection",
            source_file=source_file,
        )

    def append_sample(
        self,
        client_id: str,
        row: dict[str, Any] | pd.Series,
        seq: int,
        device: str | None = None,
    ) -> tuple[SessionBuffer, bool]:
        """Append sample to active session with gap detection and rollover.

        Args:
            client_id: Unique client identifier.
            row: Validated Contract C2 sample row.
            seq: Ingest message sequence number.
            device: Device name (defaults to row['device'] if omitted).

        Returns:
            Tuple of (active_session_buffer, appended_bool).
        """
        row_dict = row.to_dict() if isinstance(row, pd.Series) else dict(row)
        dev = device or str(row_dict.get("device", "device"))
        source_file = row_dict.get("source_file")

        buffer = self.get_or_create_session(
            client_id=client_id,
            device=dev,
            source_file=source_file,
        )

        if buffer.has_seq(seq):
            return buffer, False

        # Check source_file change
        if source_file and buffer.source_file and str(source_file) != str(buffer.source_file):
            logger.info(
                "Source file changed (%s -> %s); rolling session for client %s",
                buffer.source_file,
                source_file,
                client_id,
            )
            buffer = self.roll_session(
                client_id=client_id,
                device=dev,
                reason="source_file_change",
                source_file=source_file,
            )

        # Check batch session-gap rule (>30s gap between consecutive samples)
        if len(buffer) > 0:
            last_row = buffer.get_latest_row()
            if last_row is not None and "timestamp" in last_row:
                last_ts = pd.to_datetime(last_row["timestamp"], errors="coerce")
                new_ts = pd.to_datetime(row_dict.get("timestamp"), errors="coerce")
                if pd.notna(last_ts) and pd.notna(new_ts):
                    delta_seconds = (new_ts - last_ts).total_seconds()
                    if delta_seconds > self.gap_seconds:
                        logger.info(
                            "Session gap detected (%.1fs > %ds); rolling session for client %s",
                            delta_seconds,
                            self.gap_seconds,
                            client_id,
                        )
                        buffer = self.roll_session(
                            client_id=client_id,
                            device=dev,
                            reason=f"time_gap_{delta_seconds:.1f}s",
                            source_file=source_file,
                        )

        if buffer.is_full():
            buffer = self.roll_session(
                client_id=client_id,
                device=dev,
                reason="buffer_cap",
                source_file=source_file,
            )

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

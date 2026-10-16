"""Telemetry metrics and performance counters for the streaming pipeline (T11-018).

Calculates end-to-end and per-stage processing latency percentiles (p50, p95, max),
detects sequence number gaps, measures device-server clock skew, and tracks queue
depths and subscriber drop statistics for live health monitoring.
"""

from __future__ import annotations

import math
from collections import deque
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from streaming.schema import MetricsResponse, ScoredSample

DEFAULT_METRICS_WINDOW_SIZE = 1000


def calculate_percentile(sorted_values: list[float], percentile: float) -> float:
    """Calculate a percentile value using standard nearest-rank / linear interpolation."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    k = (len(sorted_values) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return round(d0 + d1, 3)


class StreamMetrics:
    """Session-scoped performance and quality instrumentation (T11-018).

    Maintains rolling percentiles over a bounded window, sequence gaps, duplicates,
    drops, and clock skew estimates.
    """

    def __init__(self, window_size: int = DEFAULT_METRICS_WINDOW_SIZE) -> None:
        self.window_size = window_size
        self._latencies_ms: deque[float] = deque(maxlen=window_size)
        self._skews_s: deque[float] = deque(maxlen=window_size)

        self._last_seq: int | None = None
        self._seen_seqs: set[int] = set()

        self.sequence_gaps: list[dict[str, int]] = []
        self.duplicates_count: int = 0
        self.drops_count: int = 0
        self.queue_depth: int = 0

    def reset(self) -> None:
        """Reset all metrics and windows for a new or reconnected session."""
        self._latencies_ms.clear()
        self._skews_s.clear()
        self._last_seq = None
        self._seen_seqs.clear()
        self.sequence_gaps.clear()
        self.duplicates_count = 0
        self.drops_count = 0
        self.queue_depth = 0

    def record_latency(self, latency_ms: float) -> None:
        """Record an observed latency measurement in milliseconds."""
        if latency_ms >= 0:
            self._latencies_ms.append(float(latency_ms))

    def record_drop(self, count: int = 1) -> None:
        """Record dropped samples or queue overflows."""
        self.drops_count += max(0, count)

    def set_queue_depth(self, depth: int) -> None:
        """Update current queue depth gauge."""
        self.queue_depth = max(0, depth)

    def record_sample(
        self,
        sample: ScoredSample | dict[str, Any],
        latency_ms: float | None = None,
        clock_skew_s: float | None = None,
    ) -> None:
        """Record a processed sample, updating sequence numbers, latency, and skew."""
        if isinstance(sample, BaseModel):
            s_dict = sample.model_dump(mode="python")
        else:
            s_dict = sample

        # 1. Sequence number and duplicate / gap tracking
        seq = s_dict.get("seq")
        if seq is not None and isinstance(seq, int):
            if seq in self._seen_seqs or (self._last_seq is not None and seq <= self._last_seq):
                self.duplicates_count += 1
            elif self._last_seq is not None and seq > self._last_seq + 1:
                gap_size = seq - self._last_seq - 1
                self.sequence_gaps.append(
                    {
                        "expected_seq": self._last_seq + 1,
                        "received_seq": seq,
                        "gap_size": gap_size,
                    }
                )

            self._seen_seqs.add(seq)
            if self._last_seq is None or seq > self._last_seq:
                self._last_seq = seq

        # 2. Latency calculation (if explicitly provided or derived from timestamps)
        if latency_ms is not None:
            self.record_latency(latency_ms)
        else:
            rec_str = s_dict.get("received_at")
            pub_str = s_dict.get("published_at") or s_dict.get("scored_at")
            if rec_str and pub_str:
                try:
                    dt_rec = datetime.fromisoformat(rec_str)
                    dt_pub = datetime.fromisoformat(pub_str)
                    calc_lat = (dt_pub - dt_rec).total_seconds() * 1000.0
                    self.record_latency(calc_lat)
                except ValueError:
                    pass

        # 3. Clock skew estimate
        if clock_skew_s is not None:
            self._skews_s.append(float(clock_skew_s))
        else:
            dev_ts = s_dict.get("timestamp")
            rec_str = s_dict.get("received_at")
            if dev_ts and rec_str:
                try:
                    dt_dev = datetime.fromisoformat(dev_ts)
                    dt_rec = datetime.fromisoformat(rec_str)
                    # If timezone missing on dev_ts, assume UTC for delta
                    if dt_dev.tzinfo is None and dt_rec.tzinfo is not None:
                        dt_dev = dt_dev.replace(tzinfo=UTC)
                    skew = (dt_rec - dt_dev).total_seconds()
                    self._skews_s.append(round(skew, 3))
                except ValueError:
                    pass

    @property
    def p50_latency_ms(self) -> float | None:
        """Median latency in milliseconds over the bounded window."""
        if not self._latencies_ms:
            return None
        return calculate_percentile(sorted(self._latencies_ms), 0.50)

    @property
    def p95_latency_ms(self) -> float | None:
        """95th percentile latency in milliseconds over the bounded window."""
        if not self._latencies_ms:
            return None
        return calculate_percentile(sorted(self._latencies_ms), 0.95)

    @property
    def max_latency_ms(self) -> float | None:
        """Maximum observed latency in milliseconds over the bounded window."""
        if not self._latencies_ms:
            return None
        return round(max(self._latencies_ms), 3)

    @property
    def skew_estimate_s(self) -> float | None:
        """Average clock skew in seconds over recent samples."""
        if not self._skews_s:
            return None
        return round(sum(self._skews_s) / len(self._skews_s), 3)

    def to_response(self) -> MetricsResponse:
        """Construct a validated MetricsResponse object."""
        return MetricsResponse(
            p50_latency_ms=self.p50_latency_ms,
            p95_latency_ms=self.p95_latency_ms,
            max_latency_ms=self.max_latency_ms,
            sequence_gaps=list(self.sequence_gaps),
            duplicates_count=self.duplicates_count,
            drops_count=self.drops_count,
            skew_estimate_s=self.skew_estimate_s,
            queue_depth=self.queue_depth,
        )


# Global registry of active stream metrics keyed by session_id
_SESSION_METRICS: dict[str, StreamMetrics] = {}
_DEFAULT_METRICS = StreamMetrics()


def get_stream_metrics(session_id: str | None = None) -> StreamMetrics:
    """Retrieve or initialize the StreamMetrics instance for a given session."""
    if session_id is None:
        return _DEFAULT_METRICS
    if session_id not in _SESSION_METRICS:
        _SESSION_METRICS[session_id] = StreamMetrics()
    return _SESSION_METRICS[session_id]


def reset_stream_metrics(session_id: str | None = None) -> None:
    """Reset metrics for a specific session or global default."""
    if session_id is None:
        _DEFAULT_METRICS.reset()
    elif session_id in _SESSION_METRICS:
        _SESSION_METRICS[session_id].reset()

"""Unit tests for streaming metrics and latency instrumentation (T11-018).

Tests latency percentiles over a bounded window, sequence gap detection, duplicate
detection, clock skew estimation, session resets, and the /api/v1/metrics endpoint.
No wall-clock sleeps are used.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from streaming.metrics import (
    StreamMetrics,
    calculate_percentile,
    get_stream_metrics,
    reset_stream_metrics,
)
from streaming.server import create_app


def test_percentile_calculation_deterministic():
    """Verify p50, p95, and max calculations across known input vectors."""
    values = [float(x) for x in range(1, 101)]  # 1 to 100
    p50 = calculate_percentile(values, 0.50)
    p95 = calculate_percentile(values, 0.95)

    assert p50 == 50.5
    assert p95 == 95.05


def test_bounded_window_eviction():
    """Metrics eviction occurs when sample count exceeds the configured window size."""
    window_size = 5
    metrics = StreamMetrics(window_size=window_size)

    # Insert 5 measurements: 10, 20, 30, 40, 50
    for val in [10.0, 20.0, 30.0, 40.0, 50.0]:
        metrics.record_latency(val)

    assert metrics.p50_latency_ms == 30.0
    assert metrics.max_latency_ms == 50.0

    # Insert 5 larger measurements: 100, 200, 300, 400, 500 (old ones evicted)
    for val in [100.0, 200.0, 300.0, 400.0, 500.0]:
        metrics.record_latency(val)

    # Max and p50 reflect only the 5 newest samples
    assert metrics.p50_latency_ms == 300.0
    assert metrics.max_latency_ms == 500.0


def test_sequence_gaps_and_duplicates():
    """Sequence tracking identifies duplicates and records missing sequence gaps."""
    metrics = StreamMetrics(window_size=50)

    # Sequence arrivals: 1, 2, 5 (gap 3..4), 5 (duplicate), 6
    metrics.record_sample({"seq": 1, "timestamp": "2026-10-09T10:00:00Z"})
    metrics.record_sample({"seq": 2, "timestamp": "2026-10-09T10:00:03Z"})
    metrics.record_sample({"seq": 5, "timestamp": "2026-10-09T10:00:12Z"})
    metrics.record_sample({"seq": 5, "timestamp": "2026-10-09T10:00:12Z"})
    metrics.record_sample({"seq": 6, "timestamp": "2026-10-09T10:00:15Z"})

    assert metrics.duplicates_count == 1
    assert len(metrics.sequence_gaps) == 1
    gap = metrics.sequence_gaps[0]
    assert gap["expected_seq"] == 3
    assert gap["received_seq"] == 5
    assert gap["gap_size"] == 2


def test_clock_skew_and_drops():
    """Drops and clock skew estimates are recorded accurately without sleeping."""
    metrics = StreamMetrics(window_size=50)

    metrics.record_drop(3)
    metrics.record_drop(2)
    assert metrics.drops_count == 5

    # Device timestamp is 2 seconds behind server received timestamp
    metrics.record_sample(
        sample={
            "seq": 10,
            "timestamp": "2026-10-09T10:00:00+00:00",
            "received_at": "2026-10-09T10:00:02+00:00",
            "published_at": "2026-10-09T10:00:02.015+00:00",
        }
    )

    assert metrics.skew_estimate_s == 2.0
    assert metrics.p50_latency_ms == 15.0


def test_metrics_reset_per_session():
    """Calling reset() wipes all counters, latencies, and gaps."""
    metrics = StreamMetrics()
    metrics.record_latency(45.0)
    metrics.record_drop(4)
    metrics.record_sample({"seq": 10})
    metrics.set_queue_depth(8)

    metrics.reset()

    assert metrics.p50_latency_ms is None
    assert metrics.p95_latency_ms is None
    assert metrics.max_latency_ms is None
    assert metrics.duplicates_count == 0
    assert metrics.drops_count == 0
    assert metrics.queue_depth == 0
    assert len(metrics.sequence_gaps) == 0


def test_api_v1_metrics_endpoint():
    """GET /api/v1/metrics returns current telemetry instrumentation."""
    app = create_app()
    client = TestClient(app)

    reset_stream_metrics("test-sess")
    session_metrics = get_stream_metrics("test-sess")
    session_metrics.record_latency(12.5)
    session_metrics.record_drop(1)
    session_metrics.set_queue_depth(3)

    resp = client.get("/api/v1/metrics?session_id=test-sess")
    assert resp.status_code == 200
    data = resp.json()

    assert data["p50_latency_ms"] == 12.5
    assert data["drops_count"] == 1
    assert data["queue_depth"] == 3
    assert data["duplicates_count"] == 0

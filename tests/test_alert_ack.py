"""Unit tests for alert acknowledgement API (T13-007, Contract C8/C9).

Acceptance Criteria:
- Second ack returns 200 without appending a second record (idempotent).
- Unknown alert_id returns 404 with standard C8 error envelope.
- Rate-limiting enforces max request caps.
- Hub receives alert update event on first acknowledgement.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from streaming.hub import LiveHub
from streaming.schema import AlertRecord, serialize_alert_jsonl
from streaming.server import ServerConfig, create_app


def _make_dummy_alert(alert_id: str = "alt-ack-01") -> AlertRecord:
    """Helper constructing schema-valid AlertRecord."""
    return AlertRecord(
        alert_id=alert_id,
        created_at="2026-10-17T15:30:00+00:00",
        event_id="evt-ack-100",
        session_id="sess-ack-1",
        source="phone",
        kind="NEW",
        severity="HIGH",
        anomaly_type="SIGNAL_DEGRADATION",
        event_status="PROVISIONAL",
        title="Signal Degradation Alert",
        body="RSRP dropped sharply below -115 dBm on cell 4501",
        evidence=["ss_rsrp < -115 dBm"],
        recommendation={"action": "reorient"},
        policy={"tier": "HIGH"},
    )


def test_unknown_alert_id_returns_404_with_c8_error_body() -> None:
    """Unknown alert_id yields 404 status code and C8 error envelope."""
    app = create_app(ServerConfig(allow_remote_view=True))
    client = TestClient(app)

    res = client.post("/api/v1/alerts/nonexistent-alert-999/ack")
    assert res.status_code == 404
    body = res.json()
    assert "error" in body
    assert body["error"]["code"] == "HTTP_404"
    assert "nonexistent-alert-999" in body["error"]["message"]
    assert "correlation_id" in body["error"]


def test_alert_ack_idempotency_and_no_duplicate_records(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """First ack sets acknowledged_at; second ack returns 200 without a second record."""
    test_jsonl = tmp_path / "live" / "alerts.jsonl"
    test_jsonl.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("streaming.server.DATA_DIR", tmp_path)

    hub = LiveHub()
    app = create_app(ServerConfig(allow_remote_view=True), hub=hub)
    client = TestClient(app)

    # Seed an unacknowledged alert
    alert = _make_dummy_alert("alt-idempotent-01")
    app.state.alerts[alert.alert_id] = alert
    test_jsonl.write_text(serialize_alert_jsonl(alert), encoding="utf-8")

    async def _test() -> None:
        _sub_id, queue = await hub.subscribe()

        # 1. First ack -> 200 OK, sets acknowledged_at, appends record, broadcasts
        res1 = client.post("/api/v1/alerts/alt-idempotent-01/ack")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["alert_id"] == "alt-idempotent-01"
        assert data1["acknowledged_at"] is not None
        ack_time = data1["acknowledged_at"]

        # Check hub broadcast event
        ev = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert ev["type"] == "alert"
        assert ev["alert"]["alert_id"] == "alt-idempotent-01"
        assert ev["alert"]["acknowledged_at"] == ack_time

        # Check alerts.jsonl line count: seeded line + 1 ack line = 2 lines
        lines_after_first = test_jsonl.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines_after_first) == 2

        # 2. Second ack -> 200 OK, same acknowledged_at, NO second record appended!
        res2 = client.post("/api/v1/alerts/alt-idempotent-01/ack")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["alert_id"] == "alt-idempotent-01"
        assert data2["acknowledged_at"] == ack_time

        # Line count remains exactly 2 (no second record written)
        lines_after_second = test_jsonl.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines_after_second) == 2

        # No additional broadcast event queued
        assert queue.empty()

    asyncio.run(_test())


def test_get_alerts_filtering_by_ack_and_since(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """GET /api/v1/alerts filters properly by acknowledged status and since timestamp."""
    monkeypatch.setattr("streaming.server.DATA_DIR", tmp_path)
    app = create_app(ServerConfig(allow_remote_view=True))
    client = TestClient(app)

    a1 = _make_dummy_alert("alt-list-01")
    a2 = _make_dummy_alert("alt-list-02")
    a2.created_at = "2026-10-17T16:00:00+00:00"
    a2.acknowledged_at = "2026-10-17T16:05:00+00:00"

    app.state.alerts["alt-list-01"] = a1
    app.state.alerts["alt-list-02"] = a2

    # All alerts
    all_res = client.get("/api/v1/alerts")
    assert all_res.status_code == 200
    assert len(all_res.json()) == 2

    # Filter unacknowledged
    unack_res = client.get("/api/v1/alerts?ack=false")
    assert unack_res.status_code == 200
    assert len(unack_res.json()) == 1
    assert unack_res.json()[0]["alert_id"] == "alt-list-01"

    # Filter acknowledged
    ack_res = client.get("/api/v1/alerts?ack=true")
    assert ack_res.status_code == 200
    assert len(ack_res.json()) == 1
    assert ack_res.json()[0]["alert_id"] == "alt-list-02"

    # Filter since
    since_res = client.get("/api/v1/alerts?since=2026-10-17T15:45:00+00:00")
    assert since_res.status_code == 200
    assert len(since_res.json()) == 1
    assert since_res.json()[0]["alert_id"] == "alt-list-02"

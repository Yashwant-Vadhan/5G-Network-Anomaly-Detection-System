"""Tests for T14-009: Recovery test matrix across 6 failure and reconnect scenarios.

Validates resilience, reconnection, state transitions, duplicate filtering,
subscriber drop backpressure, and data loss accounting under failure conditions:
1. Wi-Fi drop & resume (resume_from_seq within window).
2. Server restart mid-session (in-memory rollover & graceful session init).
3. Dashboard / subscriber restart without ingest disruption.
4. Phone sleep / background pause (STALE state transition and wake resumption).
5. Duplicate seq transmission (idempotent acking, duplicate counter, no duplicate rows).
6. Slow subscriber backpressure (bounded subscriber queue, DroppedEvent notification).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from streaming.connection import ConnectionTracker
from streaming.hub import LiveHub
from streaming.metrics import get_stream_metrics, reset_stream_metrics
from streaming.schema import SCHEMA_VERSION, DroppedEvent
from streaming.server import ServerConfig, create_app
from streaming.session_manager import SessionManager


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_sample_payload(pci: int = 312, ss_rsrp: float = -95.0) -> dict[str, Any]:
    """Helper to create a standard valid Contract C7 sample payload."""
    return {
        "timestamp": "28-09-26 22:42:06",
        "device": "Samsung SM-A156E",
        "manufacturer": "Samsung",
        "android": "14",
        "operator": "Jio",
        "network_type": "5G NR",
        "deployment_mode": "UNKNOWN",
        "display_override": None,
        "registered": True,
        "ss_rsrp": ss_rsrp,
        "ss_rsrq": -10.0,
        "ss_sinr": 12.0,
        "csi_rsrp": None,
        "csi_rsrq": None,
        "csi_sinr": None,
        "pci": pci,
        "nci": 12345678,
        "nrarfcn": 631392,
    }


def test_recovery_case_1_wifi_drop_and_resume():
    """Scenario 1: Wi-Fi drop mid-session and successful resume within window."""
    session_manager = SessionManager(max_rows=100)
    config = ServerConfig(retention_enabled=False)
    app = create_app(config, session_manager=session_manager)
    client = TestClient(app)

    # Step 1: Client connects and sends seq 1..5 (triggers cumulative ack at 5)
    with client.websocket_connect("/api/v1/ingest") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "phone-recovery-01",
                    "session_label": "wifi-drop-test",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "2.0.0",
                }
            )
        )
        ack = json.loads(ws.receive_text())
        session_id_1 = ack["session_id"]
        assert ack["last_seq_acked"] == 0

        for seq in range(1, 6):
            ws.send_text(
                json.dumps(
                    {
                        "type": "sample",
                        "schema_version": SCHEMA_VERSION,
                        "seq": seq,
                        "sent_at": "2026-10-18T10:00:00+05:30",
                        "payload": make_sample_payload(),
                    }
                )
            )
        cum_ack = json.loads(ws.receive_text())
        assert cum_ack["type"] == "ack"
        assert cum_ack["seq"] == 5

    # Step 2: Abrupt socket closure represents Wi-Fi drop.
    # Client reconnects with resume_from_seq=6
    with client.websocket_connect("/api/v1/ingest") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "phone-recovery-01",
                    "session_label": "wifi-drop-test",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "2.0.0",
                    "resume_from_seq": 6,
                }
            )
        )
        resume_ack = json.loads(ws.receive_text())
        assert resume_ack["session_id"] == session_id_1
        assert resume_ack["last_seq_acked"] == 5

        # Send seq 6..10
        for seq in range(6, 11):
            ws.send_text(
                json.dumps(
                    {
                        "type": "sample",
                        "schema_version": SCHEMA_VERSION,
                        "seq": seq,
                        "sent_at": "2026-10-18T10:00:03+05:30",
                        "payload": make_sample_payload(),
                    }
                )
            )
        cum_ack2 = json.loads(ws.receive_text())
        assert cum_ack2["type"] == "ack"
        assert cum_ack2["seq"] == 10

    # Verify session preservation and zero data loss
    buf = session_manager.get_session("phone-recovery-01")
    assert buf is not None
    assert buf.session_id == session_id_1
    assert len(buf.to_dataframe()) == 10
    assert buf.seen_seqs == set(range(1, 11))


def test_recovery_case_2_server_restart_mid_session():
    """Scenario 2: Server restart mid-session.

    Server memory resets; client reconnects. New server gracefully accepts telemetry,
    and client streaming continues without deadlock.
    """
    config1 = ServerConfig(retention_enabled=False)
    app1 = create_app(config1)
    client1 = TestClient(app1)

    # 1. Start session on server instance 1 and send seq 1..5
    with client1.websocket_connect("/api/v1/ingest") as ws1:
        ws1.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "phone-reboot-01",
                    "session_label": "server-reboot-test",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "2.0.0",
                }
            )
        )
        ack1 = json.loads(ws1.receive_text())
        assert ack1["type"] == "hello_ack"

        for seq in range(1, 6):
            ws1.send_text(
                json.dumps(
                    {
                        "type": "sample",
                        "schema_version": SCHEMA_VERSION,
                        "seq": seq,
                        "sent_at": "2026-10-18T10:00:00+05:30",
                        "payload": make_sample_payload(),
                    }
                )
            )
        ack = json.loads(ws1.receive_text())
        assert ack["seq"] == 5

    # 2. Server instance 1 is stopped / replaced by freshly restarted Server instance 2
    del client1
    del app1

    config2 = ServerConfig(retention_enabled=False)
    app2 = create_app(config2)
    client2 = TestClient(app2)

    # Client attempts to reconnect with resume_from_seq=6
    # Instance 2 starts with a fresh in-memory session manager and honors resume_from_seq
    with client2.websocket_connect("/api/v1/ingest") as ws2:
        ws2.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "phone-reboot-01",
                    "session_label": "server-reboot-test",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "2.0.0",
                    "resume_from_seq": 6,
                }
            )
        )
        ack2 = json.loads(ws2.receive_text())
        assert ack2["type"] == "hello_ack"
        assert ack2["last_seq_acked"] == 5

        # Client streams on new server session
        for seq in range(6, 11):
            ws2.send_text(
                json.dumps(
                    {
                        "type": "sample",
                        "schema_version": SCHEMA_VERSION,
                        "seq": seq,
                        "sent_at": "2026-10-18T10:00:05+05:30",
                        "payload": make_sample_payload(),
                    }
                )
            )
        sample_ack = json.loads(ws2.receive_text())
        assert sample_ack["seq"] == 10


def test_recovery_case_3_dashboard_restart():
    """Scenario 3: Dashboard subscriber restarts while ingest continues uninterrupted."""
    config = ServerConfig(retention_enabled=False)
    app = create_app(config)
    client = TestClient(app)

    # Ingest connects
    with client.websocket_connect("/api/v1/ingest") as ingest_ws:
        ingest_ws.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "phone-dash-restart",
                    "session_label": "dash-restart-test",
                    "device": "Pixel 7 Pro",
                    "manufacturer": "Google",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "2.0.0",
                }
            )
        )
        ack = json.loads(ingest_ws.receive_text())
        session_id = ack["session_id"]

        # Dashboard connects
        with client.websocket_connect("/api/v1/live") as dash_ws1:
            # First message from /api/v1/live is the SnapshotEvent
            snap_raw = dash_ws1.receive_text()
            snap = json.loads(snap_raw)
            assert snap["type"] == "snapshot"

            # Ingest sends seq 1
            ingest_ws.send_text(
                json.dumps(
                    {
                        "type": "sample",
                        "schema_version": SCHEMA_VERSION,
                        "seq": 1,
                        "sent_at": "2026-10-18T10:00:00+05:30",
                        "payload": make_sample_payload(pci=500),
                    }
                )
            )

            # Dashboard receives broadcast
            raw_msg = dash_ws1.receive_text()
            data = json.loads(raw_msg)
            assert data["type"] == "sample"
            assert data["sample"]["seq"] == 1

        # Dashboard terminates/reloads. Ingest continues and sends seq 2..5
        for seq in range(2, 6):
            ingest_ws.send_text(
                json.dumps(
                    {
                        "type": "sample",
                        "schema_version": SCHEMA_VERSION,
                        "seq": seq,
                        "sent_at": f"2026-10-18T10:00:0{seq}+05:30",
                        "payload": make_sample_payload(pci=600),
                    }
                )
            )
        ack_cum = json.loads(ingest_ws.receive_text())
        assert ack_cum["seq"] == 5

        # New dashboard connects and resyncs via REST endpoint
        resp = client.get(f"/api/v1/sessions/{session_id}/samples")
        assert resp.status_code == 200
        samples_data = resp.json()["samples"]
        assert len(samples_data) == 5
        assert [s["seq"] for s in samples_data] == [1, 2, 3, 4, 5]


def test_recovery_case_4_phone_sleep_stale_and_wake():
    """Scenario 4: Phone sleeps (>10s gap), state transitions to STALE, wakes and resumes."""
    class FakeClock:
        def __init__(self):
            self.mono = 1000.0
            self.wall = datetime(2026, 10, 18, 10, 0, 0, tzinfo=UTC)

        def monotonic(self):
            return self.mono

        def wall_clock(self):
            return self.wall

        def advance(self, s):
            self.mono += s
            from datetime import timedelta
            self.wall += timedelta(seconds=s)

    clock = FakeClock()
    tracker = ConnectionTracker(
        clock=clock.monotonic,
        wall_clock=clock.wall_clock,
        stale_after_seconds=10.0,
    )

    # 1. Connect and sample arriving -> LIVE
    tracker.on_connect("phone-01", "sess-sleep", source="phone")
    tracker.on_sample("sess-sleep")
    state, age = tracker.get_state("sess-sleep")
    assert state == "LIVE"
    assert age == 0.0

    # 2. Phone sleeps for 15 seconds (> 10s stale threshold)
    clock.advance(15.0)
    state, age = tracker.get_state("sess-sleep")
    assert state == "STALE"
    assert age == 15.0

    # 3. Phone wakes up, emits sample -> reverts to LIVE
    tracker.on_sample("sess-sleep")
    state, age = tracker.get_state("sess-sleep")
    assert state == "LIVE"
    assert age == 0.0


def test_recovery_case_5_duplicate_seq_transmission():
    """Scenario 5: Duplicate seq transmission.

    Assert acknowledged idempotently without duplicate storage in buffer.
    """
    session_manager = SessionManager(max_rows=100)
    config = ServerConfig(retention_enabled=False)
    app = create_app(config, session_manager=session_manager)
    client = TestClient(app)

    reset_stream_metrics()

    with client.websocket_connect("/api/v1/ingest") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "phone-dup-test",
                    "session_label": "dup-test",
                    "device": "Pixel 7 Pro",
                    "manufacturer": "Google",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "2.0.0",
                }
            )
        )
        ack = json.loads(ws.receive_text())
        session_id = ack["session_id"]

        # Send seq 1..5
        for seq in range(1, 6):
            ws.send_text(
                json.dumps(
                    {
                        "type": "sample",
                        "schema_version": SCHEMA_VERSION,
                        "seq": seq,
                        "sent_at": "2026-10-18T10:00:00+05:30",
                        "payload": make_sample_payload(),
                    }
                )
            )
        cum_ack = json.loads(ws.receive_text())
        assert cum_ack["seq"] == 5

        # Re-send seq 3 (duplicate transmission, e.g. client timeout or network glitch)
        # Because 3 <= last_seq_acked (5), server immediately returns idempotent Ack(seq=3)
        ws.send_text(
            json.dumps(
                {
                    "type": "sample",
                    "schema_version": SCHEMA_VERSION,
                    "seq": 3,
                    "sent_at": "2026-10-18T10:00:00+05:30",
                    "payload": make_sample_payload(),
                }
            )
        )
        ack3_dup = json.loads(ws.receive_text())
        assert ack3_dup["type"] == "ack"
        assert ack3_dup["seq"] == 3

    # Check metrics recorded 1 duplicate
    metrics = get_stream_metrics(session_id)
    assert metrics.duplicates_count == 1

    # Check session store has exactly 5 samples, not 6
    buf = session_manager.get_session("phone-dup-test")
    assert buf is not None
    assert len(buf.to_dataframe()) == 5
    assert buf.seen_seqs == {1, 2, 3, 4, 5}


@pytest.mark.anyio
async def test_recovery_case_6_slow_subscriber_backpressure():
    """Scenario 6: Slow subscriber backpressure.

    Assert bounded queue drops oldest frame and receives DroppedEvent notice.
    """
    hub = LiveHub(default_queue_size=3)
    sub_id, queue = await hub.subscribe(queue_size=3)

    # Broadcast 6 messages to subscriber with queue size 3
    for i in range(1, 7):
        await hub.broadcast({"msg_id": i}, session_id="sess-hub-test")

    # Queue should be bounded to capacity
    assert queue.qsize() <= 3

    received_items = []
    while not queue.empty():
        received_items.append(await queue.get())

    # Check that a DroppedEvent was received alerting the client
    has_dropped = any(isinstance(item, DroppedEvent) for item in received_items)
    assert has_dropped
    await hub.unsubscribe(sub_id)

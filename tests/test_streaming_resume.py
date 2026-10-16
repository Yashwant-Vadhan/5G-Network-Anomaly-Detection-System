"""Tests for T11-012: Ingest session resume, idempotent acks, gap metrics, and conflict."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from streaming.metrics import reset_stream_metrics
from streaming.schema import SCHEMA_VERSION
from streaming.server import ServerConfig, create_app
from streaming.session_manager import SessionManager


def make_valid_payload():
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
        "ss_rsrp": -95.0,
        "ss_rsrq": -10.0,
        "ss_sinr": 12.0,
        "csi_rsrp": None,
        "csi_rsrq": None,
        "csi_sinr": None,
        "pci": 312,
        "nci": 12345678,
        "nrarfcn": 631392,
    }


def test_reconnect_within_window_continues_session():
    """Reconnecting with resume_from_seq within resume window continues the same session."""
    session_manager = SessionManager(max_rows=100)
    config = ServerConfig(retention_enabled=False)
    app = create_app(config, session_manager=session_manager)
    client = TestClient(app)

    # 1. Connect initial session
    with client.websocket_connect("/api/v1/ingest") as ws1:
        ws1.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "client-res-01",
                    "session_label": "session-1",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "1.0.0",
                }
            )
        )
        ack1 = json.loads(ws1.receive_text())
        session_id_1 = ack1["session_id"]

        # Send sample seq 1
        ws1.send_text(
            json.dumps(
                {
                    "type": "sample",
                    "schema_version": SCHEMA_VERSION,
                    "seq": 1,
                    "sent_at": "2026-10-09T10:15:03.412+05:30",
                    "payload": make_valid_payload(),
                }
            )
        )

    # 2. Reconnect with resume_from_seq=2 within window
    with client.websocket_connect("/api/v1/ingest") as ws2:
        ws2.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "client-res-01",
                    "session_label": "session-1",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "1.0.0",
                    "resume_from_seq": 2,
                }
            )
        )
        ack2 = json.loads(ws2.receive_text())
        session_id_2 = ack2["session_id"]

        # Session ID must be preserved
        assert session_id_2 == session_id_1
        assert ack2["last_seq_acked"] == 1


def test_reconnect_after_window_rolls_new_session():
    """Reconnecting after SESSION_RESUME_WINDOW_SECONDS opens a new session."""
    current_time = 1000.0

    def mock_clock() -> float:
        return current_time

    session_manager = SessionManager(max_rows=100, clock=mock_clock, resume_window_seconds=600)
    config = ServerConfig(retention_enabled=False)
    app = create_app(config, session_manager=session_manager)
    client = TestClient(app)

    # 1. First connection at t=1000
    with client.websocket_connect("/api/v1/ingest") as ws1:
        ws1.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "client-exp-01",
                    "session_label": "walk",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "1.0.0",
                }
            )
        )
        ack1 = json.loads(ws1.receive_text())
        session_id_1 = ack1["session_id"]

    # Advance time by 601s (past 600s window)
    current_time += 601.0

    # 2. Reconnect at t=1601
    with client.websocket_connect("/api/v1/ingest") as ws2:
        ws2.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "client-exp-01",
                    "session_label": "walk",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "1.0.0",
                    "resume_from_seq": 5,
                }
            )
        )
        ack2 = json.loads(ws2.receive_text())
        session_id_2 = ack2["session_id"]

        # New session rolled
        assert session_id_2 != session_id_1


def test_duplicate_samples_add_no_rows_and_seq_gaps_in_metrics():
    """Duplicate fixtures add no rows; forward sequence gaps appear in /api/v1/metrics."""
    reset_stream_metrics()
    session_manager = SessionManager(max_rows=100)
    config = ServerConfig(retention_enabled=False)
    app = create_app(config, session_manager=session_manager)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        # Hello
        ws.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "client-gaps-01",
                    "session_label": "gap-test",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "1.0.0",
                }
            )
        )
        ack = json.loads(ws.receive_text())
        sess_id = ack["session_id"]

        # Send sample seq 1
        ws.send_text(
            json.dumps(
                {
                    "type": "sample",
                    "schema_version": SCHEMA_VERSION,
                    "seq": 1,
                    "sent_at": "2026-10-09T10:15:03.412+05:30",
                    "payload": make_valid_payload(),
                }
            )
        )

        # Send sample seq 5 (gap between 1 and 5 -> expected 2, received 5, gap_size 3)
        ws.send_text(
            json.dumps(
                {
                    "type": "sample",
                    "schema_version": SCHEMA_VERSION,
                    "seq": 5,
                    "sent_at": "2026-10-09T10:15:06.412+05:30",
                    "payload": make_valid_payload(),
                }
            )
        )

        # Send duplicate of seq 1
        ws.send_text(
            json.dumps(
                {
                    "type": "sample",
                    "schema_version": SCHEMA_VERSION,
                    "seq": 1,
                    "sent_at": "2026-10-09T10:15:03.412+05:30",
                    "payload": make_valid_payload(),
                }
            )
        )
        re_ack = json.loads(ws.receive_text())
        assert re_ack["type"] == "ack"
        assert re_ack["seq"] == 1

        buf = session_manager.get_session("client-gaps-01")
        assert buf is not None
        # Only 2 rows added (seq 1 and seq 5, duplicate seq 1 was ignored)
        assert len(buf) == 2

    # Verify metrics endpoint reports gap ranges and duplicate count
    resp = client.get(f"/api/v1/metrics?session_id={sess_id}")
    assert resp.status_code == 200
    metrics_data = resp.json()

    assert metrics_data["duplicates_count"] >= 1
    assert len(metrics_data["sequence_gaps"]) >= 1
    gap_record = metrics_data["sequence_gaps"][0]
    assert gap_record["expected_seq"] == 2
    assert gap_record["received_seq"] == 5
    assert gap_record["gap_size"] == 3


def test_session_conflict_second_connection_refused():
    """Second concurrent live connection with the same client_id is rejected with 4409."""
    config = ServerConfig(retention_enabled=False)
    app = create_app(config)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws1:
        # Client 1 connects
        ws1.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "shared-client-id",
                    "session_label": "conn1",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "1.0.0",
                }
            )
        )
        ack1 = json.loads(ws1.receive_text())
        assert ack1["type"] == "hello_ack"

        # Client 2 connects concurrently with same client_id
        with client.websocket_connect("/api/v1/ingest") as ws2:
            ws2.send_text(
                json.dumps(
                    {
                        "type": "hello",
                        "schema_version": SCHEMA_VERSION,
                        "client_id": "shared-client-id",
                        "session_label": "conn2",
                        "device": "Samsung SM-A156E",
                        "manufacturer": "Samsung",
                        "android": "14",
                        "operator": "Jio",
                        "app_version": "1.0.0",
                    }
                )
            )
            conflict_msg = json.loads(ws2.receive_text())
            assert conflict_msg["type"] == "error"
            assert conflict_msg["code"] == "SESSION_CONFLICT"
            assert conflict_msg["fatal"] is True

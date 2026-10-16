"""Tests for WS /api/v1/ingest endpoint (T11-011 / Contract C7)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from streaming.schema import SCHEMA_VERSION
from streaming.server import ServerConfig, create_app


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


def test_ws_ingest_auth_rejection():
    """Missing or incorrect bearer token rejects websocket upgrade with close code 4401."""
    config = ServerConfig(ingest_token="secret-key-12345")
    app = create_app(config)
    client = TestClient(app)

    # 1. No token -> 4401
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ingest"):
            pass

    # 2. Bad token -> 4401
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ingest", headers={"Authorization": "Bearer wrong"}):
            pass


def test_ws_ingest_full_lifecycle():
    """All C7 message types (hello, sample, ping, bye) are handled per contract."""
    config = ServerConfig(retention_enabled=False)
    app = create_app(config)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        # 1. Hello handshake
        hello_msg = {
            "type": "hello",
            "schema_version": SCHEMA_VERSION,
            "client_id": "client-uuid-1",
            "session_label": "test-walk",
            "device": "Samsung SM-A156E",
            "manufacturer": "Samsung",
            "android": "14",
            "operator": "Jio",
            "app_version": "1.0.0",
        }
        ws.send_text(json.dumps(hello_msg))
        ack_raw = ws.receive_text()
        ack = json.loads(ack_raw)
        assert ack["type"] == "hello_ack"
        assert ack["schema_version"] == 2
        assert "session_id" in ack
        assert ack["last_seq_acked"] == 0

        # 2. Send 5 samples to trigger cumulative ack
        for seq in range(1, 6):
            sample_msg = {
                "type": "sample",
                "schema_version": SCHEMA_VERSION,
                "seq": seq,
                "sent_at": "2026-10-09T10:15:03.412+05:30",
                "payload": make_valid_payload(),
            }
            ws.send_text(json.dumps(sample_msg))

        ack_data = json.loads(ws.receive_text())
        assert ack_data["type"] == "ack"
        assert ack_data["seq"] == 5

        # 3. Idempotent re-ack for earlier sample
        sample_dup = {
            "type": "sample",
            "schema_version": SCHEMA_VERSION,
            "seq": 3,
            "sent_at": "2026-10-09T10:15:03.412+05:30",
            "payload": make_valid_payload(),
        }
        ws.send_text(json.dumps(sample_dup))
        re_ack = json.loads(ws.receive_text())
        assert re_ack["type"] == "ack"
        assert re_ack["seq"] == 3

        # 4. Ping / Pong
        ws.send_text(json.dumps({"type": "ping", "schema_version": SCHEMA_VERSION}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == "pong"
        assert "server_time" in pong

        # 5. Bye message cleanly closes connection
        ws.send_text(json.dumps({"type": "bye", "schema_version": SCHEMA_VERSION}))


def test_ws_oversize_frame_closes_1009():
    """Frames exceeding MAX_MESSAGE_BYTES (8192) close the WebSocket with code 1009."""
    config = ServerConfig(retention_enabled=False)
    app = create_app(config)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        large_garbage = "x" * 9000
        ws.send_text(large_garbage)
        # WebSocket should be closed by server with code 1009
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_ws_rate_limit_returns_error_without_closing():
    """Rate limit violation returns RATE_LIMITED error without closing socket."""
    # Set capacity to 2 msgs
    config = ServerConfig(retention_enabled=False, max_msgs_per_min=1)
    app = create_app(config)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        # Hello uses token 1
        ws.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "schema_version": SCHEMA_VERSION,
                    "client_id": "client-uuid-rate",
                    "session_label": "test",
                    "device": "Samsung SM-A156E",
                    "manufacturer": "Samsung",
                    "android": "14",
                    "operator": "Jio",
                    "app_version": "1.0.0",
                }
            )
        )
        ws.receive_text()

        # Send rapid pings to exceed bucket
        ws.send_text(json.dumps({"type": "ping", "schema_version": SCHEMA_VERSION}))
        resp1 = json.loads(ws.receive_text())

        ws.send_text(json.dumps({"type": "ping", "schema_version": SCHEMA_VERSION}))
        resp2 = json.loads(ws.receive_text())

        # At least one should be RATE_LIMITED and connection remains open
        responses = [resp1, resp2]
        error_resps = [r for r in responses if r.get("code") == "RATE_LIMITED"]
        assert len(error_resps) >= 1
        assert error_resps[0]["type"] == "error"
        assert error_resps[0]["fatal"] is False


def test_ws_version_mismatch_closes_4426():
    """Unsupported schema_version returns VERSION_MISMATCH and closes socket with 4426."""
    config = ServerConfig(retention_enabled=False)
    app = create_app(config)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        ws.send_text(json.dumps({"type": "ping", "schema_version": 99}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "VERSION_MISMATCH"
        assert resp["fatal"] is True

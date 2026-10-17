"""Auth and abuse tests for ingest and live APIs (T14-001, G19, G20).

Tests:
1. Wrong / missing token on WebSocket ingest and REST endpoints.
2. Replayed seq idempotent acknowledgement (G19).
3. Oversize frame rejected with code 1009 (G20).
4. Malformed JSON handling without crashing (BAD_MESSAGE).
5. Flood / rate limiting enforcement (RATE_LIMITED).
6. Second connection with same client_id rejected (SESSION_CONFLICT, code 4409).
7. Non-loopback read request rejection unless remote view allowed.
8. Log-scan asserting secret tokens and credentials never leak into logs (G20, G26).
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from streaming.schema import MAX_MESSAGE_BYTES, SCHEMA_VERSION
from streaming.server import ServerConfig, create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_valid_hello(
    client_id: str = "device-auth-1",
    device: str = "Pixel 7 Pro",
    session_label: str = "auth-abuse-test",
) -> dict[str, Any]:
    """Helper creating a schema-valid IngestHello message (C7)."""
    return {
        "type": "hello",
        "schema_version": SCHEMA_VERSION,
        "client_id": client_id,
        "session_label": session_label,
        "device": device,
        "manufacturer": "Google",
        "android": "14",
        "operator": "Jio",
        "app_version": "2.0.0",
        "resume_from_seq": 0,
        "queue_depth": 0,
        "dropped_from_queue": 0,
    }


def make_valid_sample(
    seq: int = 1,
    device: str = "Pixel 7 Pro",
    timestamp: str = "17-10-26 15:30:00",
) -> dict[str, Any]:
    """Helper creating a schema-valid IngestSample message (C7)."""
    return {
        "type": "sample",
        "schema_version": SCHEMA_VERSION,
        "seq": seq,
        "sent_at": "2026-10-17T15:30:00.000+05:30",
        "payload": {
            "timestamp": timestamp,
            "device": device,
            "manufacturer": "Google",
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
        },
    }


def test_ingest_websocket_missing_and_wrong_token() -> None:
    """Ingest WebSocket closes with code 4401 on missing or incorrect auth token."""
    secret_token = "secret-ingest-token-abc123"
    config = ServerConfig(ingest_token=secret_token)
    app = create_app(config)
    client = TestClient(app)

    # 1. Missing token -> 4401
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ingest"):
            pass
    assert exc_info.value.code == 4401

    # 2. Wrong token in header -> 4401
    with pytest.raises(WebSocketDisconnect) as exc_info2:
        with client.websocket_connect(
            "/api/v1/ingest",
            headers={"Authorization": "Bearer bad-token-999"},
        ):
            pass
    assert exc_info2.value.code == 4401

    # 3. Wrong token in query param -> 4401
    with pytest.raises(WebSocketDisconnect) as exc_info3:
        with client.websocket_connect("/api/v1/ingest?token=invalid-query-token"):
            pass
    assert exc_info3.value.code == 4401

    # 4. Valid token in header connects successfully
    with client.websocket_connect(
        "/api/v1/ingest",
        headers={"Authorization": f"Bearer {secret_token}"},
    ) as ws:
        ws.send_text(json.dumps(make_valid_hello(client_id="test-device-auth-1")))
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"


def test_replayed_seq_idempotent_ack() -> None:
    """Duplicate / replayed seq numbers receive idempotent acks and create no duplicates (G19)."""
    app = create_app(ServerConfig(retention_enabled=False))
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        # Hello handshake
        ws.send_json(make_valid_hello(client_id="device-replayed-seq-1"))
        hello_ack = ws.receive_json()
        assert hello_ack["type"] == "hello_ack"
        session_id = hello_ack["session_id"]
        assert hello_ack["last_seq_acked"] == 0

        # Send 5 samples to trigger cumulative ack
        for seq in range(1, 6):
            ws.send_json(make_valid_sample(seq=seq))
        cum_ack = ws.receive_json()
        assert cum_ack["type"] == "ack"
        assert cum_ack["seq"] == 5

        # Replayed Sample with seq=3 (must receive immediate idempotent ack)
        ws.send_json(make_valid_sample(seq=3))
        re_ack = ws.receive_json()
        assert re_ack["type"] == "ack"
        assert re_ack["seq"] == 3

        # Verify exactly 5 scored samples stored in session buffer (no duplicate for seq=3)
        stored = app.state.session_samples.get(session_id, [])
        assert len(stored) == 5
        seqs = [s.seq for s in stored]
        assert seqs == [1, 2, 3, 4, 5]


def test_oversize_frame_rejected_code_1009() -> None:
    """Frames larger than MAX_MESSAGE_BYTES close with WebSocket code 1009 (G20)."""
    app = create_app()
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ingest") as ws:
            # Create a frame exceeding MAX_MESSAGE_BYTES (8192 bytes)
            oversize_payload = make_valid_hello()
            oversize_payload["padding"] = "x" * (MAX_MESSAGE_BYTES + 500)
            ws.send_text(json.dumps(oversize_payload))
            ws.receive_text()

    assert exc_info.value.code == 1009


def test_malformed_json_and_bad_message() -> None:
    """Malformed JSON returns BAD_MESSAGE error frame without crashing server (G20)."""
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        # 1. Invalid syntax
        ws.send_text("{invalid json structure")
        err1 = ws.receive_json()
        assert err1["type"] == "error"
        assert err1["code"] == "BAD_MESSAGE"
        assert err1["fatal"] is False

        # 2. JSON array instead of JSON object
        ws.send_text(json.dumps([1, 2, 3]))
        err2 = ws.receive_json()
        assert err2["type"] == "error"
        assert err2["code"] == "BAD_MESSAGE"
        assert err2["fatal"] is False

        # 3. Valid hello can still be processed afterwards
        ws.send_json(make_valid_hello(client_id="device-json-recover"))
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"


def test_flood_rate_limiting() -> None:
    """Flood of messages exceeding max_msgs_per_min triggers RATE_LIMITED error (G20)."""
    # Configure low rate limit: 6 msgs/min (burst=6, rate=0.1/s)
    config = ServerConfig(max_msgs_per_min=6)
    app = create_app(config)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        ws.send_json(make_valid_hello(client_id="device-rate-limit-test"))
        ws.receive_json()  # hello_ack consumed 1 token

        rate_limited_count = 0
        # Rapidly send 12 ping messages to exhaust bucket and trigger rate limiter
        for _ in range(12):
            ws.send_json({"type": "ping", "schema_version": 2})
            resp = ws.receive_json()
            if resp.get("code") == "RATE_LIMITED":
                rate_limited_count += 1
                assert resp["fatal"] is False

        assert rate_limited_count > 0, "Rate limit error must be triggered during flood"


def test_second_connection_same_client_id_conflict() -> None:
    """Second concurrent connection with identical client_id is rejected with code 4409."""
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws1:
        ws1.send_json(make_valid_hello(client_id="duplicate-client-123"))
        ack1 = ws1.receive_json()
        assert ack1["type"] == "hello_ack"

        # Attempt second connection with same client_id
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/ingest") as ws2:
                ws2.send_json(make_valid_hello(client_id="duplicate-client-123"))
                err_conflict = ws2.receive_json()
                assert err_conflict["type"] == "error"
                assert err_conflict["code"] == "SESSION_CONFLICT"
                ws2.receive_text()

        assert exc_info.value.code == 4409

        # First connection remains active - verify with ping/pong
        ws1.send_json({"type": "ping", "schema_version": 2})
        pong = ws1.receive_json()
        assert pong["type"] == "pong"


def test_non_loopback_read_request_rejection() -> None:
    """REST read endpoints and /api/v1/live WebSocket reject non-loopback hosts by default."""
    config = ServerConfig(allow_remote_view=False)
    app = create_app(config)

    # 1. Non-loopback client IP on REST endpoint -> 403 Forbidden
    client_remote = TestClient(app, client=("192.168.1.55", 49152))
    resp = client_remote.get("/api/v1/sessions")
    assert resp.status_code == 403
    assert "Forbidden" in resp.text
    assert "loopback only" in resp.text

    # 2. Loopback client IP on REST endpoint -> 200 OK
    client_local = TestClient(app, client=("127.0.0.1", 49152))
    resp_local = client_local.get("/api/v1/sessions")
    assert resp_local.status_code == 200

    # 3. Non-loopback client IP on live WebSocket -> code 4403
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client_remote.websocket_connect("/api/v1/live"):
            pass
    assert exc_info.value.code == 4403

    # 4. When allow_remote_view=True, non-loopback clients are permitted
    app_open = create_app(ServerConfig(allow_remote_view=True))
    client_remote_open = TestClient(app_open, client=("192.168.1.55", 49152))
    resp_open = client_remote_open.get("/api/v1/sessions")
    assert resp_open.status_code == 200


def test_log_scan_no_tokens_or_credentials_leaked() -> None:
    """Security log-scan verifies secret tokens and auth query params never leak into logs."""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)

    streaming_logger = logging.getLogger("streaming")
    streaming_logger.addHandler(handler)
    streaming_logger.setLevel(logging.DEBUG)

    secret_token = "ultra-secret-token-do-not-leak-777"
    bad_token = "malicious-attacker-attempt-token-999"
    config = ServerConfig(ingest_token=secret_token)
    app = create_app(config)
    client = TestClient(app)

    try:
        # Exercise various endpoints with secret and invalid tokens
        client.get("/healthz")
        client.get("/api/v1/auth-check", headers={"Authorization": f"Bearer {secret_token}"})
        client.get("/api/v1/auth-check", headers={"Authorization": f"Bearer {bad_token}"})
        client.get(f"/api/v1/healthz?token={secret_token}")

        # WebSocket failed interaction with bad token
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/api/v1/ingest?token={bad_token}"):
                pass

        # WebSocket successful interaction with valid token
        with client.websocket_connect(
            "/api/v1/ingest", headers={"Authorization": f"Bearer {secret_token}"}
        ) as ws:
            ws.send_json(make_valid_hello(client_id="test-device-logscan"))
            ws.receive_json()

        logs_emitted = log_capture.getvalue()
        # Assert secret token and attacker token are never present in log records
        assert secret_token not in logs_emitted, (
            f"Security breach: Token {secret_token} leaked into log records!"
        )
        assert bad_token not in logs_emitted, (
            f"Security breach: Bad token {bad_token} leaked into log records!"
        )
    finally:
        streaming_logger.removeHandler(handler)

"""Security tests for pairing, tickets and limits (T18-013).

Abuse cases automated:
1. Guessing pairing codes triggers brute-force lockout (429).
2. Reusing pairing codes or tickets is strictly rejected (single-use semantics).
3. Cross-session token use: token for Session A cannot write or ingest to Session B.
4. Flooding session creation from a single IP triggers 429 rate limit.
5. Oversize WebSocket frames exceeding MAX_MESSAGE_BYTES close with code 1009.
6. Requests with disallowed or spoofed Origin headers are refused with 403 / 4403.
7. Log-scan asserting pairing codes, tokens, tickets, and sensitive query strings
   never leak into server logs.
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


def _make_valid_hello(
    client_id: str = "device-sec-test",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Construct schema-valid IngestHello message (Contract C7)."""
    msg: dict[str, Any] = {
        "type": "hello",
        "schema_version": SCHEMA_VERSION,
        "client_id": client_id,
        "session_label": "security-abuse-test",
        "device": "Pixel 7 Pro",
        "manufacturer": "Google",
        "android": "14",
        "operator": "Jio",
        "app_version": "2.0.0",
        "resume_from_seq": 0,
        "queue_depth": 0,
        "dropped_from_queue": 0,
    }
    if session_id:
        msg["session_id"] = session_id
    return msg


def test_guessing_pairing_codes_triggers_lockout() -> None:
    """Guessing invalid pairing codes repeatedly locks out the IP with 429."""
    cfg = ServerConfig(pairing_lockout_attempts=3, pairing_lockout_seconds=10)
    app = create_app(cfg)
    client = TestClient(app, client=("198.51.100.12", 40001))

    # Attempts 1 and 2 fail with 404
    for _ in range(2):
        res = client.post(
            "/api/v1/pair",
            json={"pairing_code": "WRONG123", "client_id": "phone-1", "device": "Pixel 7"},
        )
        assert res.status_code == 404

    # Attempt 3 reaches the lockout threshold -> 429
    res3 = client.post(
        "/api/v1/pair",
        json={"pairing_code": "WRONG123", "client_id": "phone-1", "device": "Pixel 7"},
    )
    assert res3.status_code == 429
    assert "Locked out" in res3.json()["error"]["message"]

    # Subsequent attempt is also immediately blocked with 429
    res4 = client.post(
        "/api/v1/pair",
        json={"pairing_code": "WRONG123", "client_id": "phone-1", "device": "Pixel 7"},
    )
    assert res4.status_code == 429
    assert "Locked out" in res4.json()["error"]["message"]


def test_reusing_pairing_code_and_ticket_rejected() -> None:
    """Pairing codes and viewer tickets are strictly single-use."""
    cfg = ServerConfig(require_live_auth=True, allow_remote_view=True)
    app = create_app(cfg)
    client = TestClient(app)

    # 1. Create session and obtain pairing code
    create_res = client.post("/api/v1/live-sessions")
    assert create_res.status_code == 200
    code = create_res.json()["pairing_code"]
    session_id = create_res.json()["session_id"]

    # 2. Pair device first time -> 200 OK
    pair_res1 = client.post(
        "/api/v1/pair",
        json={"pairing_code": code, "client_id": "phone-alpha", "device": "Pixel 7"},
    )
    assert pair_res1.status_code == 200

    # 3. Attempt to reuse the same pairing code -> 409 Conflict
    pair_res2 = client.post(
        "/api/v1/pair",
        json={"pairing_code": code, "client_id": "phone-alpha", "device": "Pixel 7"},
    )
    assert pair_res2.status_code == 409
    assert "already used" in pair_res2.json()["error"]["message"]

    # 4. Generate a viewer ticket for the session
    ticket_res = client.post(f"/api/v1/live-sessions/{session_id}/ticket")
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["ticket"]

    # 5. Connect to /api/v1/live using ticket first time -> succeeds
    with client.websocket_connect("/api/v1/live") as ws:
        ws.send_text(json.dumps({"type": "auth", "ticket": ticket}))
        init_frame = ws.receive_json()
        assert init_frame["type"] == "snapshot"

    # 6. Attempt to reuse the same ticket -> rejected with code 4401
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/live") as ws:
            ws.send_text(json.dumps({"type": "auth", "ticket": ticket}))
            ws.receive_json()
    assert exc_info.value.code == 4401


def test_cross_session_token_use_rejected() -> None:
    """Ingest token issued for Session A cannot write or claim Session B."""
    cfg = ServerConfig(ingest_token="global-token")
    app = create_app(cfg)
    client = TestClient(app)

    # Create Session A and Session B
    res_a = client.post("/api/v1/live-sessions")
    code_a = res_a.json()["pairing_code"]

    res_b = client.post("/api/v1/live-sessions")
    session_b = res_b.json()["session_id"]
    code_b = res_b.json()["pairing_code"]

    # Pair both to acquire session tokens
    pair_a = client.post(
        "/api/v1/pair",
        json={"pairing_code": code_a, "client_id": "phone-a", "device": "Pixel 7"},
    )
    token_a = pair_a.json()["ingest_token"]

    pair_b = client.post(
        "/api/v1/pair",
        json={"pairing_code": code_b, "client_id": "phone-b", "device": "Pixel 7"},
    )
    token_b = pair_b.json()["ingest_token"]
    assert token_a != token_b

    # Attempt to ingest with token A while asserting session_b in hello -> 4401
    with client.websocket_connect(
        "/api/v1/ingest", headers={"Authorization": f"Bearer {token_a}"}
    ) as ws:
        ws.send_json(_make_valid_hello(client_id="phone-a", session_id=session_b))
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "UNAUTHORIZED"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
        assert exc.value.code == 4401


def test_flooding_session_creation_rate_limited() -> None:
    """Exceeding max session creations per IP window triggers 429."""
    cfg = ServerConfig(
        max_session_creations_per_ip=2,
        session_creation_window_seconds=60,
    )
    app = create_app(cfg)
    client = TestClient(app, client=("198.51.100.99", 50000))

    # 1st and 2nd creations succeed
    r1 = client.post("/api/v1/live-sessions")
    assert r1.status_code == 200
    r2 = client.post("/api/v1/live-sessions")
    assert r2.status_code == 200

    # 3rd creation from same IP triggers 429
    r3 = client.post("/api/v1/live-sessions")
    assert r3.status_code == 429
    assert "Session creation rate limit exceeded" in r3.json()["error"]["message"]


def test_oversize_websocket_frame_rejected_with_1009() -> None:
    """Sending a frame exceeding MAX_MESSAGE_BYTES is closed with code 1009."""
    app = create_app(ServerConfig())
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ingest") as ws:
            ws.send_json(_make_valid_hello(client_id="phone-oversize"))
            ws.receive_json()
            oversize_text = "X" * (MAX_MESSAGE_BYTES + 1024)
            ws.send_text(oversize_text)
            ws.receive_text()
    assert exc_info.value.code == 1009


def test_wrong_origin_refusal() -> None:
    """Disallowed or malicious Origin headers are rejected across REST and WS."""
    cfg = ServerConfig(
        allowed_origins=["https://dashboard.example.com"],
        allow_remote_view=True,
    )
    app = create_app(cfg)
    client = TestClient(app)

    # 1. REST request with wrong origin -> 403 Forbidden
    res = client.get("/healthz", headers={"Origin": "https://malicious.attacker.com"})
    assert res.status_code == 403

    # 2. WebSocket live connection with wrong origin -> code 4403
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/v1/live",
            headers={"Origin": "https://malicious.attacker.com"},
        ):
            pass
    assert exc_info.value.code == 4403

    # 3. WebSocket ingest connection with wrong origin -> code 4403
    with pytest.raises(WebSocketDisconnect) as exc_info_ingest:
        with client.websocket_connect(
            "/api/v1/ingest",
            headers={"Origin": "https://malicious.attacker.com"},
        ):
            pass
    assert exc_info_ingest.value.code == 4403


def test_sensitive_credentials_absent_from_logs() -> None:
    """Log-scan verifies pairing codes, tokens, tickets, and query strings are never logged."""
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    streaming_logger = logging.getLogger("streaming")
    streaming_logger.addHandler(handler)
    streaming_logger.setLevel(logging.DEBUG)

    cfg = ServerConfig(require_live_auth=True, allow_remote_view=True)
    app = create_app(cfg)
    client = TestClient(app)

    try:
        # Create session
        res = client.post("/api/v1/live-sessions")
        data = res.json()
        session_id = data["session_id"]
        pairing_code = data["pairing_code"]

        # Pair device
        pair_res = client.post(
            "/api/v1/pair",
            json={"pairing_code": pairing_code, "client_id": "phone-log", "device": "Pixel 7"},
        )
        ingest_token = pair_res.json()["ingest_token"]

        # Generate ticket
        ticket_res = client.post(f"/api/v1/live-sessions/{session_id}/ticket")
        ticket = ticket_res.json()["ticket"]

        # WebSocket ingest
        with client.websocket_connect(
            f"/api/v1/ingest?token={ingest_token}",
        ) as ws:
            ws.send_json(_make_valid_hello(client_id="phone-log", session_id=session_id))
            ws.receive_json()

        # WebSocket live
        with client.websocket_connect("/api/v1/live") as ws_live:
            ws_live.send_text(json.dumps({"type": "auth", "ticket": ticket}))
            ws_live.receive_json()

        logs = log_stream.getvalue()

        # Verify no credentials leaked in any logs
        assert pairing_code not in logs, f"Pairing code '{pairing_code}' was found in logs!"
        assert ingest_token not in logs, f"Ingest token '{ingest_token}' was found in logs!"
        assert ticket not in logs, f"Viewer ticket '{ticket}' was found in logs!"
    finally:
        streaming_logger.removeHandler(handler)

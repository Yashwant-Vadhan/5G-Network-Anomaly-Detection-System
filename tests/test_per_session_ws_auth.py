"""Tests for per-session WebSocket authentication (T18-003, Contract C8, C10).

Acceptance Criteria:
- Token for session A cannot write to session B
- Late or reused ticket rejected
- Live endpoint requires first-frame auth ticket within 5 s
- Wrong or missing auth closes with code 4401
- No secret tokens or tickets in server logs (G20, G26)
"""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from streaming.server import ServerConfig, create_app


def make_hello(
    client_id: str = "phone-client-1",
    device: str = "Pixel 7 Pro",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Construct schema-valid IngestHello message (Contract C7)."""
    msg: dict[str, Any] = {
        "type": "hello",
        "schema_version": 2,
        "client_id": client_id,
        "session_label": "test-walk",
        "device": device,
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


def make_sample(
    seq: int = 1,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Construct schema-valid IngestSample message (Contract C7)."""
    raw_sample = {
        "timestamp": "17-10-26 15:30:00",
        "device": "Pixel 7 Pro",
        "manufacturer": "Google",
        "android": "14",
        "operator": "Jio",
        "network_type": "NR",
        "deployment_mode": "SA",
        "registered": True,
        "ss_rsrp": -92.0,
        "ss_rsrq": -11.0,
        "ss_sinr": 18.0,
        "pci": 420,
        "nci": 13322280247,
        "nrarfcn": 632000,
    }
    if session_id:
        raw_sample["session_id"] = session_id
    msg: dict[str, Any] = {
        "type": "sample",
        "schema_version": 2,
        "seq": seq,
        "sent_at": "2026-10-17T10:00:00.000+00:00",
        "payload": raw_sample,
    }
    if session_id:
        msg["session_id"] = session_id
    return msg


def test_token_session_a_cannot_write_session_b_on_hello() -> None:
    """T18-003: Bearer token scoped to session A cannot write to session B on hello."""
    app = create_app(ServerConfig(ingest_token="global-secret", allow_remote_view=True))
    client = TestClient(app)

    # 1. Create Session A and Session B
    res_a = client.post("/api/v1/live-sessions").json()
    res_b = client.post("/api/v1/live-sessions").json()

    # 2. Pair Session A
    pair_a = client.post(
        "/api/v1/pair",
        json={"pairing_code": res_a["pairing_code"], "client_id": "phone-A"},
    ).json()
    token_a = pair_a["ingest_token"]
    session_b_id = res_b["session_id"]

    # 3. Connect using token A, but attempt to write to Session B
    with client.websocket_connect(
        "/api/v1/ingest",
        headers={"Authorization": f"Bearer {token_a}"},
    ) as ws:
        ws.send_text(json.dumps(make_hello(session_id=session_b_id)))
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "UNAUTHORIZED"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
        assert exc.value.code == 4401


def test_token_session_a_cannot_write_session_b_on_sample() -> None:
    """T18-003: Bearer token scoped to session A cannot write to session B on sample."""
    app = create_app(ServerConfig(ingest_token="global-secret", allow_remote_view=True))
    client = TestClient(app)

    # 1. Create Session A and Session B
    res_a = client.post("/api/v1/live-sessions").json()
    res_b = client.post("/api/v1/live-sessions").json()

    pair_a = client.post(
        "/api/v1/pair",
        json={"pairing_code": res_a["pairing_code"], "client_id": "phone-A"},
    ).json()
    token_a = pair_a["ingest_token"]
    session_b_id = res_b["session_id"]

    # 2. Connect with token A, send valid hello
    with client.websocket_connect(
        "/api/v1/ingest",
        headers={"Authorization": f"Bearer {token_a}"},
    ) as ws:
        ws.send_text(json.dumps(make_hello()))
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"

        # 3. Send sample targeting Session B
        ws.send_text(json.dumps(make_sample(seq=1, session_id=session_b_id)))
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "UNAUTHORIZED"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
        assert exc.value.code == 4401


def test_live_ws_first_frame_auth_success() -> None:
    """T18-003: WS /api/v1/live successfully authenticates with single-use first frame ticket."""
    config = ServerConfig(require_live_auth=True, allow_remote_view=True)
    app = create_app(config)
    client = TestClient(app)

    # 1. Create session and ticket
    sess = client.post("/api/v1/live-sessions").json()
    sess_id = sess["session_id"]
    ticket_data = client.post(f"/api/v1/live-sessions/{sess_id}/ticket").json()
    ticket = ticket_data["ticket"]

    # 2. Connect to WS /api/v1/live and send first frame auth
    with client.websocket_connect("/api/v1/live") as ws:
        auth_frame = {"type": "auth", "ticket": ticket}
        ws.send_text(json.dumps(auth_frame))

        # First received message must be SnapshotEvent for this session
        snap = ws.receive_json()
        assert snap["type"] == "snapshot"
        assert snap["session_id"] == sess_id


def test_live_ws_reused_ticket_rejected() -> None:
    """T18-003: Reused ticket rejected with code 4401 (single-use guarantee)."""
    config = ServerConfig(require_live_auth=True, allow_remote_view=True)
    app = create_app(config)
    client = TestClient(app)

    sess = client.post("/api/v1/live-sessions").json()
    ticket = client.post(f"/api/v1/live-sessions/{sess['session_id']}/ticket").json()["ticket"]

    # 1. First connection succeeds and consumes ticket
    with client.websocket_connect("/api/v1/live") as ws:
        ws.send_text(json.dumps({"type": "auth", "ticket": ticket}))
        assert ws.receive_json()["type"] == "snapshot"

    # 2. Reusing same ticket is rejected
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/live") as ws:
            ws.send_text(json.dumps({"type": "auth", "ticket": ticket}))
            ws.receive_json()

    assert exc.value.code == 4401


def test_live_ws_late_ticket_rejected() -> None:
    """T18-003: Expired (late) ticket rejected with code 4401."""
    config = ServerConfig(require_live_auth=True, allow_remote_view=True)
    app = create_app(config)
    client = TestClient(app)

    sess = client.post("/api/v1/live-sessions").json()
    ticket = client.post(f"/api/v1/live-sessions/{sess['session_id']}/ticket").json()["ticket"]

    # Expire ticket in app state
    sess_id, _ = app.state.live_session_tickets[ticket]
    app.state.live_session_tickets[ticket] = (sess_id, datetime.now(UTC) - timedelta(seconds=5))

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/live") as ws:
            ws.send_text(json.dumps({"type": "auth", "ticket": ticket}))
            ws.receive_json()

    assert exc.value.code == 4401


def test_live_ws_wrong_or_missing_auth_frame() -> None:
    """T18-003: Non-auth first frame rejected with code 4401."""
    config = ServerConfig(require_live_auth=True, allow_remote_view=True)
    app = create_app(config)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/live") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            ws.receive_json()

    assert exc.value.code == 4401


def test_no_token_in_logs() -> None:
    """T18-003, G20, G26: Tokens and tickets never leak into server logs."""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger = logging.getLogger("streaming")
    old_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    try:
        config = ServerConfig(
            ingest_token="super-secret-token-xyz",
            require_live_auth=True,
            allow_remote_view=True,
        )
        app = create_app(config)
        client = TestClient(app)

        sess = client.post("/api/v1/live-sessions").json()
        pair_res = client.post(
            "/api/v1/pair",
            json={"pairing_code": sess["pairing_code"], "client_id": "test-phone"},
        ).json()
        ingest_token = pair_res["ingest_token"]

        ticket_res = client.post(f"/api/v1/live-sessions/{sess['session_id']}/ticket").json()
        ticket = ticket_res["ticket"]

        with client.websocket_connect("/api/v1/live") as ws:
            ws.send_text(json.dumps({"type": "auth", "ticket": ticket}))
            ws.receive_json()

        logs = log_capture.getvalue()
        assert ingest_token not in logs, "Ingest token leaked in server logs!"
        assert ticket not in logs, "Viewer ticket leaked in server logs!"
        assert "super-secret-token-xyz" not in logs, "Global ingest token leaked in logs!"
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)

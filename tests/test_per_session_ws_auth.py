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


def test_end_to_end_paired_collector_telemetry_visible_on_dashboard() -> None:
    """T18-003 / Task 7: End-to-end regression test.

    Proves that telemetry sent by a paired Android collector (with collector dd-MM-yy
    timestamp and potential session gaps) becomes visible to the dashboard on /api/v1/live
    for the correct active session.
    """
    config = ServerConfig(
        require_live_auth=True,
        allow_remote_view=True,
        mode="public",
        allowed_origins=["http://testserver"],
        retention_enabled=False,
    )
    app = create_app(config)
    client = TestClient(app)

    # 1. Dashboard initiates live session and receives HttpOnly viewer cookie
    create_res = client.post("/api/v1/live-sessions")
    assert create_res.status_code == 200
    sess_data = create_res.json()
    session_id = sess_data["session_id"]
    pairing_code = sess_data["pairing_code"]

    # 2. Android collector pairs using the 8-character code
    pair_res = client.post(
        "/api/v1/pair",
        json={"pairing_code": pairing_code, "client_id": "android-redmi-123"},
    )
    assert pair_res.status_code == 200
    pair_data = pair_res.json()
    assert pair_data["session_id"] == session_id
    ingest_token = pair_data["ingest_token"]

    # 3. Dashboard requests single-use viewer ticket using viewer cookie
    ticket_res = client.post(f"/api/v1/live-sessions/{session_id}/ticket")
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["ticket"]

    # 4. Dashboard connects to /api/v1/live and authenticates with ticket in first frame
    with client.websocket_connect("/api/v1/live", headers={"Origin": "http://testserver"}) as viewer_ws:
        viewer_ws.send_text(json.dumps({"type": "auth", "ticket": ticket}))
        initial_snap = viewer_ws.receive_json()
        assert initial_snap["type"] == "snapshot"
        assert initial_snap["session_id"] == session_id

        # 5. Android collector connects to /api/v1/ingest with session token
        with client.websocket_connect(
            "/api/v1/ingest",
            headers={"Authorization": f"Bearer {ingest_token}"},
        ) as ingest_ws:
            # Collector sends hello
            ingest_ws.send_text(
                json.dumps(
                    make_hello(
                        client_id="android-redmi-123",
                        device="Redmi Note 12 5G",
                        session_id=session_id,
                    )
                )
            )
            hello_ack = ingest_ws.receive_json()
            assert hello_ack["type"] == "hello_ack"
            assert hello_ack["session_id"] == session_id

            # Viewer receives connection event transition to LIVE
            conn_ev = viewer_ws.receive_json()
            assert conn_ev["type"] == "connection"
            assert conn_ev["session_id"] == session_id
            assert conn_ev["state"] == "LIVE"

            # Collector sends sample 1 using collector timestamp format ('dd-MM-yy HH:mm:ss')
            sample_1 = {
                "type": "sample",
                "schema_version": 2,
                "seq": 1,
                "sent_at": "2026-10-22T10:15:00.123+05:30",
                "payload": {
                    "timestamp": "22-10-26 10:15:00",
                    "device": "Redmi Note 12 5G",
                    "manufacturer": "Xiaomi",
                    "android": "14",
                    "operator": "Jio 5G",
                    "network_type": "5G NR",
                    "deployment_mode": "SA",
                    "display_override": "NONE",
                    "registered": True,
                    "ss_rsrp": -88.5,
                    "ss_rsrq": -10.0,
                    "ss_sinr": 21.0,
                    "csi_rsrp": -89.0,
                    "csi_rsrq": -10.5,
                    "csi_sinr": 20.0,
                    "pci": 312,
                    "nci": 13322280247,
                    "nrarfcn": 632000,
                },
            }
            ingest_ws.send_text(json.dumps(sample_1))

            # Dashboard receives LiveSampleEvent for active session (and optional connection state event)
            msgs_received = []
            while len([m for m in msgs_received if m.get("type") == "sample"]) < 1:
                msgs_received.append(viewer_ws.receive_json())

            sample_evs = [m for m in msgs_received if m.get("type") == "sample"]
            live_ev_1 = sample_evs[0]
            assert live_ev_1["session_id"] == session_id
            assert live_ev_1["sample"]["session_id"] == session_id
            assert live_ev_1["sample"]["seq"] == 1
            assert live_ev_1["sample"]["ss_rsrp"] == -88.5
            assert live_ev_1["sample"]["device"] == "Redmi Note 12 5G"

            # Collector sends sample 2 after 120s gap (simulating the reported gap scenario)
            sample_2 = {
                "type": "sample",
                "schema_version": 2,
                "seq": 2,
                "sent_at": "2026-10-22T10:17:00.456+05:30",
                "payload": {
                    "timestamp": "22-10-26 10:17:00",
                    "device": "Redmi Note 12 5G",
                    "manufacturer": "Xiaomi",
                    "android": "14",
                    "operator": "Jio 5G",
                    "network_type": "5G NR",
                    "deployment_mode": "SA",
                    "display_override": "NONE",
                    "registered": True,
                    "ss_rsrp": -91.0,
                    "ss_rsrq": -11.5,
                    "ss_sinr": 18.0,
                    "csi_rsrp": -92.0,
                    "csi_rsrq": -12.0,
                    "csi_sinr": 17.5,
                    "pci": 312,
                    "nci": 13322280247,
                    "nrarfcn": 632000,
                },
            }
            ingest_ws.send_text(json.dumps(sample_2))

            # Dashboard receives sample 2 for the SAME active session ID without drops
            while len([m for m in msgs_received if m.get("type") == "sample"]) < 2:
                msgs_received.append(viewer_ws.receive_json())

            sample_evs = [m for m in msgs_received if m.get("type") == "sample"]
            live_ev_2 = sample_evs[1]
            assert live_ev_2["session_id"] == session_id
            assert live_ev_2["sample"]["session_id"] == session_id
            assert live_ev_2["sample"]["seq"] == 2
            assert live_ev_2["sample"]["ss_rsrp"] == -91.0

    # 6. Verify ephemeral C1 CSV export contains both captured samples
    csv_res = client.get(f"/api/v1/live-sessions/{session_id}/export.csv")
    assert csv_res.status_code == 200
    csv_lines = csv_res.text.strip().splitlines()
    assert len(csv_lines) == 3  # header + 2 samples
    assert "Redmi Note 12 5G" in csv_lines[1]
    assert "Redmi Note 12 5G" in csv_lines[2]


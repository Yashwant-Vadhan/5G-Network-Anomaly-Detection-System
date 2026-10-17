"""Tests for hosted pairing and ephemeral session lifecycle API (Contract C10 / T18-002).

Acceptance Criteria:
- Code cannot be reused (409 Conflict)
- Expired code rejected (400 Bad Request)
- Golden C10 examples committed and valid
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from ml.config import PAIRING_CODE_ALPHABET, PAIRING_CODE_LENGTH
from streaming.schema import (
    CreateLiveSessionResponse,
    DeleteLiveSessionResponse,
    LiveSessionTicketResponse,
    PairRequest,
    PairResponse,
)
from streaming.server import ServerConfig, create_app


def test_c10_golden_examples_exist_and_validate() -> None:
    """Verify that committed golden C10 JSON examples and schemas are valid."""
    fixtures_dir = Path("tests/fixtures/stream")
    c10_models = [
        ("c10_create_live_session_response", CreateLiveSessionResponse),
        ("c10_pair_request", PairRequest),
        ("c10_pair_response", PairResponse),
        ("c10_live_session_ticket_response", LiveSessionTicketResponse),
        ("c10_delete_live_session_response", DeleteLiveSessionResponse),
    ]

    for name, model_cls in c10_models:
        schema_file = fixtures_dir / f"{name}.schema.json"
        example_file = fixtures_dir / f"{name}.example.json"

        assert schema_file.exists(), f"Missing schema file: {schema_file}"
        assert example_file.exists(), f"Missing example file: {example_file}"

        data = json.loads(example_file.read_text(encoding="utf-8"))
        instance = model_cls.model_validate(data)
        assert instance is not None


def test_create_live_session_and_cookie() -> None:
    """POST /api/v1/live-sessions returns 8-char unambiguous code and sets viewer cookie."""
    app = create_app(ServerConfig(ingest_token="test-ingest-token", allow_remote_view=True))
    client = TestClient(app)

    res = client.post("/api/v1/live-sessions")
    assert res.status_code == 200, res.text
    data = res.json()

    assert "session_id" in data
    assert "pairing_code" in data
    assert "expires_at" in data

    code = data["pairing_code"]
    assert len(code) == PAIRING_CODE_LENGTH
    assert all(c in PAIRING_CODE_ALPHABET for c in code)

    # Check HttpOnly cookie
    assert "nads_viewer_session" in res.cookies
    assert res.cookies["nads_viewer_session"] == data["session_id"]


def test_pairing_flow_and_single_use() -> None:
    """Verify pairing device issues ingest token and cannot be reused (409 Conflict)."""
    app = create_app(ServerConfig(ingest_token="test-ingest-token", allow_remote_view=True))
    client = TestClient(app)

    create_res = client.post("/api/v1/live-sessions")
    session_data = create_res.json()
    code = session_data["pairing_code"]
    session_id = session_data["session_id"]

    # Pair device
    pair_payload = {
        "pairing_code": code,
        "client_id": "phone-client-1234",
        "app_version": "2.0.0",
        "schema_version": 2,
    }
    pair_res = client.post("/api/v1/pair", json=pair_payload)
    assert pair_res.status_code == 200, pair_res.text
    pair_data = pair_res.json()
    assert pair_data["session_id"] == session_id
    assert "ingest_token" in pair_data
    assert pair_data["ws_url"] == "/api/v1/ingest"

    # Reusing the pairing code must be rejected (409 Conflict)
    dup_res = client.post("/api/v1/pair", json=pair_payload)
    assert dup_res.status_code == 409
    dup_err = dup_res.json().get("error", {}).get("message", "")
    assert "already used" in dup_err.lower()


def test_expired_pairing_code_rejected() -> None:
    """Pairing with an expired code returns 400 Bad Request."""
    app = create_app(ServerConfig(ingest_token="test-ingest-token", allow_remote_view=True))
    client = TestClient(app)

    create_res = client.post("/api/v1/live-sessions")
    code = create_res.json()["pairing_code"]

    # Manually expire code in app state
    app.state.pairing_sessions[code]["expires_at"] = datetime.now(UTC) - timedelta(seconds=10)

    pair_payload = {
        "pairing_code": code,
        "client_id": "phone-client-1234",
        "app_version": "2.0.0",
        "schema_version": 2,
    }
    res = client.post("/api/v1/pair", json=pair_payload)
    assert res.status_code == 400
    exp_err = res.json().get("error", {}).get("message", "")
    assert "expired" in exp_err.lower()


def test_invalid_pairing_code_rejected() -> None:
    """Non-existent pairing code returns 404 Not Found."""
    app = create_app(ServerConfig(ingest_token="test-ingest-token", allow_remote_view=True))
    client = TestClient(app)

    pair_payload = {
        "pairing_code": "NONEXIST",
        "client_id": "phone-client-1234",
        "app_version": "2.0.0",
        "schema_version": 2,
    }
    res = client.post("/api/v1/pair", json=pair_payload)
    assert res.status_code == 404


def test_websocket_ingest_with_per_session_token() -> None:
    """WebSocket ingest accepts connection authenticated with per-session ingest token."""
    app = create_app(ServerConfig(ingest_token="global-secret", allow_remote_view=True))
    client = TestClient(app)

    # Create & pair
    create_res = client.post("/api/v1/live-sessions")
    code = create_res.json()["pairing_code"]
    pair_res = client.post(
        "/api/v1/pair",
        json={"pairing_code": code, "client_id": "test-phone", "app_version": "2.0.0"},
    )
    ingest_token = pair_res.json()["ingest_token"]

    # Connect WebSocket using per-session bearer token
    with client.websocket_connect(
        "/api/v1/ingest",
        headers={"Authorization": f"Bearer {ingest_token}"},
    ) as ws:
        hello_msg = {
            "type": "hello",
            "schema_version": 2,
            "client_id": "test-phone",
            "session_label": "paired-session",
            "device": "Pixel 7 Pro",
            "manufacturer": "Google",
            "android": "14",
            "operator": "Jio",
            "app_version": "2.0.0",
            "resume_from_seq": 0,
            "queue_depth": 0,
            "dropped_from_queue": 0,
        }
        ws.send_text(json.dumps(hello_msg))
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"


def test_ticket_and_delete_live_session() -> None:
    """Generate live WebSocket viewer ticket and teardown session with memory purge (G29)."""
    app = create_app(ServerConfig(ingest_token="global-secret", allow_remote_view=True))
    client = TestClient(app)

    # 1. Create session (sets viewer cookie on client)
    create_res = client.post("/api/v1/live-sessions")
    session_id = create_res.json()["session_id"]
    code = create_res.json()["pairing_code"]

    # Pair to create ingest token
    pair_res = client.post(
        "/api/v1/pair",
        json={"pairing_code": code, "client_id": "test-client", "app_version": "2.0.0"},
    )
    ingest_token = pair_res.json()["ingest_token"]

    # 2. Unauthorized ticket request (another client without cookie or bearer header)
    unauth_client = TestClient(app)
    unauth_res = unauth_client.post(f"/api/v1/live-sessions/{session_id}/ticket")
    assert unauth_res.status_code == 401

    # 3. Authorized ticket request using viewer cookie from creation
    ticket_res = client.post(f"/api/v1/live-sessions/{session_id}/ticket")
    assert ticket_res.status_code == 200
    ticket_data = ticket_res.json()
    assert "ticket" in ticket_data
    assert "expires_at" in ticket_data
    ticket = ticket_data["ticket"]
    assert ticket in app.state.live_session_tickets

    # 4. Teardown session
    del_res = client.delete(f"/api/v1/live-sessions/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # In-memory session data must be purged (G29)
    assert session_id not in app.state.active_live_sessions
    assert code not in app.state.pairing_sessions
    assert ingest_token not in app.state.session_ingest_tokens
    assert ticket not in app.state.live_session_tickets
    assert session_id not in app.state.session_samples
    assert session_id not in app.state.session_events

    # Subsequent ticket request returns 404
    after_res = client.post(
        f"/api/v1/live-sessions/{session_id}/ticket",
        headers={"Authorization": f"Bearer {session_id}"},
    )
    assert after_res.status_code == 404

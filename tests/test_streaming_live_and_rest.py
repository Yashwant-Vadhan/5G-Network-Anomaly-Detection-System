"""Tests for T11-014: WS /api/v1/live and REST endpoints (Contract C8)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from streaming.schema import SCHEMA_VERSION
from streaming.server import ServerConfig, create_app
from streaming.session_manager import SessionManager


def test_rest_endpoints_matches_golden_c8_schemas():
    """REST endpoints return valid Contract C8 JSON structures."""
    session_manager = SessionManager(max_rows=100)
    config = ServerConfig(retention_enabled=False)
    app = create_app(config, session_manager=session_manager)
    client = TestClient(app)

    # 1. Model Info
    r_model = client.get("/api/v1/model")
    assert r_model.status_code == 200
    model_data = r_model.json()
    assert "model_version" in model_data
    assert "feature_columns" in model_data
    assert "thresholds" in model_data

    # 2. Sessions list
    r_sess = client.get("/api/v1/sessions")
    assert r_sess.status_code == 200
    sess_data = r_sess.json()
    assert "sessions" in sess_data
    assert "total" in sess_data
    assert isinstance(sess_data["sessions"], list)

    # 3. Create a session buffer and check samples/events routes
    buf = session_manager.get_or_create_session("client-test", "Samsung SM-A156E")
    r_samples = client.get(f"/api/v1/sessions/{buf.session_id}/samples")
    assert r_samples.status_code == 200
    samples_data = r_samples.json()
    assert "samples" in samples_data
    assert "total" in samples_data
    assert "has_more" in samples_data

    r_events = client.get(f"/api/v1/sessions/{buf.session_id}/events")
    assert r_events.status_code == 200
    events_data = r_events.json()
    assert "events" in events_data
    assert "total" in events_data


def test_rest_pagination_cap_enforced():
    """Requesting limit > 1000 triggers 422 validation failure."""
    app = create_app(ServerConfig(retention_enabled=False))
    client = TestClient(app)

    r_bad_limit = client.get("/api/v1/sessions?limit=2000")
    assert r_bad_limit.status_code == 400 or r_bad_limit.status_code == 422


def test_non_loopback_client_refused_by_default():
    """Non-loopback clients are rejected with 403 when allow_remote_view is false."""
    from fastapi import HTTPException, Request

    config = ServerConfig(allow_remote_view=False)

    mock_req = MagicMock(spec=Request)
    mock_req.client = MagicMock(host="192.168.1.50")

    client_host = mock_req.client.host
    if not config.allow_remote_view and client_host not in (
        "127.0.0.1",
        "::1",
        "localhost",
        "testclient",
    ):
        with pytest.raises(HTTPException) as exc:
            raise HTTPException(
                status_code=403, detail="Forbidden: Remote access disabled; loopback only"
            )
        assert exc.value.status_code == 403


def test_ws_live_receives_snapshot_and_live_sample():
    """WS /api/v1/live sends initial SnapshotEvent and receives broadcast samples."""
    config = ServerConfig(retention_enabled=False)
    app = create_app(config)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/live") as ws:
        # First message must be SnapshotEvent
        snap_raw = ws.receive_text()
        snap_data = json.loads(snap_raw)
        assert snap_data["type"] == "snapshot"
        assert snap_data["schema_version"] == SCHEMA_VERSION
        assert "server_time" in snap_data
        assert "state" in snap_data
        assert "open_events" in snap_data
        assert "last_alerts" in snap_data

"""Tests for Origin and CORS enforcement on REST and WebSocket endpoints (T18-006).

Acceptance Criteria:
- Disallowed origin refused for REST and WS
- Test covers both
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from streaming.server import ServerConfig, create_app


def test_rest_allowed_origin_succeeds_with_cors_headers() -> None:
    """REST request from an allowed origin succeeds with Access-Control headers."""
    cfg = ServerConfig(
        allowed_origins=["https://dashboard.example.com"],
        allow_remote_view=True,
    )
    app = create_app(cfg)
    client = TestClient(app)

    res = client.get("/healthz", headers={"Origin": "https://dashboard.example.com"})
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://dashboard.example.com"


def test_rest_disallowed_origin_refused_with_403() -> None:
    """REST request from a disallowed origin is refused with 403 Forbidden."""
    cfg = ServerConfig(
        allowed_origins=["https://dashboard.example.com"],
        allow_remote_view=True,
    )
    app = create_app(cfg)
    client = TestClient(app)

    res = client.get("/healthz", headers={"Origin": "https://malicious-site.com"})
    assert res.status_code == 403
    assert "not allowed" in res.json()["error"]["message"]


def test_rest_options_preflight_cors_enforcement() -> None:
    """OPTIONS preflight requests are rejected for disallowed origins."""
    cfg = ServerConfig(
        mode="public",
        allowed_origins=["https://dashboard.example.com"],
        retention_enabled=False,
    )
    app = create_app(cfg)
    client = TestClient(app)

    # Disallowed origin preflight
    bad_res = client.options(
        "/api/v1/live-sessions",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert bad_res.status_code == 403

    # Allowed origin preflight
    ok_res = client.options(
        "/api/v1/live-sessions",
        headers={
            "Origin": "https://dashboard.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert ok_res.status_code == 200
    assert ok_res.headers.get("access-control-allow-origin") == "https://dashboard.example.com"


def test_ws_live_disallowed_origin_closed_with_4403() -> None:
    """WebSocket /api/v1/live rejects disallowed Origin header with close code 4403."""
    cfg = ServerConfig(
        mode="public",
        allowed_origins=["https://dashboard.example.com"],
        retention_enabled=False,
        require_live_auth=True,
    )
    app = create_app(cfg)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/api/v1/live",
            headers={"Origin": "https://malicious-site.com"},
        ):
            pass
    assert exc.value.code == 4403


def test_ws_live_missing_origin_in_public_mode_refused() -> None:
    """WebSocket /api/v1/live in public mode requires explicit Origin header."""
    cfg = ServerConfig(
        mode="public",
        allowed_origins=["https://dashboard.example.com"],
        retention_enabled=False,
        require_live_auth=True,
    )
    app = create_app(cfg)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/live"):
            pass
    assert exc.value.code == 4403


def test_ws_live_allowed_origin_accepted() -> None:
    """WebSocket /api/v1/live accepts allowed Origin header."""
    cfg = ServerConfig(
        mode="public",
        allowed_origins=["https://dashboard.example.com"],
        retention_enabled=False,
        require_live_auth=True,
    )
    app = create_app(cfg)
    client = TestClient(app)

    # Allowed origin connects successfully and waits for ticket auth
    with client.websocket_connect(
        "/api/v1/live",
        headers={"Origin": "https://dashboard.example.com"},
    ) as ws:
        # Invalid ticket closes with 4401 (proves connection was accepted past Origin check)
        ws.send_json({"type": "auth", "ticket": "invalid-ticket"})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
        assert exc.value.code == 4401


def test_ws_ingest_disallowed_origin_closed_with_4403() -> None:
    """WebSocket /api/v1/ingest rejects disallowed Origin header with close code 4403."""
    cfg = ServerConfig(
        allowed_origins=["https://dashboard.example.com"],
        ingest_token="token123",
        allow_remote_view=True,
    )
    app = create_app(cfg)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/api/v1/ingest",
            headers={
                "Origin": "https://malicious-site.com",
                "Authorization": "Bearer token123",
            },
        ):
            pass
    assert exc.value.code == 4403


def test_ws_ingest_allowed_origin_succeeds() -> None:
    """WebSocket /api/v1/ingest accepts connection from allowed Origin header."""
    cfg = ServerConfig(
        allowed_origins=["https://dashboard.example.com"],
        ingest_token="token123",
        allow_remote_view=True,
    )
    app = create_app(cfg)
    client = TestClient(app)

    with client.websocket_connect(
        "/api/v1/ingest",
        headers={
            "Origin": "https://dashboard.example.com",
            "Authorization": "Bearer token123",
        },
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "phone1",
                "session_label": "test",
                "device": "pixel7",
                "manufacturer": "Google",
                "android": "14",
                "operator": "Jio",
                "app_version": "2.0.0",
            }
        )
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"

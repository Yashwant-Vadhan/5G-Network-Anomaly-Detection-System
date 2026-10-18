"""Tests for bind and exposure policy (T14-003).

Automates the four security startup and exposure cases:
1. Default loopback: server defaults to 127.0.0.1; non-loopback without --allow-lan is rejected.
2. --allow-lan without token exits 2: non-loopback binding requires non-empty token with fix hint.
3. Read endpoints refuse non-loopback unless opted in: 403 Forbidden unless allow_remote_view.
4. /healthz leaks nothing: public healthcheck needs no token and leaks zero secrets/PII.

Acceptance Criteria:
- All four cases automated
- Error messages tell the fix
"""

from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ml.schema import ConfigError
from streaming.schema import HealthResponse
from streaming.server import ServerConfig, create_app


def test_case_1_default_loopback():
    """Case 1: Server defaults to 127.0.0.1; non-loopback requires --allow-lan with fix hint."""
    # 1. Default config is loopback without requiring token
    default_cfg = ServerConfig()
    assert default_cfg.host == "127.0.0.1"
    assert default_cfg.allow_lan is False
    assert default_cfg.allow_remote_view is False
    default_cfg.validate()

    # 2. Loopback variants (127.0.0.1, localhost, ::1) are valid
    ServerConfig(host="localhost").validate()
    ServerConfig(host="::1").validate()

    # 3. Non-loopback host without allow_lan raises ConfigError with fix instruction
    with pytest.raises(ConfigError) as exc_info:
        ServerConfig(host="0.0.0.0", allow_lan=False).validate()
    err_msg = str(exc_info.value)
    assert "requires --allow-lan" in err_msg
    assert "Fix: pass --allow-lan or bind to 127.0.0.1" in err_msg

    # 4. CLI invocation without allow-lan exits code 2 with fix message
    res = subprocess.run(
        [sys.executable, "-m", "streaming.server", "--host", "192.168.1.10"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 2
    assert "requires --allow-lan" in res.stderr
    assert "Fix:" in res.stderr
    assert "127.0.0.1" in res.stderr


def test_case_2_allow_lan_without_token_exits_2():
    """Case 2: --allow-lan without non-empty ingest token exits code 2 with clear fix hint."""
    # 1. Config validation fails when allow_lan is True but token is None or empty
    with pytest.raises(ConfigError) as exc_info1:
        ServerConfig(host="0.0.0.0", allow_lan=True, ingest_token=None).validate()
    err_msg1 = str(exc_info1.value)
    assert "requires a non-empty NADS_INGEST_TOKEN" in err_msg1
    assert "Fix: set NADS_INGEST_TOKEN=<token> or pass --token=<token>" in err_msg1

    with pytest.raises(ConfigError) as exc_info2:
        ServerConfig(host="0.0.0.0", allow_lan=True, ingest_token="").validate()
    assert "requires a non-empty NADS_INGEST_TOKEN" in str(exc_info2.value)

    # 2. CLI invocation with --allow-lan but without token exits 2 and prints fix
    res = subprocess.run(
        [sys.executable, "-m", "streaming.server", "--host", "0.0.0.0", "--allow-lan"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 2
    assert "requires a non-empty NADS_INGEST_TOKEN" in res.stderr
    assert "Fix: set NADS_INGEST_TOKEN=<token> or pass --token=<token>" in res.stderr

    # 3. Passing valid token and allow-lan succeeds
    valid_cfg = ServerConfig(host="0.0.0.0", allow_lan=True, ingest_token="sec-token-123")
    valid_cfg.validate()


def test_case_3_read_endpoints_refuse_non_loopback_unless_opted_in():
    """Case 3: Read endpoints refuse non-loopback clients with 403 unless opted in."""
    # 1. By default, allow_remote_view is False
    config_default = ServerConfig(allow_remote_view=False)
    app_default = create_app(config_default)

    remote_client_ip = "192.168.1.55"
    remote_client = TestClient(app_default, client=(remote_client_ip, 45678))

    read_endpoints = [
        ("GET", "/api/v1/sessions"),
        ("GET", "/api/v1/sessions/sess-test-01/samples"),
        ("GET", "/api/v1/sessions/sess-test-01/events"),
        ("GET", "/api/v1/alerts"),
        ("POST", "/api/v1/alerts/alt-test-01/ack"),
    ]

    for method, path in read_endpoints:
        if method == "GET":
            resp = remote_client.get(path)
        else:
            resp = remote_client.post(path)

        assert resp.status_code == 403, (
            f"Endpoint {path} did not reject non-loopback client {remote_client_ip}"
        )
        body = resp.json()
        assert "Remote access disabled; loopback only" in str(body)

    # WebSocket /api/v1/live also refuses non-loopback client
    with pytest.raises(WebSocketDisconnect) as ws_err:
        with remote_client.websocket_connect("/api/v1/live"):
            pass
    assert ws_err.value.code == 4403

    # Loopback client succeeds
    loopback_client = TestClient(app_default, client=("127.0.0.1", 12345))
    resp_loopback = loopback_client.get("/api/v1/sessions")
    assert resp_loopback.status_code == 200

    # 2. When opted in via allow_remote_view=True, remote client is accepted
    config_opted_in = ServerConfig(allow_remote_view=True)
    app_opted_in = create_app(config_opted_in)
    remote_client_allowed = TestClient(app_opted_in, client=(remote_client_ip, 45678))

    resp_allowed = remote_client_allowed.get("/api/v1/sessions")
    assert resp_allowed.status_code == 200

    with remote_client_allowed.websocket_connect("/api/v1/live") as ws_live:
        msg = ws_live.receive_json()
        assert msg["type"] == "snapshot"


def test_case_4_healthz_leaks_nothing():
    """Case 4: /healthz needs no token, works remotely, and leaks no secret or PII."""
    secret_token = "ultra-secret-ingest-token-999"
    secret_webhook = "https://hooks.slack.com/services/T00/B00/secret_webhook_val"
    secret_email = "smtp.internal-security.local"

    with patch.dict(
        os.environ,
        {
            "NADS_INGEST_TOKEN": secret_token,
            "NADS_ALERT_WEBHOOK_URL": secret_webhook,
            "NADS_ALERT_EMAIL_HOST": secret_email,
        },
    ):
        config = ServerConfig(
            ingest_token=secret_token,
            allow_remote_view=False,
        )
        app = create_app(config)

        # 1. Accessible by remote client without token or loopback permission
        remote_client = TestClient(app, client=("192.168.1.200", 33333))
        resp = remote_client.get("/healthz")
        assert resp.status_code == 200

        data = resp.json()
        # Conforms strictly to HealthResponse schema
        health = HealthResponse.model_validate(data)
        assert health.status == "ok"
        assert health.version == "2.0.0"
        assert isinstance(health.uptime_s, float) and health.uptime_s >= 0.0

        # Exact key set: status, version, uptime_s only
        assert set(data.keys()) == {"status", "version", "uptime_s"}

        # 2. Verify absolute absence of secret strings in body and headers
        resp_text = resp.text
        assert secret_token not in resp_text
        assert secret_webhook not in resp_text
        assert secret_email not in resp_text

        for header_name, header_val in resp.headers.items():
            assert secret_token not in header_val, f"Secret leaked in header {header_name}"
            assert secret_webhook not in header_val
            assert secret_email not in header_val

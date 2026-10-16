"""Unit tests for FastAPI streaming server, auth, and error handling (T11-010)."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from streaming.server import ServerConfig, create_app


def test_healthz_endpoint_public():
    """GET /healthz needs no token and leaks nothing sensitive."""
    config = ServerConfig(ingest_token="secret-token-12345")
    app = create_app(config)
    client = TestClient(app)

    # Calling /healthz without any Authorization header
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"
    assert isinstance(data["uptime_s"], (int, float))
    assert data["uptime_s"] >= 0.0

    # Ensure no tokens or sensitive config are leaked in response body or headers
    assert "secret-token-12345" not in resp.text
    for val in resp.headers.values():
        assert "secret-token-12345" not in val

    # Verify X-Correlation-ID header is present
    assert "X-Correlation-ID" in resp.headers


def test_correlation_id_propagation():
    """X-Correlation-ID is preserved when passed by client or generated if absent."""
    app = create_app()
    client = TestClient(app)

    # 1. Generated when absent
    r1 = client.get("/healthz")
    assert r1.status_code == 200
    corr1 = r1.headers.get("X-Correlation-ID")
    assert corr1 is not None
    assert corr1.startswith("corr-")

    # 2. Preserved when supplied
    custom_corr = "client-trace-abc-123"
    r2 = client.get("/healthz", headers={"X-Correlation-ID": custom_corr})
    assert r2.status_code == 200
    assert r2.headers.get("X-Correlation-ID") == custom_corr


def test_auth_token_enforcement():
    """Protected endpoints reject missing/invalid tokens with 401 and C8 error body."""
    secret = "test-secret-token-abcdef123456"
    config = ServerConfig(ingest_token=secret)
    app = create_app(config)
    client = TestClient(app)

    # 1. Missing token -> 401
    r_missing = client.get("/api/v1/auth-check")
    assert r_missing.status_code == 401
    err_body = r_missing.json()
    assert "error" in err_body
    assert err_body["error"]["code"] == "UNAUTHORIZED"
    assert "correlation_id" in err_body["error"]
    assert secret not in r_missing.text

    # 2. Wrong token -> 401
    r_wrong = client.get(
        "/api/v1/auth-check",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert r_wrong.status_code == 401
    err_body2 = r_wrong.json()
    assert err_body2["error"]["code"] == "UNAUTHORIZED"
    assert secret not in r_wrong.text

    # 3. Correct token -> 200
    r_valid = client.get(
        "/api/v1/auth-check",
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert r_valid.status_code == 200
    assert r_valid.json() == {"status": "authenticated"}


def test_generic_exception_never_leaks_traceback():
    """Internal server errors return status 500 and C8 body without tracebacks."""
    secret = "super-secret-key"
    config = ServerConfig(ingest_token=secret)
    app = create_app(config)

    # Register a route that deliberately raises an unexpected exception
    router = APIRouter()

    @router.get("/api/v1/test-fault")
    def faulty_endpoint():
        # Simulate unexpected internal crash with secret in local variable
        _sensitive_var = secret
        raise RuntimeError(f"Database crash with {_sensitive_var}")

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/api/v1/test-fault")
    assert resp.status_code == 500
    data = resp.json()

    assert "error" in data
    assert data["error"]["code"] == "INTERNAL"
    assert data["error"]["message"] == "Internal server error"
    assert "correlation_id" in data["error"]

    # Absolutely no stack trace, filename, or token leaked to client
    assert "RuntimeError" not in resp.text
    assert "Traceback" not in resp.text
    assert secret not in resp.text


def test_public_mode_unsafe_config_refuses_to_start():
    """Unsafe public configuration refuses to start per T18-001."""
    from ml.schema import ConfigError

    # 1. Missing allowed origins in public mode
    with pytest.raises(ConfigError, match="Public mode requires explicit NADS_ALLOWED_ORIGINS"):
        ServerConfig(mode="public", allowed_origins=[], retention_enabled=False).validate()

    # 2. Wildcard origin in public mode
    with pytest.raises(ConfigError, match="Wildcard '\\*' origin is forbidden in public mode"):
        ServerConfig(mode="public", allowed_origins=["*"], retention_enabled=False).validate()

    # 3. Retention enabled in public mode
    with pytest.raises(ConfigError, match="Live session retention must be disabled in public mode"):
        ServerConfig(
            mode="public",
            allowed_origins=["https://dashboard.5g-nads.example.com"],
            retention_enabled=True,
        ).validate()


def test_public_mode_safe_config_starts_and_logs(caplog: pytest.LogCaptureFixture):
    """Safe public configuration starts cleanly and logs mode without secrets."""
    import logging

    secret_token = "secret-token-xyz-123"
    config = ServerConfig(
        mode="public",
        allowed_origins=["https://dashboard.5g-nads.example.com"],
        retention_enabled=False,
        ingest_token=secret_token,
    )

    with caplog.at_level(logging.INFO, logger="streaming.server"):
        app = create_app(config)

    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200

    # Mode is logged
    log_text = caplog.text
    assert "PUBLIC" in log_text
    # Secret token is never logged
    assert secret_token not in log_text

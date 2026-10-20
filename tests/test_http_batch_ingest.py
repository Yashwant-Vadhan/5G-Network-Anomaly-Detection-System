"""Unit tests for HTTP batch ingest fallback endpoint (T15-001).

Verifies:
1. Same golden examples validate cleanly via POST /api/v1/ingest/batch.
2. Duplicates ignored without crashing or corrupting metrics (Guardrail G19).
3. Authentication required when ingest token is configured (global & per-session tokens).
4. Rate limits enforced on oversized batches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from streaming.server import ServerConfig, create_app


@pytest.fixture
def golden_sample() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "fixtures" / "stream" / "c7_ingest_sample.example.json"
    assert fixture_path.exists(), f"Golden fixture missing at {fixture_path}"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_http_batch_ingest_golden_example_validates(golden_sample: dict[str, Any]) -> None:
    """Acceptance criterion 1: Same golden examples validate via HTTP batch fallback."""
    app = create_app()
    client = TestClient(app)

    batch = [golden_sample]
    resp = client.post("/api/v1/ingest/batch", json=batch)
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert data["accepted"] == 1
    assert data["duplicates"] == 0
    assert data["last_seq_acked"] == golden_sample["seq"]
    assert data["session_id"] is not None


def test_http_batch_ingest_wrapped_samples_dict(golden_sample: dict[str, Any]) -> None:
    """Accepts batch wrapped as {'samples': [...]}."""
    app = create_app()
    client = TestClient(app)

    payload = {"samples": [golden_sample]}
    resp = client.post("/api/v1/ingest/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert data["duplicates"] == 0


def test_http_batch_ingest_invalid_schema_rejected(golden_sample: dict[str, Any]) -> None:
    """Schema version != 2 or wrong message type is rejected with 422."""
    app = create_app()
    client = TestClient(app)

    # 1. Invalid schema_version
    bad_version = dict(golden_sample)
    bad_version["schema_version"] = 1
    resp = client.post("/api/v1/ingest/batch", json=[bad_version])
    assert resp.status_code == 422

    # 2. Invalid message type (ping instead of sample)
    bad_type = dict(golden_sample)
    bad_type["type"] = "ping"
    resp2 = client.post("/api/v1/ingest/batch", json=[bad_type])
    assert resp2.status_code == 422


def test_http_batch_ingest_duplicates_ignored_g19(golden_sample: dict[str, Any]) -> None:
    """Acceptance criterion 2: Duplicates ignored without crashing or corrupting metrics (G19)."""
    app = create_app()
    client = TestClient(app)

    s1 = dict(golden_sample)
    s1["seq"] = 1
    s2 = dict(golden_sample)
    s2["seq"] = 2
    s3 = dict(golden_sample)
    s3["seq"] = 3

    # Batch 1: Ingest s1 and s2
    r1 = client.post("/api/v1/ingest/batch", json=[s1, s2])
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["accepted"] == 2
    assert d1["duplicates"] == 0
    assert d1["last_seq_acked"] == 2
    session_id = d1["session_id"]

    # Batch 2: Resend s1, s2 and new s3 in same session
    r2 = client.post(
        f"/api/v1/ingest/batch?session_id={session_id}",
        json=[s1, s2, s3],
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["accepted"] == 1
    assert d2["duplicates"] == 2
    assert d2["last_seq_acked"] == 3

    # Batch 3: Intra-batch duplicates [s4, s4]
    s4 = dict(golden_sample)
    s4["seq"] = 4
    r3 = client.post(
        f"/api/v1/ingest/batch?session_id={session_id}",
        json=[s4, s4],
    )
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["accepted"] == 1
    assert d3["duplicates"] == 1
    assert d3["last_seq_acked"] == 4


def test_http_batch_ingest_auth_required(golden_sample: dict[str, Any]) -> None:
    """Acceptance criterion 3: Auth required when configured."""
    secret = "test-secret-token-abcdef123456"
    config = ServerConfig(ingest_token=secret)
    app = create_app(config)
    client = TestClient(app)

    # 1. Missing auth token -> 401
    r_no_auth = client.post("/api/v1/ingest/batch", json=[golden_sample])
    assert r_no_auth.status_code == 401

    # 2. Invalid auth token -> 401
    r_bad_auth = client.post(
        "/api/v1/ingest/batch",
        json=[golden_sample],
        headers={"Authorization": "Bearer wrong-token-xyz"},
    )
    assert r_bad_auth.status_code == 401

    # 3. Valid global Bearer token -> 200
    r_valid_bearer = client.post(
        "/api/v1/ingest/batch",
        json=[golden_sample],
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert r_valid_bearer.status_code == 200
    assert r_valid_bearer.json()["accepted"] == 1

    # 4. Valid token in query param -> 200
    s_next = dict(golden_sample)
    s_next["seq"] = golden_sample["seq"] + 1
    r_valid_query = client.post(
        f"/api/v1/ingest/batch?token={secret}",
        json=[s_next],
    )
    assert r_valid_query.status_code == 200
    assert r_valid_query.json()["accepted"] == 1

    # 5. Valid per-session ephemeral token -> 200
    session_token = "ephemeral-sess-token-999"
    target_session = "live-session-12345"
    app.state.session_ingest_tokens[session_token] = target_session

    s_sess = dict(golden_sample)
    s_sess["seq"] = 500
    r_sess_token = client.post(
        "/api/v1/ingest/batch",
        json=[s_sess],
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert r_sess_token.status_code == 200
    assert r_sess_token.json()["session_id"] == target_session


def test_http_batch_ingest_rate_limit_exceeded(golden_sample: dict[str, Any]) -> None:
    """Enforces rate limit when batch exceeds maximum allowed operational limit."""
    config = ServerConfig(max_msgs_per_min=3)
    app = create_app(config)
    client = TestClient(app)

    # Sending 4 samples when max_msgs_per_min is 3 -> 429
    samples = []
    for i in range(4):
        s = dict(golden_sample)
        s["seq"] = i + 1
        samples.append(s)

    resp = client.post("/api/v1/ingest/batch", json=samples)
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.json()["error"]["message"]

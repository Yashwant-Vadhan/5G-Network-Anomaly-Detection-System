"""Tests for limits, abuse controls, brute-force lockout, and idle session reaper (T18-004).

Acceptance Criteria:
- Limits configurable in ml/config.py with origin comments
- Lockout test passes
- Reaper frees memory (test)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from ml.config import (
    IDLE_SESSION_TIMEOUT_SECONDS,
    MAX_LIVE_SESSIONS,
    MAX_SESSION_CREATIONS_PER_IP,
    PAIRING_LOCKOUT_ATTEMPTS,
    PAIRING_LOCKOUT_SECONDS,
)
from streaming.schema import ScoredSample
from streaming.server import ServerConfig, create_app, reap_idle_sessions


def test_abuse_limits_configurable_with_origin_comments() -> None:
    """Verify that limits in ml/config.py are loaded and have expected default values."""
    assert MAX_LIVE_SESSIONS == 5
    assert PAIRING_LOCKOUT_ATTEMPTS == 5
    assert PAIRING_LOCKOUT_SECONDS == 900
    assert IDLE_SESSION_TIMEOUT_SECONDS == 900
    assert MAX_SESSION_CREATIONS_PER_IP == 10

    custom_cfg = ServerConfig(
        max_live_sessions=3,
        pairing_lockout_attempts=2,
        pairing_lockout_seconds=300,
        idle_session_timeout_seconds=60,
    )
    assert custom_cfg.max_live_sessions == 3
    assert custom_cfg.pairing_lockout_attempts == 2
    assert custom_cfg.pairing_lockout_seconds == 300
    assert custom_cfg.idle_session_timeout_seconds == 60


def test_pairing_brute_force_lockout() -> None:
    """Repeated failed pairing attempts trigger lockout with 429 Too Many Requests."""
    cfg = ServerConfig(pairing_lockout_attempts=3, pairing_lockout_seconds=600)
    app = create_app(cfg)
    client = TestClient(app)

    # Attempt 1 & 2: 404 code not found
    for _ in range(2):
        res = client.post("/api/v1/pair", json={"pairing_code": "INVALID1", "client_id": "phone1"})
        assert res.status_code == 404

    # Attempt 3: threshold reached -> 429 Lockout
    res3 = client.post("/api/v1/pair", json={"pairing_code": "INVALID2", "client_id": "phone1"})
    assert res3.status_code == 429
    detail_msg = res3.json()["error"]["message"]
    assert "Locked out" in detail_msg

    # Subsequent attempt within lockout window remains locked out
    res4 = client.post("/api/v1/pair", json={"pairing_code": "ANYCODE1", "client_id": "phone1"})
    assert res4.status_code == 429
    assert "Locked out" in res4.json()["error"]["message"]


def test_successful_pairing_resets_failed_counter() -> None:
    """A valid pairing resets the failed attempt tracking for the client IP."""
    cfg = ServerConfig(pairing_lockout_attempts=3, pairing_lockout_seconds=600)
    app = create_app(cfg)
    client = TestClient(app)

    # 2 failed attempts (under threshold of 3)
    for _ in range(2):
        res = client.post("/api/v1/pair", json={"pairing_code": "BADCODE1", "client_id": "phone1"})
        assert res.status_code == 404

    # Create a valid session and pair it
    create_res = client.post("/api/v1/live-sessions")
    assert create_res.status_code == 200
    code = create_res.json()["pairing_code"]

    pair_res = client.post("/api/v1/pair", json={"pairing_code": code, "client_id": "phone1"})
    assert pair_res.status_code == 200

    # Failed attempts for testclient IP should now be reset
    client_ip = "testclient"
    assert client_ip not in app.state.pairing_failed_attempts


def test_max_live_sessions_limit() -> None:
    """POST /api/v1/live-sessions enforces max_live_sessions cap."""
    cfg = ServerConfig(max_live_sessions=2)
    app = create_app(cfg)
    client = TestClient(app)

    # Create 2 sessions successfully
    res1 = client.post("/api/v1/live-sessions")
    assert res1.status_code == 200
    res2 = client.post("/api/v1/live-sessions")
    assert res2.status_code == 200

    # Third session exceeds cap -> 429
    res3 = client.post("/api/v1/live-sessions")
    assert res3.status_code == 429
    detail_msg = res3.json()["error"]["message"]
    assert "Maximum live sessions" in detail_msg


def test_reaper_frees_idle_session_memory() -> None:
    """Idle session reaper purges sessions, tickets, tokens, and telemetry buffers."""
    cfg = ServerConfig(idle_session_timeout_seconds=300)
    app = create_app(cfg)
    client = TestClient(app)

    # Create two sessions: sid_active and sid_idle
    res1 = client.post("/api/v1/live-sessions")
    sid_idle = res1.json()["session_id"]
    code_idle = res1.json()["pairing_code"]

    res2 = client.post("/api/v1/live-sessions")
    sid_active = res2.json()["session_id"]
    code_active = res2.json()["pairing_code"]

    # Pair both sessions
    p1 = client.post("/api/v1/pair", json={"pairing_code": code_idle, "client_id": "p1"})
    token_idle = p1.json()["ingest_token"]

    p2 = client.post("/api/v1/pair", json={"pairing_code": code_active, "client_id": "p2"})
    token_active = p2.json()["ingest_token"]

    # Generate tickets
    t1 = client.post(
        f"/api/v1/live-sessions/{sid_idle}/ticket",
        headers={"Authorization": f"Bearer {token_idle}"},
    )
    ticket_idle = t1.json()["ticket"]

    # Populate in-memory sample telemetry for both
    now_iso = datetime.now(UTC).isoformat()
    dummy_sample_idle = ScoredSample(
        seq=1,
        timestamp=now_iso,
        device="pixel7",
        session_id=sid_idle,
        received_at=now_iso,
        scored_at=now_iso,
        published_at=now_iso,
        ss_rsrp=-85.0,
        if_score=0.1,
    )
    dummy_sample_active = ScoredSample(
        seq=1,
        timestamp=now_iso,
        device="pixel7",
        session_id=sid_active,
        received_at=now_iso,
        scored_at=now_iso,
        published_at=now_iso,
        ss_rsrp=-85.0,
        if_score=0.1,
    )
    app.state.session_samples[sid_idle] = [dummy_sample_idle]
    app.state.session_samples[sid_active] = [dummy_sample_active]

    # Advance time: set sid_idle last_active_at to 400 seconds in past
    past_time = datetime.now(UTC) - timedelta(seconds=400)
    app.state.active_live_sessions[sid_idle]["last_active_at"] = past_time

    # Run reaper at current time
    reaped = reap_idle_sessions(app)
    assert sid_idle in reaped
    assert sid_active not in reaped

    # Verify memory is freed for sid_idle (G29)
    assert sid_idle not in app.state.active_live_sessions
    assert code_idle not in app.state.pairing_sessions
    assert token_idle not in app.state.session_ingest_tokens
    assert ticket_idle not in app.state.live_session_tickets
    assert sid_idle not in app.state.session_samples

    # Verify sid_active remains intact
    assert sid_active in app.state.active_live_sessions
    assert code_active in app.state.pairing_sessions
    assert token_active in app.state.session_ingest_tokens
    assert sid_active in app.state.session_samples

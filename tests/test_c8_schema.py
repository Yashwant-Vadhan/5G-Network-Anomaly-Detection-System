"""Unit tests for Contract C8 live-event and REST response models (T10-006)."""

import pytest
from pydantic import TypeAdapter, ValidationError

from streaming.schema import (
    ALERT_DECISION_REASONS,
    AlertDecision,
    BrowserAuthFrame,
    ConnectionEvent,
    DroppedEvent,
    ErrorDetail,
    ErrorResponse,
    EventRecord,
    HealthResponse,
    HeartbeatEvent,
    LiveEventClosed,
    LiveEventOpen,
    LiveEventUpdate,
    LiveSampleEvent,
    LiveSubscriberMessage,
    MetricsResponse,
    ModelInfoResponse,
    SamplesResponse,
    ScoredSample,
    SessionListResponse,
    SessionSummary,
    SnapshotEvent,
)


def test_status_closed_enum():
    """EventRecord.status must be strictly PROVISIONAL or FINAL."""
    base_data = {
        "event_id": "evt-001",
        "session_id": "redmi-1",
        "start": "2026-10-09T10:15:00+05:30",
        "end": "2026-10-09T10:15:30+05:30",
        "anomaly_type": "SIGNAL_DEGRADATION",
        "severity": "HIGH",
        "ml": {"anomaly_type": "SIGNAL_DEGRADATION", "max_severity": "HIGH"},
        "alert_decision": {
            "alerted": True,
            "reason": "Alert triggered",
        },
    }

    # Valid PROVISIONAL
    rec_prov = EventRecord.model_validate({**base_data, "status": "PROVISIONAL"})
    assert rec_prov.status == "PROVISIONAL"

    # Valid FINAL
    rec_final = EventRecord.model_validate({**base_data, "status": "FINAL"})
    assert rec_final.status == "FINAL"

    # Invalid status must be rejected
    with pytest.raises(ValidationError):
        EventRecord.model_validate({**base_data, "status": "PENDING"})


def test_alert_decision_five_fixed_reasons():
    """alert_decision.reason must be one of the five fixed strings from DESIGN_v2."""
    assert len(ALERT_DECISION_REASONS) == 5
    for reason in ALERT_DECISION_REASONS:
        decision = AlertDecision(alerted=False, reason=reason)
        assert decision.reason == reason

    # Any unknown string must be rejected
    with pytest.raises(ValidationError):
        AlertDecision(alerted=False, reason="Unrecognized custom alert reason")


def test_scored_sample_and_live_sample_event_round_trip():
    """ScoredSample carries all C4 columns and streaming timestamps; LiveSampleEvent round-trips."""
    sample_data = {
        "timestamp": "01-10-26 18:26:32",
        "device": "SM-A156E",
        "manufacturer": "samsung",
        "android": "16",
        "operator": "airtel",
        "network_type": "LTE",
        "deployment_mode": "NSA",
        "display_override": "NR_NSA",
        "registered": False,
        "ss_rsrp": -97.0,
        "ss_rsrq": -12.0,
        "ss_sinr": 3.0,
        "csi_rsrp": None,
        "csi_rsrq": None,
        "csi_sinr": None,
        "pci": 861,
        "nci": 0,
        "nrarfcn": 629952,
        "session_id": "sm-a156e-1",
        "sample_idx": 42,
        "is_valid": True,
        "model_eligible": True,
        "csi_available": False,
        "is_synthetic": False,
        "source_file": "5G_measurements_Samsung_Indoor-Movement.csv",
        "dup_ts": False,
        "delta_rsrp": -2.0,
        "delta_rsrq": 0.0,
        "delta_sinr": 1.0,
        "pci_changed": False,
        "nci_changed": False,
        "network_changed": False,
        "rolling_mean_rsrp": -96.5,
        "rolling_std_rsrp": 0.5,
        "rolling_mean_rsrq": -12.0,
        "rolling_std_rsrq": 0.0,
        "rolling_mean_sinr": 2.8,
        "rolling_std_sinr": 0.4,
        "weak_rsrp_run": 0,
        "poor_rsrq_run": 0,
        "poor_sinr_run": 0,
        "baseline_z_rsrp": 0.2,
        "baseline_z_rsrq": 0.1,
        "baseline_z_sinr": -0.4,
        "baseline_z_max": 0.4,
        "baseline_flag": False,
        "if_score": 0.35,
        "if_flag": False,
        "anomaly_type": "NORMAL",
        "severity": "NONE",
        "event_id": None,
        "is_anom": False,
        "seq": 42,
        "received_at": "2026-10-01T18:26:32.500+05:30",
        "scored_at": "2026-10-01T18:26:32.505+05:30",
        "published_at": "2026-10-01T18:26:32.508+05:30",
        "edge_if_score": 0.34,
        "edge_divergence": 0.01,
    }

    sample = ScoredSample.model_validate(sample_data)
    assert sample.seq == 42
    assert sample.edge_if_score == 0.34

    live_event = LiveSampleEvent(
        server_time="2026-10-01T18:26:32.510+05:30",
        session_id="sm-a156e-1",
        sample=sample,
    )
    assert live_event.type == "sample"

    # Adapter round-trip
    adapter = TypeAdapter(LiveSubscriberMessage)
    dumped = live_event.model_dump(mode="json")
    reloaded = adapter.validate_python(dumped)
    assert reloaded == live_event


def test_scored_sample_invalid_timestamp_rejected():
    """Missing timezone offset in streaming timestamps must be rejected."""
    bad_data = {
        "timestamp": "01-10-26 18:26:32",
        "device": "SM-A156E",
        "session_id": "sm-a156e-1",
        "seq": 1,
        "received_at": "2026-10-01T18:26:32",  # Missing offset
        "scored_at": "2026-10-01T18:26:32.505+05:30",
        "published_at": "2026-10-01T18:26:32.508+05:30",
    }
    with pytest.raises(ValidationError):
        ScoredSample.model_validate(bad_data)


def test_live_subscriber_events():
    """All live subscriber message types serialize and discriminate properly."""
    adapter = TypeAdapter(LiveSubscriberMessage)

    # 1. ConnectionEvent
    conn = ConnectionEvent(
        server_time="2026-10-09T10:15:00+05:30",
        session_id="redmi-1",
        state="LIVE",
        last_sample_age_s=1.2,
        source="phone",
    )
    assert adapter.validate_python(conn.model_dump(mode="json")).type == "connection"

    # 2. DroppedEvent
    drop = DroppedEvent(
        server_time="2026-10-09T10:15:05+05:30",
        session_id="redmi-1",
        count=15,
    )
    assert adapter.validate_python(drop.model_dump(mode="json")).type == "dropped"

    # 3. HeartbeatEvent
    hb = HeartbeatEvent(
        server_time="2026-10-09T10:15:10+05:30",
    )
    assert adapter.validate_python(hb.model_dump(mode="json")).type == "heartbeat"

    # 4. SnapshotEvent
    snap = SnapshotEvent(
        server_time="2026-10-09T10:15:10+05:30",
        session_id="redmi-1",
        state="LIVE",
        open_events=[],
        last_alerts=[],
    )
    assert adapter.validate_python(snap.model_dump(mode="json")).type == "snapshot"

    # 5. LiveEventOpen / Update / Closed
    evt_record = EventRecord(
        event_id="evt-001",
        session_id="redmi-1",
        start="2026-10-09T10:15:00+05:30",
        end="2026-10-09T10:15:30+05:30",
        anomaly_type="SIGNAL_DEGRADATION",
        severity="HIGH",
        ml={"anomaly_type": "SIGNAL_DEGRADATION"},
        status="PROVISIONAL",
        alert_decision=AlertDecision(alerted=False, reason="Below persistence/severity threshold"),
    )
    ev_open = LiveEventOpen(
        server_time="2026-10-09T10:15:00+05:30", session_id="redmi-1", event=evt_record
    )
    assert adapter.validate_python(ev_open.model_dump(mode="json")).type == "event_open"

    ev_upd = LiveEventUpdate(
        server_time="2026-10-09T10:15:10+05:30", session_id="redmi-1", event=evt_record
    )
    assert adapter.validate_python(ev_upd.model_dump(mode="json")).type == "event_update"

    evt_final = evt_record.model_copy(update={"status": "FINAL"})
    ev_close = LiveEventClosed(
        server_time="2026-10-09T10:15:30+05:30", session_id="redmi-1", event=evt_final
    )
    assert adapter.validate_python(ev_close.model_dump(mode="json")).type == "event_closed"


def test_browser_auth_frame():
    auth = BrowserAuthFrame(ticket="ticket-uuid-12345")
    assert auth.type == "auth"
    assert auth.ticket == "ticket-uuid-12345"

    with pytest.raises(ValidationError):
        BrowserAuthFrame(ticket="")


def test_rest_response_models():
    """All REST response models conform to C8 specifications."""
    health = HealthResponse(uptime_s=123.45)
    assert health.status == "ok"
    assert health.version == "2.0.0"

    sess_summary = SessionSummary(
        session_id="sess-001",
        source="replay",
        status="OPEN",
        sample_count=100,
    )
    sess_list = SessionListResponse(sessions=[sess_summary], total=1)
    assert len(sess_list.sessions) == 1

    model_info = ModelInfoResponse(
        model_version="if_v1",
        feature_columns=["ss_rsrp", "ss_sinr"],
        feature_hash="hash123",
        thresholds={"if_threshold": 0.6},
    )
    assert model_info.model_version == "if_v1"

    metrics = MetricsResponse(p50_latency_ms=2.1, p95_latency_ms=4.8, max_latency_ms=12.0)
    assert metrics.p50_latency_ms == 2.1

    samples_resp = SamplesResponse(samples=[], total=0, has_more=False)
    assert samples_resp.total == 0

    err = ErrorResponse(
        error=ErrorDetail(
            code="BAD_REQUEST", message="Invalid seq parameter", correlation_id="req-999"
        )
    )
    assert err.error.code == "BAD_REQUEST"

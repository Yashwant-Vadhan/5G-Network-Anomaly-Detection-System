"""Unit tests for Contract C9 alert models and JSONL format (T10-007)."""

import json

import pytest
from pydantic import ValidationError

from streaming.schema import (
    AlertDelivery,
    AlertRecord,
    deserialize_alert_jsonl,
    serialize_alert_jsonl,
)


def test_alert_kind_enum():
    """AlertRecord.kind must be strictly NEW, ESCALATION, or RESOLVED."""
    base_data = {
        "alert_id": "al-000001",
        "created_at": "2026-10-09T10:15:41+05:30",
        "event_id": "redmi-1-e003",
        "session_id": "redmi-1",
        "source": "phone",
        "severity": "MEDIUM",
        "anomaly_type": "PERSISTENT_POOR_QUALITY",
        "event_status": "PROVISIONAL",
        "title": "MEDIUM · Persistent poor radio quality (possible)",
        "body": "SINR below configured threshold for 24s",
    }

    # Test all 3 allowed kinds
    for kind in ["NEW", "ESCALATION", "RESOLVED"]:
        rec = AlertRecord.model_validate({**base_data, "kind": kind})
        assert rec.kind == kind

    # Disallowed kind raises ValidationError
    with pytest.raises(ValidationError):
        AlertRecord.model_validate({**base_data, "kind": "REOPENED"})


def test_webhook_body_data_minimization():
    """to_webhook_body() returns strictly title, body, severity, anomaly_type, event_status, created_at by default."""
    alert = AlertRecord(
        alert_id="al-000017",
        created_at="2026-10-09T10:15:41+05:30",
        event_id="redmi-1-e003",
        session_id="redmi-1",
        source="phone",
        kind="NEW",
        severity="MEDIUM",
        anomaly_type="PERSISTENT_POOR_QUALITY",
        event_status="PROVISIONAL",
        title="MEDIUM · Persistent poor radio quality (possible)",
        body="SINR below the configured poor-quality level for 24 s; RSRQ also degraded; no cell change in the window.",
        evidence=["SS-RSRP degraded to -105 dBm", "PCI was 336", "Cell ID 13322280247"],
        recommendation={"text": "Investigate coverage gap", "kind": "INVESTIGATION"},
        policy={
            "rule_evidence": True,
            "persistence_samples": 8,
            "min_persistence": 6,
            "min_severity": "MEDIUM",
        },
        delivery=[
            AlertDelivery(channel="in_app", status="OK"),
            AlertDelivery(channel="webhook", status="FAILED", detail="timeout"),
        ],
    )

    webhook_body = alert.to_webhook_body()
    assert set(webhook_body.keys()) == {
        "title",
        "body",
        "severity",
        "anomaly_type",
        "event_status",
        "created_at",
    }
    # Sensitive and device details must not be in default webhook payload (G26)
    assert "evidence" not in webhook_body
    assert "event_id" not in webhook_body
    assert "session_id" not in webhook_body
    assert "policy" not in webhook_body
    assert "delivery" not in webhook_body

    # Explicit opt-in allows evidence
    with_evidence = alert.to_webhook_body(include_evidence=True)
    assert "evidence" in with_evidence


def test_jsonl_round_trip():
    """AlertRecord round-trips via single-line JSONL serialization/deserialization."""
    original = AlertRecord(
        alert_id="al-000099",
        created_at="2026-10-09T11:20:00+05:30",
        event_id="samsung-1-e001",
        session_id="samsung-1",
        source="replay",
        kind="ESCALATION",
        severity="HIGH",
        anomaly_type="SIGNAL_DEGRADATION",
        event_status="FINAL",
        title="HIGH · Sudden signal degradation (possible)",
        body="RSRP dropped by 15 dB in 3 s",
        evidence=["RSRP drop"],
        recommendation={"text": "Monitor area", "kind": "MONITORING"},
        policy={"rule_evidence": True},
        delivery=[AlertDelivery(channel="in_app", status="OK")],
        acknowledged_at=None,
    )

    line = serialize_alert_jsonl(original)
    assert line.endswith("\n")
    # Must be valid single JSON object
    parsed_dict = json.loads(line.strip())
    assert parsed_dict["alert_id"] == "al-000099"

    reloaded = deserialize_alert_jsonl(line)
    assert reloaded == original

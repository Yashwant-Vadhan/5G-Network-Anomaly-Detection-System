"""Tests for T13-001: Alert policy pure functional decision engine (G6, G21)."""

from __future__ import annotations

from typing import Any

from streaming.alerts.policy import decide, has_agent_rule_evidence
from streaming.schema import AlertDecision


def make_event(
    anomaly_type: str = "SIGNAL_DEGRADATION",
    severity: str = "MEDIUM",
    persistence: int = 6,
    rule_evidence: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """Helper constructing an event payload for policy decision testing."""
    evt: dict[str, Any] = {
        "event_id": "test-ev-001",
        "session_id": "test-session",
        "start": "2026-10-17T10:00:00+05:30",
        "end": "2026-10-17T10:00:18+05:30",
        "anomaly_type": anomaly_type,
        "severity": severity,
        "persistence": persistence,
        "rule_evidence": rule_evidence,
        "ml": {"sample_count": persistence},
        "status": "PROVISIONAL",
    }
    evt.update(kwargs)
    return evt


def test_statistical_only_ml_flag_never_alerts():
    """STATISTICAL_ONLY flag without rule evidence returns 'ML-only (no rule evidence)'."""
    evt = make_event(anomaly_type="STATISTICAL_ONLY", rule_evidence=False)
    decision = decide(evt)
    assert isinstance(decision, AlertDecision)
    assert decision.alerted is False
    assert decision.reason == "ML-only (no rule evidence)"


def test_cell_transition_alone_never_alerts():
    """Guardrails G6/G21: Cell transitions alone never trigger alerts."""
    evt = make_event(
        anomaly_type="CELL_TRANSITION",
        severity="HIGH",
        persistence=10,
        rule_evidence=True,
    )
    decision = decide(evt)
    assert decision.alerted is False
    assert decision.reason == "Transition only"


def test_network_state_transition_alone_never_alerts():
    """Guardrails G6/G21: Network state transitions alone never trigger alerts."""
    evt = make_event(
        anomaly_type="NETWORK_STATE_TRANSITION",
        severity="HIGH",
        persistence=10,
        rule_evidence=True,
    )
    decision = decide(evt)
    assert decision.alerted is False
    assert decision.reason == "Transition only"


def test_normal_state_never_alerts():
    """Normal state events never trigger alerts."""
    evt = make_event(anomaly_type="NORMAL", severity="NONE", persistence=10)
    decision = decide(evt)
    assert decision.alerted is False
    assert decision.reason == "Transition only"


def test_missing_agent_rule_evidence_rejected_as_ml_only():
    """Anomalies lacking corroborating agent rule evidence are rejected."""
    evt = make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="HIGH",
        persistence=10,
        rule_evidence=False,
        evidence=[],
        signal_report={},
        diagnosis={},
    )
    decision = decide(evt)
    assert decision.alerted is False
    assert decision.reason == "ML-only (no rule evidence)"


def test_below_persistence_and_severity_threshold():
    """Events with rule evidence below both persistence and severity thresholds are rejected."""
    evt = make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="LOW",  # Below MEDIUM
        persistence=2,  # Below 6
        rule_evidence=True,
    )
    decision = decide(evt)
    assert decision.alerted is False
    assert decision.reason == "Below persistence/severity threshold"


def test_alert_triggered_by_meeting_persistence_threshold():
    """Persistence >= ALERT_MIN_PERSISTENCE_SAMPLES triggers alert even if severity is LOW."""
    evt = make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="LOW",
        persistence=6,  # Meets default 6
        rule_evidence=True,
    )
    decision = decide(evt)
    assert decision.alerted is True
    assert decision.reason == "Alert triggered"


def test_alert_triggered_by_meeting_severity_threshold():
    """Severity >= ALERT_MIN_SEVERITY triggers alert even if persistence is below threshold."""
    evt = make_event(
        anomaly_type="PERSISTENT_POOR_QUALITY",
        severity="MEDIUM",  # Meets default MEDIUM
        persistence=2,  # Below 6
        rule_evidence=True,
    )
    decision = decide(evt)
    assert decision.alerted is True
    assert decision.reason == "Alert triggered"


def test_alert_triggered_high_severity():
    """High severity events with rule evidence trigger alerts."""
    evt = make_event(
        anomaly_type="COMBINED_ANOMALY",
        severity="HIGH",
        persistence=3,
        rule_evidence=True,
    )
    decision = decide(evt)
    assert decision.alerted is True
    assert decision.reason == "Alert triggered"


def test_agent_reports_evidence_detection():
    """Agent report findings and evidence lists are correctly recognized by has_agent_rule_evidence."""
    # From signal_report findings
    e1 = {"signal_report": {"findings": ["SS-RSRP -115 dBm"]}}
    assert has_agent_rule_evidence(e1) is True

    # From diagnosis primary cause
    e2 = {"diagnosis": {"primary_cause": "POOR_COVERAGE"}}
    assert has_agent_rule_evidence(e2) is True

    # From top-level evidence
    e3 = {"evidence": ["Degraded SINR"]}
    assert has_agent_rule_evidence(e3) is True

    # Empty reports
    e4 = {"signal_report": {}, "diagnosis": {"primary_cause": "NORMAL"}}
    assert has_agent_rule_evidence(e4) is False


def test_custom_config_thresholds_override():
    """Config parameter can override default persistence and severity thresholds."""

    class CustomConfig:
        ALERT_MIN_PERSISTENCE_SAMPLES = 10
        ALERT_MIN_SEVERITY = "HIGH"

    evt = make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="MEDIUM",  # Meets default MEDIUM, but not custom HIGH
        persistence=7,  # Meets default 6, but not custom 10
        rule_evidence=True,
    )
    # Default config triggers
    assert decide(evt).alerted is True

    # Custom config rejects because below both custom thresholds
    custom_decision = decide(evt, config=CustomConfig())
    assert custom_decision.alerted is False
    assert custom_decision.reason == "Below persistence/severity threshold"


def test_pure_function_no_side_effects_or_mutation():
    """decide() does not mutate input event or depend on global state."""
    evt = make_event(
        anomaly_type="SUDDEN_SIGNAL_DEGRADATION",
        severity="HIGH",
        persistence=8,
        rule_evidence=True,
    )
    original_keys = set(evt.keys())
    decision = decide(evt)
    assert decision.alerted is True
    assert set(evt.keys()) == original_keys

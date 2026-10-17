"""Tests for T13-001: Alert policy pure functional decision engine (G6, G21)."""

from __future__ import annotations

from typing import Any

from streaming.alerts.policy import (
    AlertStateTracker,
    decide,
    has_agent_rule_evidence,
)
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
    """Agent reports and evidence lists are correctly recognized by has_agent_rule_evidence."""
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


def test_cooldown_with_injectable_clock():
    """T13-002: Cooldown tested with an injectable clock."""
    simulated_time = 1000.0

    def mock_clock() -> float:
        return simulated_time

    evt = make_event(
        session_id="session-clk",
        anomaly_type="SIGNAL_DEGRADATION",
        severity="MEDIUM",
        persistence=8,
        rule_evidence=True,
    )

    history: list[dict[str, Any]] = []

    # 1. First emission at t=1000.0 triggers NEW alert
    d1 = decide(evt, history=history, clock=mock_clock)
    assert d1.alerted is True
    assert d1.kind == "NEW"
    assert d1.reason == "Alert triggered"

    # Record emitted alert in history
    alert_1 = {
        "alert_id": "alt-001",
        "session_id": "session-clk",
        "anomaly_type": "SIGNAL_DEGRADATION",
        "severity": "MEDIUM",
        "created_at": "1000.0",
        "kind": "NEW",
        "delivery": [{"channel": "in_app", "status": "OK"}],
    }
    history.append(alert_1)

    # 2. Advance clock by 100s (< 300s cooldown)
    simulated_time = 1100.0
    d2 = decide(evt, history=history, clock=mock_clock)
    assert d2.alerted is False
    assert d2.kind is None
    assert d2.reason == "Cooldown active"

    # 3. Advance clock past 300s cooldown (t=1305.0)
    simulated_time = 1305.0
    d3 = decide(evt, history=history, clock=mock_clock)
    assert d3.alerted is True
    assert d3.kind == "NEW"
    assert d3.reason == "Alert triggered"


def test_no_duplicate_new_after_reconnect():
    """T13-002: No duplicate NEW alert triggered after phone reconnects within cooldown."""
    alert_history = [
        {
            "alert_id": "alt-rec-1",
            "session_id": "sess-reconnect-1",
            "anomaly_type": "PERSISTENT_POOR_QUALITY",
            "severity": "MEDIUM",
            "created_at": "2026-10-17T10:00:00+00:00",
            "kind": "NEW",
            "delivery": [{"channel": "in_app", "status": "OK"}],
        }
    ]

    # Reconnect occurs 60 seconds later with new provisional event
    reconnect_evt = make_event(
        session_id="sess-reconnect-1",
        anomaly_type="PERSISTENT_POOR_QUALITY",
        severity="MEDIUM",
        persistence=10,
        rule_evidence=True,
        timestamp="2026-10-17T10:01:00+00:00",
    )

    decision = decide(reconnect_evt, history=alert_history)
    assert decision.alerted is False
    assert decision.kind is None
    assert decision.reason == "Cooldown active"


def test_resolved_never_sent_without_prior_delivered_alert():
    """T13-002: RESOLVED is never sent without a prior delivered alert."""
    closed_evt = make_event(
        event_id="ev-closed-01",
        session_id="sess-res-1",
        anomaly_type="SIGNAL_DEGRADATION",
        status="FINAL",
        rule_evidence=True,
    )

    # 1. Closed event without prior alert history -> NO resolved alert
    d1 = decide(closed_evt, history=[])
    assert d1.alerted is False
    assert d1.kind is None
    assert d1.reason == "Below persistence/severity threshold"

    # 2. Closed event where prior alert delivery failed -> NO resolved alert
    failed_history = [
        {
            "event_id": "ev-closed-01",
            "session_id": "sess-res-1",
            "anomaly_type": "SIGNAL_DEGRADATION",
            "kind": "NEW",
            "delivery": [{"channel": "webhook", "status": "FAILED"}],
        }
    ]
    d2 = decide(closed_evt, history=failed_history)
    assert d2.alerted is False
    assert d2.kind is None

    # 3. Closed event with prior DELIVERED alert -> Emits RESOLVED
    delivered_history = [
        {
            "event_id": "ev-closed-01",
            "session_id": "sess-res-1",
            "anomaly_type": "SIGNAL_DEGRADATION",
            "kind": "NEW",
            "delivery": [{"channel": "in_app", "status": "OK"}],
        }
    ]
    d3 = decide(closed_evt, history=delivered_history)
    assert d3.alerted is True
    assert d3.kind == "RESOLVED"
    assert d3.reason == "Alert triggered"

    # 4. RESOLVED already emitted -> Do not emit duplicate RESOLVED
    resolved_history = list(delivered_history) + [
        {
            "event_id": "ev-closed-01",
            "session_id": "sess-res-1",
            "anomaly_type": "SIGNAL_DEGRADATION",
            "kind": "RESOLVED",
            "delivery": [{"channel": "in_app", "status": "OK"}],
        }
    ]
    d4 = decide(closed_evt, history=resolved_history)
    assert d4.alerted is False


def test_escalation_when_severity_rises_during_cooldown():
    """T13-002: ESCALATION is allowed during cooldown when severity strictly increases."""
    tracker = AlertStateTracker(cooldown_seconds=300)
    tracker.record(
        {
            "event_id": "ev-esc-01",
            "session_id": "sess-esc-1",
            "anomaly_type": "SIGNAL_DEGRADATION",
            "severity": "LOW",
            "created_at": "1000.0",
            "kind": "NEW",
            "delivery": [{"channel": "in_app", "status": "OK"}],
        }
    )

    # 1. Same severity within cooldown -> Suppressed by cooldown
    low_evt = make_event(
        event_id="ev-esc-01",
        session_id="sess-esc-1",
        anomaly_type="SIGNAL_DEGRADATION",
        severity="LOW",
        persistence=8,
        rule_evidence=True,
    )
    d_same = decide(low_evt, history=tracker, now=1050.0)
    assert d_same.alerted is False
    assert d_same.reason == "Cooldown active"

    # 2. Higher severity (MEDIUM > LOW) within cooldown -> ESCALATION allowed!
    med_evt = make_event(
        event_id="ev-esc-01",
        session_id="sess-esc-1",
        anomaly_type="SIGNAL_DEGRADATION",
        severity="MEDIUM",
        persistence=8,
        rule_evidence=True,
    )
    d_esc = decide(med_evt, history=tracker, now=1050.0)
    assert d_esc.alerted is True
    assert d_esc.kind == "ESCALATION"
    assert d_esc.reason == "Alert triggered"

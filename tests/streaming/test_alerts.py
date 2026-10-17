"""Comprehensive alert tests: policy negatives, cooldown, channel failure (T13-009).

Acceptance Criteria:
- All negative cases from v1 list covered (Guardrail G21):
  ML-only, low RSRP only, low SINR only, UNKNOWN only, cell change only,
  5G->LTE only -> no alert.
- Cooldown, escalation, and resolution lifecycle verified.
- Webhook timeout and email channel failure do not affect in-app delivery.
- Property-style test over fixtures.
- Coverage on streaming/alerts/ >= 85%.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from streaming.alerts.channels.in_app import InAppChannel
from streaming.alerts.channels.webhook import WebhookChannel
from streaming.alerts.dispatcher import AlertDispatcher
from streaming.alerts.policy import (
    AlertStateTracker,
    _is_alert_delivered,
    _parse_alert_time,
    decide,
    has_agent_rule_evidence,
)
from streaming.hub import LiveHub
from streaming.schema import AlertDelivery, AlertRecord, deserialize_alert_jsonl


def _make_event(
    anomaly_type: str = "SIGNAL_DEGRADATION",
    severity: str = "MEDIUM",
    persistence: int = 6,
    rule_evidence: bool = True,
    status: str = "PROVISIONAL",
    **kwargs: Any,
) -> dict[str, Any]:
    """Helper constructing an event payload for policy decision testing."""
    evt: dict[str, Any] = {
        "event_id": "test-ev-100",
        "session_id": "test-session-1",
        "start": "2026-10-17T10:00:00+00:00",
        "end": "2026-10-17T10:00:15+00:00",
        "anomaly_type": anomaly_type,
        "severity": severity,
        "persistence": persistence,
        "rule_evidence": rule_evidence,
        "ml": {"sample_count": persistence},
        "status": status,
    }
    evt.update(kwargs)
    return evt


def _make_alert_record(
    alert_id: str = "alt-t13-009",
    kind: str = "NEW",
    severity: str = "MEDIUM",
    status: str = "PROVISIONAL",
    created_at: str = "2026-10-17T10:00:15+00:00",
    session_id: str = "test-session-1",
) -> AlertRecord:
    """Helper constructing a valid C9 AlertRecord."""
    return AlertRecord(
        alert_id=alert_id,
        created_at=created_at,
        event_id="test-ev-100",
        session_id=session_id,
        source="phone",
        kind=kind,  # type: ignore[arg-type]
        severity=severity,
        anomaly_type="SIGNAL_DEGRADATION",
        event_status=status,  # type: ignore[arg-type]
        title=f"{severity} · Test Alert",
        body="Signal degraded below threshold",
        evidence=["ss_rsrp < -110 dBm"],
        recommendation={"action": "reorient"},
        policy={"tier": severity},
        delivery=[],
    )


# ==============================================================================
# 1. Policy Negative Cases from v1 List (Guardrail G21)
# ==============================================================================


def test_ml_only_without_rule_evidence_never_alerts() -> None:
    """ML anomaly detection alone without rule evidence never triggers alerts (G21)."""
    evt1 = _make_event(anomaly_type="STATISTICAL_ONLY", rule_evidence=False)
    dec1 = decide(evt1)
    assert not dec1.alerted
    assert "ML-only" in dec1.reason

    evt2 = _make_event(anomaly_type="SIGNAL_DEGRADATION", rule_evidence=False)
    dec2 = decide(evt2)
    assert not dec2.alerted
    assert "ML-only" in dec2.reason


def test_low_rsrp_only_below_persistence_never_alerts() -> None:
    """Low RSRP spike below persistence threshold never alerts."""
    evt = _make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="LOW",
        persistence=1,
        rule_evidence=False,
        evidence=["ss_rsrp < -115 dBm"],
    )
    dec = decide(evt)
    assert not dec.alerted


def test_low_sinr_only_below_persistence_never_alerts() -> None:
    """Low SINR alone without sustained persistence or corroboration never alerts."""
    evt = _make_event(
        anomaly_type="POOR_RADIO_QUALITY",
        severity="LOW",
        persistence=2,
        rule_evidence=False,
        evidence=["ss_sinr < -5 dB"],
    )
    dec = decide(evt)
    assert not dec.alerted


def test_unknown_anomaly_type_alone_never_alerts() -> None:
    """Events flagged as UNKNOWN anomaly type never trigger an alert."""
    evt = _make_event(
        anomaly_type="UNKNOWN",
        severity="LOW",
        persistence=1,
        rule_evidence=False,
    )
    dec = decide(evt)
    assert not dec.alerted
    assert "ML-only" in dec.reason


def test_cell_change_transitions_never_alert() -> None:
    """Normal cell reselection, handover, and beam switch transitions never alert."""
    transitions = [
        "CELL_RESELECTION",
        "HANDOVER",
        "BEAM_SWITCH",
        "CELL_TRANSITION",
        "NETWORK_STATE_TRANSITION",
    ]
    for tr in transitions:
        evt = _make_event(anomaly_type=tr, rule_evidence=True, persistence=10)
        dec = decide(evt)
        assert not dec.alerted
        assert dec.reason == "Transition only"


def test_five_g_to_lte_handoff_alone_never_alerts() -> None:
    """5G to LTE technology transition alone does not trigger an anomaly alert."""
    evt = _make_event(
        anomaly_type="HANDOVER",
        technology_change="5G_TO_LTE",
        rule_evidence=True,
    )
    dec = decide(evt)
    assert not dec.alerted
    assert dec.reason == "Transition only"


# ==============================================================================
# 2. Cooldown, Escalation, and Resolution Lifecycle
# ==============================================================================


def test_cooldown_escalation_and_resolve_lifecycle() -> None:
    """Verify NEW alert -> Cooldown suppression -> Severity escalation -> Resolution."""
    tracker = AlertStateTracker(cooldown_seconds=300)

    # 1. First event: triggers NEW alert
    evt1 = _make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="MEDIUM",
        persistence=6,
        rule_evidence=True,
        end="2026-10-17T10:00:15+00:00",
    )
    dec1 = decide(evt1, history=tracker)
    assert dec1.alerted
    assert dec1.kind == "NEW"

    # Record the delivered alert
    alt1 = _make_alert_record(
        alert_id="alt-1",
        kind="NEW",
        severity="MEDIUM",
        created_at="2026-10-17T10:00:15+00:00",
    )
    alt1.delivery = [AlertDelivery(channel="in_app", status="OK")]
    tracker.record(alt1)

    # 2. Same severity 60s later: suppressed by cooldown
    evt2 = _make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="MEDIUM",
        persistence=8,
        rule_evidence=True,
        end="2026-10-17T10:01:15+00:00",
    )
    dec2 = decide(evt2, history=tracker)
    assert not dec2.alerted
    assert "cooldown" in dec2.reason.lower()

    # 3. Escalation: severity increases to CRITICAL within cooldown -> ESCALATION alert
    evt3 = _make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="CRITICAL",
        persistence=10,
        rule_evidence=True,
        end="2026-10-17T10:02:00+00:00",
    )
    dec3 = decide(evt3, history=tracker)
    assert dec3.alerted
    assert dec3.kind == "ESCALATION"

    alt2 = _make_alert_record(
        alert_id="alt-2",
        kind="ESCALATION",
        severity="CRITICAL",
        created_at="2026-10-17T10:02:00+00:00",
    )
    alt2.delivery = [AlertDelivery(channel="in_app", status="OK")]
    tracker.record(alt2)

    # 4. Resolved: event finishes (status=FINAL) -> RESOLVED alert
    evt4 = _make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        severity="CRITICAL",
        status="FINAL",
        end="2026-10-17T10:05:00+00:00",
    )
    dec4 = decide(evt4, history=tracker)
    assert dec4.alerted
    assert dec4.kind == "RESOLVED"

    # 5. Resolved event with NO prior alert delivered does not send RESOLVED
    empty_tracker = AlertStateTracker(cooldown_seconds=300)
    evt_unalerted = _make_event(
        anomaly_type="SIGNAL_DEGRADATION",
        status="FINAL",
    )
    dec_unalerted = decide(evt_unalerted, history=empty_tracker)
    assert not dec_unalerted.alerted


# ==============================================================================
# 3. Channel Failure Isolation (Webhook Timeout & Email Failure)
# ==============================================================================


class FailingEmailChannel:
    """Simulated outbound email channel that always crashes or times out."""

    name: str = "email"

    async def send(self, alert: AlertRecord) -> AlertDelivery:
        raise RuntimeError("SMTP connection refused to mail.internal:587")


def test_channel_failure_isolation_in_app_delivery_succeeds(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Webhook timeout and email failure do NOT affect in-app delivery."""
    test_jsonl = tmp_path / "alerts.jsonl"
    hub = LiveHub()

    # Webhook channel configured to time out
    async def _mock_timeout(*args: Any, **kwargs: Any) -> Any:
        raise httpx.TimeoutException("Webhook POST timed out after 5.0s")

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_timeout)

    webhook_ch = WebhookChannel(
        webhook_url="https://hooks.example.com/alerts",
        timeout_seconds=0.1,
        max_retries=1,
    )
    email_ch = FailingEmailChannel()
    in_app_ch = InAppChannel(hub=hub, alerts_path=test_jsonl)

    dispatcher = AlertDispatcher(
        channels=[webhook_ch, email_ch, in_app_ch],
        timeout_seconds=0.2,
        max_retries=1,
    )

    alert = _make_alert_record(alert_id="alt-isolated-99")

    async def _run() -> None:
        _sub_id, queue = await hub.subscribe()

        # Dispatch alert across all channels
        res = await dispatcher.dispatch(alert)
        assert res is alert

        # Verify delivery statuses
        deliveries = {d.channel: d for d in alert.delivery}
        assert deliveries["webhook"].status == "FAILED"
        assert deliveries["email"].status == "FAILED"

        # In-app delivery succeeded despite external channel failures
        assert deliveries["in_app"].status == "OK"

        # Live hub received broadcast event
        ev = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert ev["type"] == "alert"
        assert ev["alert"]["alert_id"] == "alt-isolated-99"

        # alerts.jsonl has exactly 1 valid record
        lines = test_jsonl.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        rec = deserialize_alert_jsonl(lines[0])
        assert rec.alert_id == "alt-isolated-99"

    asyncio.run(_run())


# ==============================================================================
# 4. Property-Style Test Over Fixtures
# ==============================================================================


def test_property_matrix_decision_invariants() -> None:
    """Property test verifying decision invariants over multi-dimensional event combinations."""
    anomaly_types = [
        "SIGNAL_DEGRADATION",
        "POOR_RADIO_QUALITY",
        "CELL_EDGE_INSTABILITY",
        "STATISTICAL_ONLY",
        "CELL_RESELECTION",
        "HANDOVER",
    ]
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    persistences = [1, 3, 6, 12]
    rule_flags = [True, False]

    for atype in anomaly_types:
        for sev in severities:
            for pers in persistences:
                for rflag in rule_flags:
                    evt = _make_event(
                        anomaly_type=atype,
                        severity=sev,
                        persistence=pers,
                        rule_evidence=rflag,
                    )
                    decision = decide(evt)

                    # Invariant 1: If transition, must never alert
                    if atype in ("CELL_RESELECTION", "HANDOVER"):
                        assert not decision.alerted
                        assert decision.reason == "Transition only"

                    # Invariant 2: If no rule evidence, must never alert
                    elif not rflag or atype == "STATISTICAL_ONLY":
                        assert not decision.alerted
                        assert "ML-only" in decision.reason

                    # Invariant 3: If alerted, kind must be NEW (with empty prior alerts)
                    elif decision.alerted:
                        assert decision.kind == "NEW"
                        assert decision.reason == "Alert triggered"


def test_policy_edge_cases_and_tracker_helpers() -> None:
    """Exercise fallback branches in policy for full code coverage."""
    # Test has_agent_rule_evidence with dict and object kwargs
    assert not has_agent_rule_evidence({"rule_evidence": False})
    assert has_agent_rule_evidence({"rule_evidence": True})
    assert has_agent_rule_evidence({"evidence": ["rule matched"]})
    assert has_agent_rule_evidence({"policy": {"rule_evidence": True}})
    assert has_agent_rule_evidence({"ml": {"rule_evidence": True}})
    assert has_agent_rule_evidence({"signal_report": {"findings": ["low rsrp"]}})
    assert has_agent_rule_evidence({"cell_report": {"anomalies": ["edge"]}})
    assert has_agent_rule_evidence({"network": {"evidence": ["skew"]}})

    # Test time parsing helper
    assert _parse_alert_time(None) == 0.0
    assert _parse_alert_time(12345.0) == 12345.0
    now_dt = datetime.now(UTC)
    assert _parse_alert_time(now_dt) == now_dt.timestamp()
    assert _parse_alert_time("invalid-date") == 0.0

    # Test delivery check helper
    assert _is_alert_delivered({"delivery": []})
    assert _is_alert_delivered({"delivery": [{"status": "OK"}]})
    assert not _is_alert_delivered({"delivery": [{"status": "FAILED"}]})
    assert _is_alert_delivered({"delivered": True})
    assert not _is_alert_delivered({"delivered": False})
    assert _is_alert_delivered({})

    # Test tracker with custom timestamps and date formats
    tracker = AlertStateTracker(cooldown_seconds=60)
    alt = _make_alert_record("alt-ts-test", created_at=now_dt.isoformat())
    tracker.record(alt)

    alerts = tracker.get_alerts(session_id="test-session-1")
    assert len(alerts) == 1

    alerts_filtered = tracker.get_alerts(
        session_id="other-sess",
        anomaly_type="SIGNAL_DEGRADATION",
    )
    assert len(alerts_filtered) == 0

"""Pure functional policy engine evaluating whether an event qualifies for alerting
(T13-001, T13-002, G6, G21).

Applies deterministic gating rules based on persistence, severity thresholds,
multi-agent evidence requirements, cooldown timers, escalation detection,
and resolution criteria.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from ml.config import (
    ALERT_COOLDOWN_SECONDS,
    ALERT_MIN_PERSISTENCE_SAMPLES,
    ALERT_MIN_SEVERITY,
)
from streaming.schema import AlertDecision, AlertRecord

# Severity ranking for deterministic threshold comparisons
SEVERITY_ORDER: dict[str, int] = {
    "NONE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}

# Non-alerting transition and normal anomaly types (G6, G21)
TRANSITION_TYPES: frozenset[str] = frozenset(
    {
        "NORMAL",
        "CELL_TRANSITION",
        "NETWORK_STATE_TRANSITION",
    }
)


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve field from dictionary or object attribute."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_alert_time(val: Any) -> float:
    """Convert timestamp, ISO string, or datetime to float unix seconds."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, datetime):
        return val.timestamp()
    val_str = str(val).strip()
    try:
        return float(val_str)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(val_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def _is_alert_delivered(alert: Any) -> bool:
    """Check whether an alert record was successfully delivered to at least one channel."""
    delivery = _get_field(alert, "delivery")
    if delivery is not None and isinstance(delivery, (list, tuple)):
        if len(delivery) == 0:
            return True
        return any(_get_field(d, "status") == "OK" for d in delivery)
    delivered = _get_field(alert, "delivered")
    if delivered is not None:
        return bool(delivered)
    return True


class AlertStateTracker:
    """In-memory state tracker for alert cooldowns and active alerts per (session, anomaly_type)."""

    def __init__(self, cooldown_seconds: int = ALERT_COOLDOWN_SECONDS) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._alerts: list[dict[str, Any] | AlertRecord] = []

    def record(self, alert: Any) -> None:
        """Record an emitted alert in history."""
        self._alerts.append(alert)

    def get_alerts(
        self, session_id: str | None = None, anomaly_type: str | None = None
    ) -> list[Any]:
        """Retrieve recorded alerts matching session and anomaly type."""
        res: list[Any] = []
        for a in self._alerts:
            a_sess = _get_field(a, "session_id")
            a_type = _get_field(a, "anomaly_type")
            if session_id and a_sess != session_id:
                continue
            if anomaly_type and a_type != anomaly_type:
                continue
            res.append(a)
        return res


def has_agent_rule_evidence(e_dict: dict[str, Any]) -> bool:
    """Determine whether at least one agent reported corroborated domain rule evidence.

    Inspects explicit policy flags, agent reports (signal, cell, network),
    diagnosis evidence, and top-level evidence lists. Pure function without I/O.
    """
    # 1. Explicit boolean flag
    if "rule_evidence" in e_dict:
        return bool(e_dict["rule_evidence"])
    if isinstance(e_dict.get("policy"), dict) and "rule_evidence" in e_dict["policy"]:
        return bool(e_dict["policy"]["rule_evidence"])
    if isinstance(e_dict.get("ml"), dict) and "rule_evidence" in e_dict["ml"]:
        return bool(e_dict["ml"]["rule_evidence"])

    # 2. Top-level evidence list
    evidence = e_dict.get("evidence")
    if isinstance(evidence, (list, tuple)) and len(evidence) > 0:
        return True

    # 3. Domain agent reports
    for key in (
        "signal_report",
        "cell_report",
        "network_report",
        "signal",
        "cell",
        "network",
    ):
        rep = e_dict.get(key)
        if isinstance(rep, dict):
            if rep.get("findings") or rep.get("anomalies") or rep.get("evidence"):
                return True
            if rep.get("degraded") or rep.get("is_anomaly") or rep.get("has_anomaly"):
                return True

    # 4. Diagnosis agent report
    diag = e_dict.get("diagnosis")
    if isinstance(diag, dict):
        if diag.get("evidence"):
            return True
        cause = str(diag.get("primary_cause", "")).upper()
        if cause and cause not in ("NORMAL", "UNKNOWN", "NONE", ""):
            return True

    return False


def decide(
    event_state: Any,
    history: list[Any] | AlertStateTracker | None = None,
    config: Any | None = None,
    clock: Callable[[], float | datetime] | None = None,
    now: float | datetime | None = None,
) -> AlertDecision:
    """Evaluate whether an event qualifies for an external alert notification (T13-001, T13-002).

    Gating Rules:
    1. Anomaly type not in {NORMAL, STATISTICAL_ONLY, CELL_TRANSITION, NETWORK_STATE_TRANSITION}.
       - STATISTICAL_ONLY -> 'ML-only (no rule evidence)'
       - Transition types -> 'Transition only'
    2. At least one domain agent reported rule evidence.
       - Missing rule evidence -> 'ML-only (no rule evidence)'
    3. Event satisfies persistence >= ALERT_MIN_PERSISTENCE_SAMPLES or
       severity >= ALERT_MIN_SEVERITY.
       - Below both thresholds -> 'Below persistence/severity threshold'
    4. Closed events: emit 'RESOLVED' only if prior NEW/ESCALATION alert was delivered.
    5. Active events: emit 'NEW' on first alert, 'ESCALATION' if severity strictly increases,
       or suppress with 'Cooldown active' if within ALERT_COOLDOWN_SECONDS.

    Args:
        event_state: EventRecord, ScoredSample, or event state dictionary.
        history: Sequence of prior alerts or AlertStateTracker instance.
        config: Optional configuration object overriding default alert thresholds.
        clock: Optional injectable callable returning current timestamp or datetime.
        now: Optional current timestamp or datetime override.

    Returns:
        AlertDecision: Pydantic model with alerted (bool), reason, and kind.
    """
    if isinstance(event_state, BaseModel):
        e_dict = event_state.model_dump(mode="python")
    elif isinstance(event_state, dict):
        e_dict = event_state
    else:
        e_dict = {}

    session_id = str(e_dict.get("session_id") or "default")
    anomaly_type = str(e_dict.get("anomaly_type", "NORMAL")).upper()
    event_id = str(e_dict.get("event_id") or "")
    status = str(e_dict.get("status") or e_dict.get("event_status") or "PROVISIONAL").upper()
    is_closed = status in ("FINAL", "CLOSED") or bool(e_dict.get("is_closed", False))

    cooldown_seconds = getattr(config, "ALERT_COOLDOWN_SECONDS", ALERT_COOLDOWN_SECONDS)

    # Determine current timestamp in unix seconds
    if now is not None:
        curr_time_s = now.timestamp() if isinstance(now, datetime) else float(now)
    elif clock is not None:
        c_val = clock()
        curr_time_s = c_val.timestamp() if isinstance(c_val, datetime) else float(c_val)
    elif "timestamp" in e_dict or "end" in e_dict or "created_at" in e_dict:
        ts_raw = e_dict.get("timestamp") or e_dict.get("end") or e_dict.get("created_at")
        curr_time_s = _parse_alert_time(ts_raw)
    else:
        curr_time_s = datetime.now(UTC).timestamp()

    # Extract prior alerts from history
    if isinstance(history, AlertStateTracker):
        prior_alerts = history.get_alerts(session_id=session_id, anomaly_type=anomaly_type)
        all_event_alerts = (
            [a for a in history.get_alerts() if _get_field(a, "event_id") == event_id]
            if event_id
            else []
        )
    elif isinstance(history, (list, tuple)):
        prior_alerts = [
            a
            for a in history
            if (_get_field(a, "session_id") == session_id or not _get_field(a, "session_id"))
            and str(_get_field(a, "anomaly_type", "")).upper() == anomaly_type
        ]
        all_event_alerts = (
            [a for a in history if _get_field(a, "event_id") == event_id] if event_id else []
        )
    else:
        prior_alerts = []
        all_event_alerts = []

    # CASE A: Event is closed / FINAL -> Check for RESOLVED alert
    if is_closed:
        delivered_alerts = [
            a
            for a in (all_event_alerts or prior_alerts)
            if _get_field(a, "kind") in ("NEW", "ESCALATION") and _is_alert_delivered(a)
        ]
        already_resolved = any(
            _get_field(a, "kind") == "RESOLVED" for a in (all_event_alerts or prior_alerts)
        )
        if delivered_alerts and not already_resolved:
            return AlertDecision(alerted=True, reason="Alert triggered", kind="RESOLVED")
        return AlertDecision(
            alerted=False, reason="Below persistence/severity threshold", kind=None
        )

    # CASE B: Event is active / provisional
    # Rule 1a: Statistical / ML-only flags without rule corroboration never alert
    if anomaly_type == "STATISTICAL_ONLY":
        return AlertDecision(alerted=False, reason="ML-only (no rule evidence)", kind=None)

    # Rule 1b: Normal states and transition-only events never alert (G6, G21)
    if anomaly_type in TRANSITION_TYPES:
        return AlertDecision(alerted=False, reason="Transition only", kind=None)

    # Rule 2: Corroborated domain agent rule evidence required
    if not has_agent_rule_evidence(e_dict):
        return AlertDecision(alerted=False, reason="ML-only (no rule evidence)", kind=None)

    # Rule 3: Must meet minimum persistence OR minimum severity threshold
    min_persistence = getattr(
        config, "ALERT_MIN_PERSISTENCE_SAMPLES", ALERT_MIN_PERSISTENCE_SAMPLES
    )
    min_severity_str = str(getattr(config, "ALERT_MIN_SEVERITY", ALERT_MIN_SEVERITY)).upper()
    min_severity_rank = SEVERITY_ORDER.get(min_severity_str, 2)

    persistence = e_dict.get("persistence")
    if persistence is None:
        persistence = e_dict.get("persistence_samples")
    if persistence is None:
        ml_dict = e_dict.get("ml")
        if isinstance(ml_dict, dict):
            persistence = ml_dict.get("sample_count")
    if persistence is None:
        persistence = 1

    try:
        persistence_val = int(persistence)
    except (ValueError, TypeError):
        persistence_val = 1

    event_severity = str(e_dict.get("severity", "LOW")).upper()
    event_severity_rank = SEVERITY_ORDER.get(event_severity, 1)

    meets_persistence = persistence_val >= min_persistence
    meets_severity = event_severity_rank >= min_severity_rank

    if not (meets_persistence or meets_severity):
        return AlertDecision(
            alerted=False, reason="Below persistence/severity threshold", kind=None
        )

    # Evaluate NEW vs ESCALATION vs COOLDOWN
    prior_emissions = [a for a in prior_alerts if _get_field(a, "kind") in ("NEW", "ESCALATION")]

    if not prior_emissions:
        return AlertDecision(alerted=True, reason="Alert triggered", kind="NEW")

    highest_prior_severity_rank = max(
        SEVERITY_ORDER.get(str(_get_field(a, "severity", "LOW")).upper(), 1)
        for a in prior_emissions
    )

    if event_severity_rank > highest_prior_severity_rank:
        return AlertDecision(alerted=True, reason="Alert triggered", kind="ESCALATION")

    last_alert = prior_emissions[-1]
    last_alert_time_s = _parse_alert_time(
        _get_field(last_alert, "created_at") or _get_field(last_alert, "timestamp")
    )
    elapsed_s = curr_time_s - last_alert_time_s

    if elapsed_s < cooldown_seconds:
        return AlertDecision(alerted=False, reason="Cooldown active", kind=None)

    return AlertDecision(alerted=True, reason="Alert triggered", kind="NEW")

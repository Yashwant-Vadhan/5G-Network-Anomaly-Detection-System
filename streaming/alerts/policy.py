"""Pure functional policy engine evaluating whether an event qualifies for alerting
(T13-001, G6, G21).

Applies deterministic gating rules based on persistence, severity thresholds,
and multi-agent evidence requirements, explicitly suppressing alerts for normal
transitions and ML-only flags without corroborated domain evidence.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ml.config import (
    ALERT_MIN_PERSISTENCE_SAMPLES,
    ALERT_MIN_SEVERITY,
)
from streaming.schema import AlertDecision

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
    history: list[Any] | None = None,
    config: Any | None = None,
) -> AlertDecision:
    """Evaluate whether an event qualifies for an external alert notification (T13-001).

    Gating Rules:
    1. Anomaly type not in {NORMAL, STATISTICAL_ONLY, CELL_TRANSITION, NETWORK_STATE_TRANSITION}.
       - STATISTICAL_ONLY -> 'ML-only (no rule evidence)'
       - Transition types -> 'Transition only'
    2. At least one domain agent reported rule evidence.
       - Missing rule evidence -> 'ML-only (no rule evidence)'
    3. Event satisfies persistence >= ALERT_MIN_PERSISTENCE_SAMPLES or
       severity >= ALERT_MIN_SEVERITY.
       - Below both thresholds -> 'Below persistence/severity threshold'
    4. Passes all gating checks -> 'Alert triggered' (alerted=True).

    Args:
        event_state: EventRecord, ScoredSample, or event state dictionary.
        history: Optional sequence of prior alert records (used for cooldown in T13-002).
        config: Optional configuration object overriding default alert thresholds.

    Returns:
        AlertDecision: Pydantic model with alerted (bool) and reason (AlertDecisionReason).
    """
    if isinstance(event_state, BaseModel):
        e_dict = event_state.model_dump(mode="python")
    elif isinstance(event_state, dict):
        e_dict = event_state
    else:
        e_dict = {}

    anomaly_type = str(e_dict.get("anomaly_type", "NORMAL")).upper()

    # Rule 1a: Statistical / ML-only flags without rule corroboration never alert
    if anomaly_type == "STATISTICAL_ONLY":
        return AlertDecision(alerted=False, reason="ML-only (no rule evidence)")

    # Rule 1b: Normal states and transition-only events never alert (G6, G21)
    if anomaly_type in TRANSITION_TYPES:
        return AlertDecision(alerted=False, reason="Transition only")

    # Rule 2: Corroborated domain agent rule evidence required
    if not has_agent_rule_evidence(e_dict):
        return AlertDecision(alerted=False, reason="ML-only (no rule evidence)")

    # Extract thresholds from config or ml.config defaults
    min_persistence = getattr(
        config, "ALERT_MIN_PERSISTENCE_SAMPLES", ALERT_MIN_PERSISTENCE_SAMPLES
    )
    min_severity_str = str(getattr(config, "ALERT_MIN_SEVERITY", ALERT_MIN_SEVERITY)).upper()
    min_severity_rank = SEVERITY_ORDER.get(min_severity_str, 2)

    # Extract event persistence and severity
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

    # Rule 3: Must meet minimum persistence OR minimum severity threshold
    meets_persistence = persistence_val >= min_persistence
    meets_severity = event_severity_rank >= min_severity_rank

    if not (meets_persistence or meets_severity):
        return AlertDecision(alerted=False, reason="Below persistence/severity threshold")

    # All criteria satisfied
    return AlertDecision(alerted=True, reason="Alert triggered")

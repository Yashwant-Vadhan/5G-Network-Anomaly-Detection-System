"""Recommendation Agent for 5G-NADS (T5-006).

Generates practical, actionable recommendations based on Diagnosis evidence.
"""

from __future__ import annotations

import logging

from agents.contracts import Diagnosis, Recommendation

logger = logging.getLogger(__name__)


def recommend(diagnosis: Diagnosis) -> Recommendation:
    """Generate practical recommendation from Diagnosis report.

    Args:
        diagnosis: Diagnosis contract object.

    Returns:
        Recommendation contract dataclass.
    """
    atype = diagnosis.anomaly_type

    if atype in ("NORMAL", "CELL_TRANSITION"):
        return Recommendation(
            text="Continue standard monitoring. No operator action required.",
            kind="MONITORING",
        )

    if atype == "COMBINED_ANOMALY":
        return Recommendation(
            text=(
                "Flag area for RF coverage audit and inspect"
                " potential handover failure / cell edge degradation."
            ),
            kind="OPERATOR_ACTION",
        )

    if atype in ("SIGNAL_DEGRADATION", "SUDDEN_SIGNAL_DEGRADATION", "PERSISTENT_POOR_QUALITY"):
        return Recommendation(
            text=(
                "Monitor signal metric trend across adjacent"
                " cells and check for physical shielding or interference."
            ),
            kind="MONITORING",
        )

    return Recommendation(
        text="Maintain standard metric telemetry collection.",
        kind="MONITORING",
    )

"""Diagnosis Agent for 5G-NADS (T5-005).

Synthesizes signal, cell, network, and ML anomaly evidence into a cohesive Diagnosis.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.contracts import CellReport, Diagnosis, NetworkReport, SignalReport

logger = logging.getLogger(__name__)


def diagnose(
    signal: SignalReport,
    cell: CellReport,
    network: NetworkReport,
    ml: dict[str, Any],
    anomaly_type: str = "NORMAL",
) -> Diagnosis:
    """Synthesize evidence across reports into a unified Diagnosis contract.

    Args:
        signal: SignalReport object.
        cell: CellReport object.
        network: NetworkReport object.
        ml: Dictionary containing ML detection metadata.
        anomaly_type: Categorical anomaly type.

    Returns:
        Diagnosis contract dataclass.
    """
    evidence = list(signal.evidence) + list(cell.evidence) + list(network.evidence)

    summary = f"Detected {anomaly_type} event."
    if anomaly_type == "NORMAL":
        summary = "Normal network operating conditions."

    confidence_note = (
        "Diagnostic correlation derived deterministically from empirical measurements; "
        "not a confirmed network hardware failure."
    )

    return Diagnosis(
        summary=summary,
        evidence=evidence,
        confidence_note=confidence_note,
        anomaly_type=anomaly_type,
    )

"""Signal Agent for 5G-NADS (T5-002).

Analyzes RSRP, RSRQ, SINR, deltas, and rolling stats within an event window.
Guardrail G14: Only signal reasoning — no cell or network logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agents.contracts import SignalReport

if TYPE_CHECKING:
    from agents.contracts import EventWindow

logger = logging.getLogger(__name__)


def analyze(window: EventWindow) -> SignalReport:
    """Analyze signal conditions within an event window.

    Args:
        window: EventWindow contract object.

    Returns:
        SignalReport contract dataclass.
    """
    df = window.df
    evidence = []

    if df.empty or ("ss_rsrp" not in df.columns and "ss_sinr" not in df.columns):
        return SignalReport(
            signal_condition="unknown",
            evidence=["No signal metrics available in window."],
        )

    rsrp = df["ss_rsrp"].dropna() if "ss_rsrp" in df.columns else []
    sinr = df["ss_sinr"].dropna() if "ss_sinr" in df.columns else []

    if len(rsrp) == 0 and len(sinr) == 0:
        return SignalReport(
            signal_condition="unknown",
            evidence=["All signal metric values are NA in window."],
        )

    # Calculate metrics
    mean_rsrp = float(rsrp.mean()) if len(rsrp) > 0 else -140.0
    mean_sinr = float(sinr.mean()) if len(sinr) > 0 else -20.0

    if len(rsrp) >= 2:
        start_rsrp = float(rsrp.iloc[0])
        end_rsrp = float(rsrp.iloc[-1])
        evidence.append(
            f"SS-RSRP moved from {start_rsrp:.1f} dBm"
            f" to {end_rsrp:.1f} dBm (mean: {mean_rsrp:.1f} dBm)."
        )

    if len(sinr) >= 2:
        start_sinr = float(sinr.iloc[0])
        end_sinr = float(sinr.iloc[-1])
        evidence.append(
            f"SS-SINR moved from {start_sinr:.1f} dB"
            f" to {end_sinr:.1f} dB (mean: {mean_sinr:.1f} dB)."
        )

    # Evaluate condition
    condition = "good"
    if mean_rsrp < -110.0 or mean_sinr < 0.0:
        condition = "degraded"
    elif mean_rsrp < -95.0 or mean_sinr < 10.0:
        condition = "fair"

    return SignalReport(
        signal_condition=condition,
        evidence=evidence,
    )

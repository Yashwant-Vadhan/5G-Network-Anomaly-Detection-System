"""Network-State Agent for 5G-NADS (T5-004).

Analyzes network_type, deployment_mode, display_override, and registration status.
Guardrail G4: NEVER infers SA when deployment_mode is UNKNOWN.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agents.contracts import NetworkReport

if TYPE_CHECKING:
    from agents.contracts import EventWindow

logger = logging.getLogger(__name__)


def analyze(window: EventWindow) -> NetworkReport:
    """Analyze network state and transitions within an event window.

    Args:
        window: EventWindow containing sequential measurements.

    Returns:
        NetworkReport contract dataclass.
    """
    df = window.df
    evidence = []

    if df.empty:
        return NetworkReport(
            network_state="stable",
            deployment_mode="UNKNOWN",
            evidence=["No measurement data in window."],
        )

    # 1. Deployment mode (preserve exact observed value, never upgrade UNKNOWN -> SA)
    observed_modes = (
        df["deployment_mode"].dropna().unique() if "deployment_mode" in df.columns else []
    )
    if len(observed_modes) > 0:
        deployment_mode = str(observed_modes[0])
    else:
        deployment_mode = "UNKNOWN"

    evidence.append(f"Deployment mode reported as {deployment_mode}.")

    # 2. Network type transitions
    network_state = "stable"
    if "network_type" in df.columns:
        types = df["network_type"].dropna().tolist()
        if len(set(types)) > 1:
            network_state = "transitioning"
            unique_types = " -> ".join(dict.fromkeys(types).keys())
            evidence.append(f"Network type transition observed: {unique_types}.")

    # 3. Registration status
    if "registered" in df.columns:
        unregistered_count = int((df["registered"] == False).sum())  # noqa: E712
        if unregistered_count > 0:
            evidence.append(f"Device unregistered in {unregistered_count} sample(s).")
            if network_state == "stable":
                network_state = "unregistered"

    return NetworkReport(
        network_state=network_state,
        deployment_mode=deployment_mode,
        evidence=evidence,
    )

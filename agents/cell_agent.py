"""Cell Agent for 5G-NADS (T5-003).

Analyzes PCI and NCI cell transitions within an event window.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agents.contracts import CellReport

if TYPE_CHECKING:
    from agents.contracts import EventWindow

logger = logging.getLogger(__name__)


def analyze(window: EventWindow) -> CellReport:
    """Analyze cell changes and sequences within an event window.

    Args:
        window: EventWindow contract object.

    Returns:
        CellReport contract dataclass.
    """
    df = window.df
    evidence = []

    if df.empty or "pci" not in df.columns:
        return CellReport(
            cell_event="NONE",
            evidence=["No cell identifier data in window."],
        )

    pcis = df["pci"].dropna().tolist()
    unique_pcis = list(dict.fromkeys(pcis))

    if len(unique_pcis) <= 1:
        return CellReport(
            cell_event="NONE",
            evidence=[
                f"PCI remained constant at {unique_pcis[0]}"
                if unique_pcis
                else "No valid PCI observed."
            ],
        )

    # Detect cell change / repeated change
    if len(unique_pcis) >= 3 and pcis[0] == pcis[-1] and pcis[0] != pcis[1]:
        event_type = "REPEATED_CELL_CHANGE"
        evidence.append(f"Repeated ping-pong cell change observed between PCIs {unique_pcis}.")
    else:
        event_type = "CELL_CHANGE"
        evidence.append(f"Cell transition observed from PCI {unique_pcis[0]} to {unique_pcis[-1]}.")

    return CellReport(
        cell_event=event_type,
        evidence=evidence,
    )

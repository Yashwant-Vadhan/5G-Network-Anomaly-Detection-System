"""Precomputed cell and network transitions helper (T16-002, Contract C11).

Extracts and precomputes Physical Cell ID (PCI) and Network Type transition events
from measurement and anomaly-scored datasets.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def compute_transitions(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect cell (PCI) and network type transitions within sessions.

    Migrated from dashboard/pages/3_Cells_And_Network.py L42-78 into a pure,
    reusable, tested helper per T16-002 and Contract C11.

    Args:
        df: DataFrame containing at least 'timestamp' and optionally 'pci',
            'network_type', 'session_id', 'device'.

    Returns:
        List of transition event dictionaries matching Contract C11:
        [
            {
                "ts": "...",
                "session_id": "...",
                "type": "PCI" | "NETWORK_TYPE",
                "from": "...",
                "to": "...",
                "device": "...",
            },
            ...
        ]
    """
    if df is None or df.empty:
        return []

    transitions: list[dict[str, Any]] = []

    # If session_id is available, group by session to prevent cross-session jumps
    has_session = "session_id" in df.columns
    groups = (
        [(session_id, group) for session_id, group in df.groupby("session_id", sort=False)]
        if has_session
        else [(None, df)]
    )

    for session_id, session_df in groups:
        if len(session_df) < 2:
            continue

        reset_df = session_df.reset_index(drop=True)
        session_str = (
            str(session_id) if session_id is not None else str(reset_df.get("session_id", ["—"])[0])
        )

        # 1. PCI transitions
        if "pci" in reset_df.columns:
            for i in range(1, len(reset_df)):
                prev_pci = reset_df.loc[i - 1, "pci"]
                curr_pci = reset_df.loc[i, "pci"]
                if pd.notna(prev_pci) and pd.notna(curr_pci) and prev_pci != curr_pci:
                    row = reset_df.iloc[i]
                    transitions.append(
                        {
                            "ts": str(row["timestamp"]),
                            "session_id": str(row.get("session_id", session_str)),
                            "type": "PCI",
                            "from": str(prev_pci),
                            "to": str(curr_pci),
                            "device": str(row.get("device", "—")),
                        }
                    )

        # 2. Network Type transitions
        if "network_type" in reset_df.columns:
            for i in range(1, len(reset_df)):
                prev_net = reset_df.loc[i - 1, "network_type"]
                curr_net = reset_df.loc[i, "network_type"]
                if pd.notna(prev_net) and pd.notna(curr_net) and prev_net != curr_net:
                    row = reset_df.iloc[i]
                    transitions.append(
                        {
                            "ts": str(row["timestamp"]),
                            "session_id": str(row.get("session_id", session_str)),
                            "type": "NETWORK_TYPE",
                            "from": str(prev_net),
                            "to": str(curr_net),
                            "device": str(row.get("device", "—")),
                        }
                    )

    # Sort transitions by timestamp to ensure deterministic ordering
    transitions.sort(key=lambda t: t["ts"])
    return transitions

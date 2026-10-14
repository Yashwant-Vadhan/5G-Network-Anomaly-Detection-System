"""Unit tests for cell and network transition detector (T16-002)."""

from __future__ import annotations

import pandas as pd

from ml.transitions import compute_transitions


def test_transitions_empty_and_single_row():
    """Empty or single-row dataframes yield no transitions."""
    assert compute_transitions(pd.DataFrame()) == []
    df_single = pd.DataFrame(
        [{"timestamp": "2026-10-01 10:00:00", "pci": 100, "network_type": "5G NR"}]
    )
    assert compute_transitions(df_single) == []


def test_transitions_negative_case_no_change():
    """Negative case: No change in PCI or network_type produces zero transition events."""
    data = [
        {
            "timestamp": f"2026-10-01 10:00:0{i}",
            "pci": 336,
            "network_type": "5G NR",
            "session_id": "s1",
        }
        for i in range(5)
    ]
    df = pd.DataFrame(data)
    transitions = compute_transitions(df)
    assert transitions == []


def test_transitions_pci_change():
    """Changing PCI within a session triggers a PCI transition."""
    df = pd.DataFrame(
        [
            {
                "timestamp": "2026-10-01 10:00:00",
                "pci": 336,
                "network_type": "5G NR",
                "session_id": "s1",
            },
            {
                "timestamp": "2026-10-01 10:00:01",
                "pci": 412,
                "network_type": "5G NR",
                "session_id": "s1",
            },
            {
                "timestamp": "2026-10-01 10:00:02",
                "pci": 412,
                "network_type": "5G NR",
                "session_id": "s1",
            },
        ]
    )
    transitions = compute_transitions(df)
    assert len(transitions) == 1
    t = transitions[0]
    assert t["type"] == "PCI"
    assert t["from"] == "336"
    assert t["to"] == "412"
    assert t["session_id"] == "s1"
    assert t["ts"] == "2026-10-01 10:00:01"


def test_transitions_network_type_change():
    """Changing network_type within a session triggers a NETWORK_TYPE transition."""
    df = pd.DataFrame(
        [
            {
                "timestamp": "2026-10-01 10:00:00",
                "pci": 336,
                "network_type": "LTE",
                "session_id": "s1",
            },
            {
                "timestamp": "2026-10-01 10:00:01",
                "pci": 336,
                "network_type": "5G NR",
                "session_id": "s1",
            },
        ]
    )
    transitions = compute_transitions(df)
    assert len(transitions) == 1
    t = transitions[0]
    assert t["type"] == "NETWORK_TYPE"
    assert t["from"] == "LTE"
    assert t["to"] == "5G NR"
    assert t["session_id"] == "s1"


def test_transitions_session_boundary_isolation():
    """Changes across session boundaries do not trigger false intra-session transitions."""
    df = pd.DataFrame(
        [
            {
                "timestamp": "2026-10-01 10:00:00",
                "pci": 100,
                "network_type": "5G NR",
                "session_id": "s1",
            },
            {
                "timestamp": "2026-10-01 10:00:01",
                "pci": 100,
                "network_type": "5G NR",
                "session_id": "s1",
            },
            # Session s2 starts with a different PCI, but within s2 it is constant
            {
                "timestamp": "2026-10-01 11:00:00",
                "pci": 200,
                "network_type": "LTE",
                "session_id": "s2",
            },
            {
                "timestamp": "2026-10-01 11:00:01",
                "pci": 200,
                "network_type": "LTE",
                "session_id": "s2",
            },
        ]
    )
    transitions = compute_transitions(df)
    assert transitions == []


def test_transitions_nan_handling():
    """Missing (NaN) values do not trigger valid transitions."""
    df = pd.DataFrame(
        [
            {
                "timestamp": "2026-10-01 10:00:00",
                "pci": 100,
                "network_type": "5G NR",
                "session_id": "s1",
            },
            {
                "timestamp": "2026-10-01 10:00:01",
                "pci": None,
                "network_type": None,
                "session_id": "s1",
            },
            {
                "timestamp": "2026-10-01 10:00:02",
                "pci": 100,
                "network_type": "5G NR",
                "session_id": "s1",
            },
        ]
    )
    transitions = compute_transitions(df)
    assert transitions == []

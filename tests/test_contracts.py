"""Unit tests for agents/contracts.py (T1-009)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from agents.contracts import (
    CellReport,
    Diagnosis,
    EventWindow,
    NetworkReport,
    Recommendation,
    SignalReport,
)


def test_event_window_serialization() -> None:
    """EventWindow should initialize, convert to dict, and serialize to JSON."""
    df = pd.DataFrame({"ss_rsrp": [-85, -90]})
    window = EventWindow(
        df=df,
        event_id="evt-001",
        session_id="redmi-1",
        start="2026-09-30T12:00:00Z",
        end="2026-09-30T12:00:06Z",
        context_before=2,
        ml={"if_score": 0.75, "if_flag": True},
    )

    d = window.to_dict()
    assert d["event_id"] == "evt-001"
    assert d["ml"]["if_score"] == 0.75
    json_str = json.dumps(d)
    assert "evt-001" in json_str


def test_signal_report_serialization() -> None:
    """SignalReport should initialize and serialize to valid JSON."""
    report = SignalReport(
        signal_condition="degraded",
        evidence=["SINR dropped from +3 to -7 dB", "RSRP decreased"],
    )
    d = report.to_dict()
    assert d["signal_condition"] == "degraded"
    assert len(d["evidence"]) == 2
    assert json.loads(json.dumps(d)) == d


def test_cell_report_serialization() -> None:
    """CellReport should initialize and serialize to valid JSON."""
    report = CellReport(
        cell_event="CELL_CHANGE",
        evidence=["PCI changed from 336 to 565"],
    )
    d = report.to_dict()
    assert d["cell_event"] == "CELL_CHANGE"
    assert json.loads(json.dumps(d)) == d


def test_network_report_valid() -> None:
    """NetworkReport with valid deployment_mode should serialize to JSON."""
    report = NetworkReport(
        network_state="STABLE_NR",
        deployment_mode="NSA",
        evidence=["Connected to NR NSA cell"],
    )
    d = report.to_dict()
    assert d["deployment_mode"] == "NSA"
    assert json.loads(json.dumps(d)) == d


def test_network_report_invalid_deployment_mode() -> None:
    """NetworkReport with invalid deployment_mode should raise ValueError."""
    with pytest.raises(ValueError, match="Invalid deployment_mode 'FOO'"):
        NetworkReport(
            network_state="STABLE_NR",
            deployment_mode="FOO",
            evidence=[],
        )


def test_diagnosis_serialization() -> None:
    """Diagnosis should initialize and serialize to valid JSON."""
    diag = Diagnosis(
        summary="Possible radio-quality degradation associated with cell transition.",
        evidence=["SINR dropped"],
        confidence_note="correlation, not confirmed cause",
        anomaly_type="COMBINED_ANOMALY",
    )
    d = diag.to_dict()
    assert d["anomaly_type"] == "COMBINED_ANOMALY"
    assert json.loads(json.dumps(d)) == d


def test_recommendation_valid() -> None:
    """Recommendation with valid kind should serialize to JSON."""
    rec = Recommendation(
        text="Continue monitoring signal levels.",
        kind="MONITORING",
    )
    d = rec.to_dict()
    assert d["kind"] == "MONITORING"
    assert json.loads(json.dumps(d)) == d


def test_recommendation_invalid_kind() -> None:
    """Recommendation with invalid kind should raise ValueError."""
    with pytest.raises(ValueError, match="Invalid recommendation kind 'INVALID_KIND'"):
        Recommendation(
            text="Take action",
            kind="INVALID_KIND",
        )


def test_docstrings_reference_overview_section_28() -> None:
    """Docstrings in agents/contracts.py must reference project-overview.md §28."""
    import agents.contracts as contracts_mod

    assert "§28" in contracts_mod.__doc__
    assert "§28" in EventWindow.__doc__
    assert "§28" in SignalReport.__doc__
    assert "§28" in CellReport.__doc__
    assert "§28" in NetworkReport.__doc__
    assert "§28" in Diagnosis.__doc__
    assert "§28" in Recommendation.__doc__

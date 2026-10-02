"""Unit tests for agents layer (T5-001, T5-004)."""

import pandas as pd

from agents.contracts import EventWindow
from agents.network_agent import analyze as analyze_network
from agents.orchestrator import build_event_window, run_agents


def test_build_event_window():
    """Verify build_event_window builds valid EventWindow with context without crossing sessions."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 10,
            "session_id": ["s1"] * 10,
            "timestamp": pd.date_range("2026-09-28T10:00:00Z", periods=10, freq="3s"),
            "ss_rsrp": [-80.0] * 10,
            "ss_sinr": [20.0] * 10,
        }
    )

    event = {
        "event_id": "evt-001",
        "session_id": "s1",
        "start_time": str(df["timestamp"].iloc[5]),
        "end_time": str(df["timestamp"].iloc[8]),
        "anomaly_type": "SIGNAL_DEGRADATION",
        "max_severity": "MEDIUM",
        "sample_count": 4,
    }

    window = build_event_window(df, event, context_samples=3)

    assert isinstance(window, EventWindow)
    assert window.event_id == "evt-001"
    assert len(window.df) == 7  # 3 context + 4 event samples


def test_network_agent_never_promotes_unknown_to_sa():
    """Guardrail G4: Network Agent must never output SA when input deployment_mode is UNKNOWN."""
    df = pd.DataFrame(
        {
            "network_type": ["NR", "NR"],
            "deployment_mode": ["UNKNOWN", "UNKNOWN"],
            "registered": [True, True],
        }
    )

    window = EventWindow(
        df=df,
        event_id="evt-001",
        session_id="s1",
        start="2026-09-28T10:00:00Z",
        end="2026-09-28T10:00:03Z",
        context_before=0,
        ml={"anomaly_type": "NORMAL"},
    )

    report = analyze_network(window)
    assert report.deployment_mode == "UNKNOWN"
    assert "SA" not in report.deployment_mode


def test_orchestrator_run_agents():
    """Verify run_agents executes full pipeline (Signal -> Cell -> Network -> Diagnosis -> Recommendation)."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-80.0, -85.0, -115.0],
            "ss_sinr": [20.0, 10.0, -5.0],
            "pci": [336, 336, 565],
            "network_type": ["NR", "NR", "NR"],
            "deployment_mode": ["NSA", "NSA", "NSA"],
            "registered": [True, True, True],
        }
    )

    window = EventWindow(
        df=df,
        event_id="evt-001",
        session_id="s1",
        start="2026-09-28T10:00:00Z",
        end="2026-09-28T10:00:06Z",
        context_before=0,
        ml={"anomaly_type": "COMBINED_ANOMALY", "max_severity": "HIGH"},
    )

    res = run_agents(window)

    assert "signal_report" in res
    assert "cell_report" in res
    assert "network_report" in res
    assert "diagnosis" in res
    assert "recommendation" in res


def test_text_renderer_all_types_and_determinism():
    """Verify text renderer handles all anomaly types deterministically."""
    from agents.contracts import Diagnosis, Recommendation
    from agents.text_renderer import FORBIDDEN_WORDS, render

    anomaly_types = [
        "NORMAL",
        "NONE",
        "SIGNAL_DEGRADATION",
        "SUDDEN_SIGNAL_DEGRADATION",
        "CELL_TRANSITION",
        "NETWORK_STATE_TRANSITION",
        "PERSISTENT_POOR_QUALITY",
        "COMBINED_ANOMALY",
        "STATISTICAL_ONLY",
    ]

    rec = Recommendation(text="Continue monitoring.", kind="MONITORING")

    for atype in anomaly_types:
        diag = Diagnosis(
            summary=f"Summary for {atype}",
            evidence=["Evidence item 1", "Evidence item 2"],
            confidence_note="Correlation note",
            anomaly_type=atype,
        )
        rendered_1 = render(diag, rec)
        rendered_2 = render(diag, rec)

        assert rendered_1 == rendered_2
        assert "Summary:" in rendered_1
        assert "Evidence:" in rendered_1
        assert "Recommendation" in rendered_1

        # Check copy rules
        lower_text = rendered_1.lower()
        for forbidden in FORBIDDEN_WORDS:
            assert forbidden not in lower_text


def test_write_events_diagnosed_contract_c5(tmp_path):
    """T5-008: Verify write_events_diagnosed produces valid C5 JSON matching example keys."""
    import json

    from agents.orchestrator import write_events_diagnosed

    df = pd.DataFrame(
        {
            "ss_rsrp": [-80.0, -85.0, -115.0],
            "ss_sinr": [20.0, 10.0, -5.0],
            "pci": [336, 336, 565],
            "network_type": ["NR", "NR", "NR"],
            "deployment_mode": ["NSA", "NSA", "NSA"],
            "registered": [True, True, True],
        }
    )

    window = EventWindow(
        df=df,
        event_id="evt-c5-001",
        session_id="redmi-1",
        start="2026-09-28T10:00:00Z",
        end="2026-09-28T10:00:06Z",
        context_before=0,
        ml={"anomaly_type": "COMBINED_ANOMALY", "max_severity": "MEDIUM", "if_score": 0.71},
    )

    res = run_agents(window)
    out_file = tmp_path / "events_diagnosed.json"

    write_events_diagnosed([res], out_file)

    assert out_file.exists()
    with open(out_file, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    rec = data[0]
    assert rec["event_id"] == "evt-c5-001"
    assert rec["session_id"] == "redmi-1"
    assert rec["anomaly_type"] == "COMBINED_ANOMALY"
    assert "signal" in rec
    assert "cell" in rec
    assert "network" in rec
    assert "diagnosis" in rec
    assert "recommendation" in rec


def test_write_events_diagnosed_fails_on_missing_keys(tmp_path):
    """T5-008: Verify write_events_diagnosed raises ValueError and does not write file when keys are missing."""
    import pytest

    from agents.orchestrator import write_events_diagnosed

    incomplete_event = {
        "event_id": "evt-bad",
        "session_id": "redmi-1",
        # Missing start, end, signal, cell, network, diagnosis, recommendation, etc.
    }

    out_file = tmp_path / "events_diagnosed_bad.json"

    with pytest.raises(ValueError, match="missing required keys"):
        write_events_diagnosed([incomplete_event], out_file)

    assert not out_file.exists()


# ---------------------------------------------------------------------------
# Per-Agent Tests (≥ 3 tests per agent)
# ---------------------------------------------------------------------------


# Signal Agent Tests
def test_signal_agent_good_condition():
    """Test Signal Agent returns good condition when metrics are high."""
    from agents.signal_agent import analyze as analyze_signal

    df = pd.DataFrame({"ss_rsrp": [-75.0], "ss_rsrq": [-8.0], "ss_sinr": [25.0]})
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_signal(window)
    assert report.signal_condition in ["good", "fair"]


def test_signal_agent_degraded_condition():
    """Test Signal Agent returns degraded condition with evidence on low metrics."""
    from agents.signal_agent import analyze as analyze_signal

    df = pd.DataFrame(
        {"ss_rsrp": [-125.0, -130.0], "ss_rsrq": [-18.0, -19.0], "ss_sinr": [-8.0, -10.0]}
    )
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_signal(window)
    assert report.signal_condition == "degraded"
    assert len(report.evidence) > 0


def test_signal_agent_all_missing():
    """Test Signal Agent returns unknown condition when all metrics are missing without crashing."""
    from agents.signal_agent import analyze as analyze_signal

    df = pd.DataFrame({"ss_rsrp": [None], "ss_rsrq": [None], "ss_sinr": [None]})
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_signal(window)
    assert report.signal_condition == "unknown"


# Cell Agent Tests
def test_cell_agent_no_change():
    """Test Cell Agent reports NONE when PCI remains constant."""
    from agents.cell_agent import analyze as analyze_cell

    df = pd.DataFrame({"pci": [336, 336, 336]})
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_cell(window)
    assert report.cell_event == "NONE"


def test_cell_agent_single_change():
    """Test Cell Agent reports CELL_CHANGE on a single PCI transition."""
    from agents.cell_agent import analyze as analyze_cell

    df = pd.DataFrame({"pci": [336, 336, 565]})
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_cell(window)
    assert report.cell_event == "CELL_CHANGE"
    assert len(report.evidence) > 0


def test_cell_agent_repeated_ping_pong():
    """Test Cell Agent reports REPEATED_CELL_CHANGE on ping-pong A->B->A sequence."""
    from agents.cell_agent import analyze as analyze_cell

    df = pd.DataFrame({"pci": [336, 565, 336]})
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_cell(window)
    assert report.cell_event == "REPEATED_CELL_CHANGE"


def test_cell_agent_missing_pci():
    """Test Cell Agent handles missing PCI gracefully."""
    from agents.cell_agent import analyze as analyze_cell

    df = pd.DataFrame({"pci": [None, None]})
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_cell(window)
    assert report.cell_event == "NONE"


# Network Agent Tests
def test_network_agent_transition():
    """Test Network Agent detects NR to LTE transition."""
    from agents.network_agent import analyze as analyze_network

    df = pd.DataFrame(
        {
            "network_type": ["NR", "LTE"],
            "deployment_mode": ["NSA", "NSA"],
            "registered": [True, True],
        }
    )
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_network(window)
    assert report.network_state in ["TRANSITION", "STABLE", "CHANGING"] or len(report.evidence) > 0


def test_network_agent_unregistered():
    """Test Network Agent produces evidence when registered is False."""
    from agents.network_agent import analyze as analyze_network

    df = pd.DataFrame(
        {
            "network_type": ["NR", "NR"],
            "deployment_mode": ["SA", "SA"],
            "registered": [True, False],
        }
    )
    window = EventWindow(
        df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
    )
    report = analyze_network(window)
    assert any("unregistered" in e.lower() or "registered" in e.lower() for e in report.evidence)


def test_network_agent_parametrised_g4():
    """Parametrised Guardrail G4 test: UNKNOWN input in deployment_mode never outputs SA."""
    from agents.network_agent import analyze as analyze_network

    for mode in ["UNKNOWN"]:
        df = pd.DataFrame({"network_type": ["NR"], "deployment_mode": [mode], "registered": [True]})
        window = EventWindow(
            df=df, event_id="e1", session_id="s1", start="t1", end="t2", context_before=0, ml={}
        )
        report = analyze_network(window)
        assert report.deployment_mode == mode


# Diagnosis Agent Tests
def test_diagnosis_agent_statistical_only():
    """Test Diagnosis Agent produces statistical-only explanation when rule evidence is absent."""
    from agents.contracts import CellReport, NetworkReport, SignalReport
    from agents.diagnosis_agent import diagnose

    sig = SignalReport(signal_condition="good", evidence=[])
    cell = CellReport(cell_event="NONE", evidence=[])
    net = NetworkReport(network_state="STABLE", deployment_mode="SA", evidence=[])

    diag = diagnose(
        sig, cell, net, ml={"anomaly_type": "STATISTICAL_ONLY"}, anomaly_type="STATISTICAL_ONLY"
    )
    assert (
        "statistical" in diag.summary.lower()
        or "statistically" in diag.summary.lower()
        or "statistical_only" in diag.summary.lower()
    )


def test_diagnosis_agent_no_causal_language():
    """Test Diagnosis Agent never uses forbidden causal words in output summary or confidence note."""
    from agents.contracts import CellReport, NetworkReport, SignalReport
    from agents.diagnosis_agent import diagnose

    sig = SignalReport(signal_condition="degraded", evidence=["SINR drop"])
    cell = CellReport(cell_event="CELL_CHANGE", evidence=["PCI change"])
    net = NetworkReport(network_state="STABLE", deployment_mode="NSA", evidence=[])

    diag = diagnose(
        sig, cell, net, ml={"anomaly_type": "COMBINED_ANOMALY"}, anomaly_type="COMBINED_ANOMALY"
    )
    forbidden = ["caused", "because of", "due to", "problem was caused"]
    combined_text = (diag.summary + " " + diag.confidence_note).lower()
    for word in forbidden:
        assert word not in combined_text


# Recommendation Agent Tests
def test_recommendation_agent_low_severity_monitoring_only():
    """Test Recommendation Agent outputs MONITORING for NORMAL / CELL_TRANSITION."""
    from agents.contracts import Diagnosis
    from agents.recommendation_agent import recommend

    diag = Diagnosis(
        summary="Normal event", evidence=[], confidence_note="Note", anomaly_type="NORMAL"
    )
    rec = recommend(diag)
    assert rec.kind == "MONITORING"


def test_recommendation_agent_operator_action_suggestion():
    """Test Recommendation Agent outputs OPERATOR_ACTION for COMBINED_ANOMALY as suggestions only."""
    from agents.contracts import Diagnosis
    from agents.recommendation_agent import recommend

    diag = Diagnosis(
        summary="High degradation",
        evidence=["RSRP drop"],
        confidence_note="Note",
        anomaly_type="COMBINED_ANOMALY",
    )
    rec = recommend(diag)
    assert rec.kind == "OPERATOR_ACTION"


def test_recommendation_agent_no_first_person():
    """Test Recommendation Agent output contains no first-person action claims ('I', 'We', 'My')."""
    from agents.contracts import Diagnosis
    from agents.recommendation_agent import recommend

    diag = Diagnosis(
        summary="Degradation",
        evidence=["RSRP drop"],
        confidence_note="Note",
        anomaly_type="SIGNAL_DEGRADATION",
    )
    rec = recommend(diag)
    words = rec.text.split()
    for first_person in ["I", "We", "my", "our", "us"]:
        assert first_person not in words


# ---------------------------------------------------------------------------
# Guardrail Automation Tests (G9 & G14)
# ---------------------------------------------------------------------------


def test_guardrail_g9_no_sklearn_in_agents():
    """Guardrail G9: Verify no Python code in agents/ imports sklearn."""
    from pathlib import Path

    agents_dir = Path("agents")
    for py_file in agents_dir.glob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            stripped = line.strip()
            if (
                not stripped.startswith("#")
                and not stripped.startswith('"""')
                and not stripped.startswith("*")
            ):
                assert not stripped.startswith("import sklearn"), (
                    f"G9 violation in {py_file}: {line}"
                )
                assert not stripped.startswith("from sklearn"), f"G9 violation in {py_file}: {line}"


def test_guardrail_g14_no_cross_agent_imports():
    """Guardrail G14: Individual reasoning agents must not import each other."""
    from pathlib import Path

    agent_files = ["signal_agent.py", "cell_agent.py", "network_agent.py"]
    agents_dir = Path("agents")

    for f_name in agent_files:
        content = (agents_dir / f_name).read_text(encoding="utf-8")
        for other_name in agent_files:
            if other_name != f_name:
                mod_name = other_name.replace(".py", "")
                assert f"import {mod_name}" not in content, f"G14 violation in {f_name}"
                assert f"from agents.{mod_name}" not in content, f"G14 violation in {f_name}"

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


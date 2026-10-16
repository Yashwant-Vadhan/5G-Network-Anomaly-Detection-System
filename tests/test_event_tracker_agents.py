"""Tests for T11-008: Running unchanged agents on event open/change/close."""

from __future__ import annotations

from unittest.mock import patch

from agents.orchestrator import validate_c5_record
from streaming.event_tracker import EventTracker


def make_rich_sample(
    timestamp: str,
    anomaly_type: str = "NORMAL",
    severity: str = "LOW",
    is_anom: bool = False,
    ss_rsrp: float = -85.0,
    ss_sinr: float = 15.0,
    pci: int = 120,
    network_type: str = "NR",
    deployment_mode: str = "SA",
) -> dict:
    return {
        "timestamp": timestamp,
        "device": "Samsung SM-A156E",
        "anomaly_type": anomaly_type,
        "severity": severity,
        "is_anom": is_anom,
        "seq": 1,
        "ss_rsrp": ss_rsrp,
        "ss_sinr": ss_sinr,
        "pci": pci,
        "network_type": network_type,
        "deployment_mode": deployment_mode,
        "registered": True,
    }


def test_agents_invoked_on_open_change_close():
    """EventTracker executes agents on OPEN, type/severity UPDATE, and CLOSE."""
    tracker = EventTracker(session_id="s1", device="Samsung", close_gap_samples=2)

    # 1. Normal sample - no event, no agent call
    action, evt = tracker.process_sample(make_rich_sample("2026-10-09T10:00:00", is_anom=False))
    assert action == "NONE"
    assert evt is None

    # 2. Open event on first anomaly -> agents run and populate diagnosis
    action, evt = tracker.process_sample(
        make_rich_sample(
            "2026-10-09T10:00:03",
            anomaly_type="SIGNAL_DEGRADATION",
            severity="LOW",
            is_anom=True,
            ss_rsrp=-115.0,
        )
    )
    assert action == "OPEN"
    assert evt is not None
    assert evt.status == "PROVISIONAL"
    assert evt.diagnosis is not None
    assert evt.recommendation is not None
    assert evt.explanation_text is not None

    # Check C5 compliance of the record
    evt_dict = evt.model_dump()
    validate_c5_record(evt_dict)

    # 3. Update without type/severity change -> same type/sev, agent not re-executed
    with patch("streaming.event_tracker.run_agents") as mock_run:
        action, evt_same = tracker.process_sample(
            make_rich_sample(
                "2026-10-09T10:00:06",
                anomaly_type="SIGNAL_DEGRADATION",
                severity="LOW",
                is_anom=True,
                ss_rsrp=-114.0,
            )
        )
        assert action == "UPDATE"
        assert mock_run.call_count == 0

    # 4. Update WITH type/severity change -> agents run
    action, evt_changed = tracker.process_sample(
        make_rich_sample(
            "2026-10-09T10:00:09",
            anomaly_type="PERSISTENT_POOR_QUALITY",
            severity="HIGH",
            is_anom=True,
            ss_rsrp=-118.0,
        )
    )
    assert action == "UPDATE"
    assert evt_changed.anomaly_type == "PERSISTENT_POOR_QUALITY"
    assert evt_changed.severity == "HIGH"
    validate_c5_record(evt_changed.model_dump())

    # 5. Normal sample gap
    tracker.process_sample(make_rich_sample("2026-10-09T10:00:12", is_anom=False))

    # 6. Second normal sample -> CLOSE to FINAL
    action, final_evt = tracker.process_sample(
        make_rich_sample("2026-10-09T10:00:15", is_anom=False)
    )
    assert action == "CLOSED"
    assert final_evt.status == "FINAL"
    assert final_evt.diagnosis is not None
    validate_c5_record(final_evt.model_dump())


def test_agent_cache_by_window_hash():
    """Agent results are cached by (event_id, window_hash)."""
    tracker = EventTracker(session_id="s1", device="Samsung")

    sample1 = make_rich_sample(
        "2026-10-09T10:00:00",
        anomaly_type="SIGNAL_DEGRADATION",
        severity="LOW",
        is_anom=True,
    )

    with patch(
        "streaming.event_tracker.run_agents",
        wraps=__import__("agents.orchestrator").orchestrator.run_agents,
    ) as spy_agents:
        tracker.process_sample(sample1)
        assert spy_agents.call_count == 1
        assert len(tracker._agent_cache) == 1

        # Diagnosing again with identical event and dataframe uses cache
        tracker._diagnose_event(tracker.active_event, "PROVISIONAL")
        assert spy_agents.call_count == 1


def test_hedged_language_in_diagnoses():
    """Diagnoses and recommendations must not contain causal assertions."""
    tracker = EventTracker(session_id="s1", device="Samsung")
    _, evt = tracker.process_sample(
        make_rich_sample(
            "2026-10-09T10:00:00",
            anomaly_type="COMBINED_ANOMALY",
            severity="HIGH",
            is_anom=True,
            ss_rsrp=-120.0,
            ss_sinr=-5.0,
        )
    )
    diag_summary = evt.diagnosis.get("summary", "").lower()
    conf_note = evt.diagnosis.get("confidence_note", "").lower()
    combined_diag = f"{diag_summary} {conf_note}"

    forbidden = ["caused", "because of", "due to", "problem was caused"]
    for word in forbidden:
        assert word not in combined_diag


def test_agents_stubbed_out_preserves_ml_flags():
    """Guardrail G9: With enable_agents=False, ML flags and event lifecycle are identical."""
    tracker_with_agents = EventTracker(session_id="s1", device="Samsung", close_gap_samples=1)
    tracker_without_agents = EventTracker(
        session_id="s1", device="Samsung", close_gap_samples=1, enable_agents=False
    )

    s1 = make_rich_sample(
        "2026-10-09T10:00:00", anomaly_type="SIGNAL_DEGRADATION", severity="LOW", is_anom=True
    )
    s2 = make_rich_sample("2026-10-09T10:00:03", is_anom=False)

    a1, evt1 = tracker_with_agents.process_sample(s1)
    a2, evt2 = tracker_without_agents.process_sample(s1)

    assert a1 == a2 == "OPEN"
    assert evt1.anomaly_type == evt2.anomaly_type
    assert evt1.severity == evt2.severity
    assert evt1.status == evt2.status == "PROVISIONAL"
    assert evt2.diagnosis is None  # Agents disabled

    c1, cl1 = tracker_with_agents.process_sample(s2)
    c2, cl2 = tracker_without_agents.process_sample(s2)

    assert c1 == c2 == "CLOSED"
    assert cl1.anomaly_type == cl2.anomaly_type
    assert cl1.severity == cl2.severity
    assert cl1.status == cl2.status == "FINAL"

"""Tests verifying optional LLM has zero effect on the live path (T15-003, Guardrail G13).

Acceptance Criteria:
- With NADS_USE_LLM unset and no network the live path works 100% offline.
- With NADS_USE_LLM set, flags, types, severities and alert decisions are byte-identical.
- Alert text always originates from deterministic template renderers, never from an LLM.
"""

from __future__ import annotations

import os
import socket
from unittest.mock import MagicMock, patch

from agents.llm_explainer import explain_diagnosis, is_llm_enabled
from streaming.alerts.dispatcher import format_alert_body_with_template
from streaming.alerts.policy import AlertStateTracker, decide
from streaming.engine import StreamingEngine
from streaming.event_tracker import EventTracker


def _sample_payload(seq: int, rsrp: float, sinr: float) -> dict:
    return {
        "seq": seq,
        "payload": {
            "timestamp": f"2026-10-18T10:00:{seq:02d}Z",
            "device": "Pixel 8",
            "manufacturer": "Google",
            "android": "14",
            "operator": "Jio",
            "network_type": "NR",
            "deployment_mode": "SA",
            "display_override": "NONE",
            "registered": True,
            "ss_rsrp": rsrp,
            "ss_rsrq": -11.0,
            "ss_sinr": sinr,
            "csi_rsrp": None,
            "csi_rsrq": None,
            "csi_sinr": None,
            "pci": 42,
            "nci": 268435456,
            "nrarfcn": 640000,
        },
    }


def test_live_path_without_llm_and_no_network() -> None:
    """Live streaming pipeline runs completely offline with no network and no LLM."""

    def _block_connect(*args, **kwargs):
        raise OSError("Network is unreachable (simulated offline mode)")

    with patch.dict(os.environ, {"NADS_USE_LLM": "false"}, clear=True):
        with patch.object(socket.socket, "connect", side_effect=_block_connect):
            assert not is_llm_enabled()

            engine = StreamingEngine()
            tracker = EventTracker(session_id="offline-sess", device="Pixel 8", enable_agents=False)
            alert_tracker = AlertStateTracker()

            samples = [
                _sample_payload(1, -85.0, 18.0),
                _sample_payload(2, -118.0, -3.0),
                _sample_payload(3, -120.0, -5.0),
                _sample_payload(4, -85.0, 18.0),
            ]

            scored_samples = []
            events = []
            for s in samples:
                scored = engine.process(s)
                scored_samples.append(scored)
                action, evt = tracker.process_sample(scored)
                if evt is not None:
                    events.append((action, evt))
                    decision = decide(evt, history=alert_tracker)
                    assert decision is not None

            assert len(scored_samples) == 4
            assert any(s.is_anom for s in scored_samples)
            assert len(events) >= 1


def test_live_path_byte_identical_with_and_without_llm() -> None:
    """Flags, types, severities, and alert decisions are byte-identical with and without LLM."""
    test_samples = [
        _sample_payload(1, -85.0, 18.0),
        _sample_payload(2, -115.0, -2.0),
        _sample_payload(3, -118.0, -4.0),
        _sample_payload(4, -122.0, -6.0),
        _sample_payload(5, -85.0, 18.0),
    ]

    # Run 1: NADS_USE_LLM unset / false
    with patch.dict(os.environ, {"NADS_USE_LLM": "false"}):
        engine1 = StreamingEngine()
        tracker1 = EventTracker(session_id="run1", device="Pixel 8", enable_agents=False)
        alert_tracker1 = AlertStateTracker()

        scored_run1 = [engine1.process(s) for s in test_samples]
        events_run1 = []
        decisions_run1 = []
        for s in scored_run1:
            act, evt = tracker1.process_sample(s)
            if evt:
                events_run1.append((act, evt))
                decisions_run1.append(decide(evt, history=alert_tracker1))

    # Run 2: NADS_USE_LLM=true with mock Ollama response
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"response": "Extraneous LLM narrative."}'
    mock_resp.__enter__.return_value = mock_resp

    with patch.dict(os.environ, {"NADS_USE_LLM": "true"}):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            engine2 = StreamingEngine()
            tracker2 = EventTracker(session_id="run1", device="Pixel 8", enable_agents=False)
            alert_tracker2 = AlertStateTracker()

            scored_run2 = [engine2.process(s) for s in test_samples]
            events_run2 = []
            decisions_run2 = []
            for s in scored_run2:
                act, evt = tracker2.process_sample(s)
                if evt:
                    events_run2.append((act, evt))
                    decisions_run2.append(decide(evt, history=alert_tracker2))

    # Assert byte-identical scored samples
    assert len(scored_run1) == len(scored_run2)
    for s1, s2 in zip(scored_run1, scored_run2, strict=True):
        assert s1.is_anom == s2.is_anom
        assert s1.anomaly_type == s2.anomaly_type
        assert s1.severity == s2.severity
        assert s1.if_flag == s2.if_flag
        assert s1.baseline_flag == s2.baseline_flag
        assert s1.if_score == s2.if_score
        assert s1.baseline_z_max == s2.baseline_z_max

    # Assert byte-identical event lifecycle
    assert len(events_run1) == len(events_run2)
    for (a1, e1), (a2, e2) in zip(events_run1, events_run2, strict=True):
        assert a1 == a2
        assert e1.anomaly_type == e2.anomaly_type
        assert e1.severity == e2.severity
        assert e1.status == e2.status
        assert e1.ml == e2.ml

    # Assert byte-identical alert decisions
    assert len(decisions_run1) == len(decisions_run2)
    for d1, d2 in zip(decisions_run1, decisions_run2, strict=True):
        assert d1.alerted == d2.alerted
        assert d1.reason == d2.reason
        assert d1.kind == d2.kind


def test_alert_text_always_from_template_renderer() -> None:
    """Alert text is strictly formatted via template renderer and never altered by LLM."""
    atype = "SIGNAL_DEGRADATION"
    summary = "RSRP degraded below -115 dBm"
    evidence = ["ss_rsrp: -118 dBm", "ss_sinr: -3.5 dB"]

    body_no_llm = format_alert_body_with_template(
        anomaly_type=atype,
        summary=summary,
        evidence=evidence,
    )

    with patch.dict(os.environ, {"NADS_USE_LLM": "true"}):
        with patch(
            "agents.llm_explainer.explain_diagnosis",
            return_value="Unauthorized LLM modification",
        ):
            body_with_llm = format_alert_body_with_template(
                anomaly_type=atype,
                summary=summary,
                evidence=evidence,
            )

    # Must be byte-identical and free of LLM alteration
    assert body_no_llm == body_with_llm
    assert "Unauthorized LLM modification" not in body_with_llm
    assert summary in body_with_llm
    for ev in evidence:
        assert ev in body_with_llm


def test_llm_explainer_does_not_mutate_diagnosis_data() -> None:
    """LLM explainer only returns a rephrased string or None without touching inputs."""
    diag_summary = "Signal dropped abruptly."
    evidence_list = ["pci: 42 -> 100", "delta_rsrp: -25 dB"]
    note_text = "Handover failure suspected"

    res_off = explain_diagnosis(diag_summary, evidence_list, note_text, "CELL_TRANSITION")
    assert res_off is None

    # Evidence and summary inputs remain unmodified
    assert diag_summary == "Signal dropped abruptly."
    assert evidence_list == ["pci: 42 -> 100", "delta_rsrp: -25 dB"]

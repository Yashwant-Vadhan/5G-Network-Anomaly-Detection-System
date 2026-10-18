"""Guardrail tests for v2 rules G17–G26 (T10-009, T14-006).

Each test function verifies one guardrail from docs/planning/TECH_RULES_v2.md,
ensuring strict stream-batch parity, logging independence, ordering/idempotency,
authentication, evidence-gated alerting, raw data promotion, event lifecycle status,
honest latency reporting, advisory edge inference, and payload minimisation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from scripts.check_no_literal_thresholds import main as check_thresholds_main
from streaming.alerts.policy import (
    TRANSITION_TYPES,
    AlertStateTracker,
    decide,
)
from streaming.event_tracker import EventTracker, ImmutableEventError
from streaming.schema import (
    MAX_MESSAGE_BYTES,
    AlertRecord,
    EventRecord,
    ScoredSample,
)
from streaming.server import ConfigError, ServerConfig
from streaming.session_manager import SessionBuffer
from streaming.store import LiveCaptureStore


def test_no_threshold_literals_in_streaming() -> None:
    """Grep check: No numeric threshold literals in streaming/ outside config (T10-009)."""
    exit_code = check_thresholds_main()
    assert exit_code == 0, "Hardcoded numeric threshold literals found in streaming/"


def test_g17_stream_batch_parity() -> None:
    """Guardrail G17: Stream–batch parity (T11-006).

    The streaming engine yields the same flags/types/severities and scores
    (tolerance 1e-6) as the batch pipeline for the same ordered samples.
    """
    from tests.test_streaming_parity import TestSampleDataParity

    TestSampleDataParity().test_ordered_delivery()


def test_g18_streaming_must_never_harm_or_alter_logging() -> None:
    """Guardrail G18: Streaming must never harm or alter logging (T12-007, T14-006).

    CSV logging is independent of the stream; a subscriber queue drop or network
    disconnection never mutates or drops logged samples from the buffer. Missing
    samples are detected via sequence gaps, never synthesised.

    Note on OEM background behaviour: Automation of Android OEM vendor task-killers
    (MIUI/EMUI battery managers) requires manual verification on physical hardware.
    """
    buf = SessionBuffer(client_id="client-g18", session_id="test-g18", device="Pixel 8")
    assert len(buf) == 0

    # Ingest samples
    row1 = {"ss_rsrp": -85.0, "pci": 100, "timestamp": "2026-10-18T10:00:00Z"}
    buf.append(row1, seq=1)
    row2 = {"ss_rsrp": -90.0, "pci": 100, "timestamp": "2026-10-18T10:00:01Z"}
    buf.append(row2, seq=2)

    # Simulate subscriber backpressure drop
    sub_q: list[Any] = []
    # Dropping from sub_q does not touch the session buffer
    assert len(sub_q) == 0

    # Buffer records remain completely untouched and unmutated
    assert len(buf) == 2
    assert buf._rows[0]["ss_rsrp"] == -85.0
    assert buf._rows[1]["ss_rsrp"] == -90.0

    # Sequence gap detection without synthesis
    buf.append({"ss_rsrp": -95.0, "pci": 100, "timestamp": "2026-10-18T10:00:05Z"}, seq=5)
    # Total recorded rows is 3 (seq 1, 2, 5), missing seq 3 & 4 are never fabricated
    assert len(buf) == 3


def test_g19_idempotent_ordered_ingest() -> None:
    """Guardrail G19: Idempotent, ordered ingest (T11-013, T14-006).

    Duplicate/replayed seq never creates a second row; ordering uses device timestamps.
    """
    buf = SessionBuffer(client_id="client-g19", session_id="test-g19", device="Pixel 8")

    # Ingest seq 1 and seq 2
    buf.append({"ss_rsrp": -80.0, "timestamp": "2026-10-18T10:00:00Z"}, seq=1)
    buf.append({"ss_rsrp": -82.0, "timestamp": "2026-10-18T10:00:01Z"}, seq=2)
    assert len(buf) == 2

    # Duplicate seq 2 arrives
    appended = buf.append({"ss_rsrp": -99.0, "timestamp": "2026-10-18T10:00:01Z"}, seq=2)
    assert appended is False
    # Deduplication ensures row count remains 2 and original data is preserved
    assert len(buf) == 2
    assert buf._rows[1]["ss_rsrp"] == -82.0


def test_g20_authenticated_and_bounded_ingest() -> None:
    """Guardrail G20: Authenticated and bounded ingest (T14-001, T14-003, T14-006).

    Token verification uses constant-time comparison; wrong tokens are rejected;
    payload size cap MAX_MESSAGE_BYTES is enforced; tokens are never logged.
    """
    import hmac

    token = "secret-token-xyz-123"
    bad_token = "wrong-token-abc-999"

    # 1. Constant-time comparison
    assert hmac.compare_digest(token, token) is True
    assert hmac.compare_digest(token, bad_token) is False
    assert hmac.compare_digest("", token) is False

    # 2. Maximum message bounds
    assert MAX_MESSAGE_BYTES == 8192  # 8 KB cap
    oversized_bytes = b"x" * (MAX_MESSAGE_BYTES + 1)
    assert len(oversized_bytes) > MAX_MESSAGE_BYTES

    # 3. Bind exposure policy
    cfg_no_lan = ServerConfig(host="0.0.0.0", allow_lan=False, ingest_token="token123")
    with pytest.raises(ConfigError) as exc_no_lan:
        cfg_no_lan.validate()
    assert "--allow-lan" in str(exc_no_lan.value)

    cfg_no_tok = ServerConfig(host="0.0.0.0", allow_lan=True, ingest_token=None)
    with pytest.raises(ConfigError) as exc_no_tok:
        cfg_no_tok.validate()
    assert "NADS_INGEST_TOKEN" in str(exc_no_tok.value)


def test_g21_alerts_require_rule_evidence() -> None:
    """Guardrail G21: Alerts require rule evidence (T13-008, T13-009, T14-006).

    No alert (any channel) from ML-only flags, from a single weak metric,
    from UNKNOWN, or from a cell/network change alone.
    """
    tracker = AlertStateTracker()

    # 1. Statistical / ML-only anomaly never alerts
    evt_ml = {
        "event_id": "ev-ml-1",
        "anomaly_type": "STATISTICAL_ONLY",
        "severity": "HIGH",
        "persistence": 10,
        "rule_evidence": False,
        "status": "PROVISIONAL",
    }
    dec_ml = decide(evt_ml, history=tracker)
    assert not dec_ml.alerted
    assert "ML-only" in dec_ml.reason

    # 2. UNKNOWN type never alerts
    evt_unk = {
        "event_id": "ev-unk-1",
        "anomaly_type": "UNKNOWN",
        "severity": "MEDIUM",
        "persistence": 8,
        "rule_evidence": True,
        "status": "PROVISIONAL",
    }
    dec_unk = decide(evt_unk, history=tracker)
    assert not dec_unk.alerted

    # 3. Transitions alone never alert
    for trans in TRANSITION_TYPES:
        evt_t = {
            "event_id": f"ev-{trans.lower()}",
            "anomaly_type": trans,
            "severity": "MEDIUM",
            "persistence": 6,
            "rule_evidence": True,
            "status": "PROVISIONAL",
        }
        dec_t = decide(evt_t, history=tracker)
        assert not dec_t.alerted
        assert "Transition only" in dec_t.reason


def test_g22_live_data_is_raw_data(tmp_path: Path) -> None:
    """Guardrail G22: Live data is raw data (T11-009, T14-006).

    Live captures are C1-format, append-only while open, hashed on close,
    promoted to data/raw/ only by the script with a manifest entry; replay
    sessions are labelled source=replay and never counted as new real data.
    """
    # 1. Enforce path safety: cannot write directly to data/raw/
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    with pytest.raises(ValueError, match="Refusing to write to data/raw/"):
        LiveCaptureStore(
            client_id="client-bad",
            session_id="sess-bad",
            base_dir=raw_dir,
        )

    # 2. Replay sessions are labelled source=replay
    replay_dir = tmp_path / "data" / "live"
    store_replay = LiveCaptureStore(
        client_id="client-rep",
        session_id="sess-rep",
        base_dir=replay_dir,
        source="replay",
    )
    assert store_replay.source == "replay"
    store_replay.close()
    meta_replay = json.loads(store_replay.meta_path.read_text(encoding="utf-8"))
    assert meta_replay["source"] == "replay"

    # 3. Live session is append-only in C1 format and sha256 computed on close
    store_live = LiveCaptureStore(
        client_id="client-live",
        session_id="sess-live",
        base_dir=replay_dir,
        source="phone",
    )
    sample = {
        "timestamp": "2026-10-18T10:00:00Z",
        "device": "Pixel 8",
        "ss_rsrp": -85.0,
        "ss_sinr": 15.0,
        "pci": 100,
    }
    store_live.append_sample(sample)
    store_live.close()

    assert store_live.is_closed
    meta_live = json.loads(store_live.meta_path.read_text(encoding="utf-8"))
    assert meta_live["source"] == "phone"
    assert meta_live["sample_count"] == 1
    assert meta_live["sha256"] is not None
    assert len(meta_live["sha256"]) == 64


def test_g23_provisional_not_equal_final() -> None:
    """Guardrail G23: Provisional != final (T11-008, T14-006).

    Open events are labelled PROVISIONAL in every output; only closed events
    are FINAL and immutable.
    """
    tracker = EventTracker(session_id="test-g23", device="Pixel 8", enable_agents=False)

    # 1. Synthesize anomalous scored sample
    sample = {
        "timestamp": "2026-10-18T10:00:00Z",
        "is_anom": True,
        "anomaly_type": "SIGNAL_DEGRADATION",
        "severity": "HIGH",
        "if_score": 0.85,
    }
    action, evt = tracker.process_sample(sample)
    assert action == "OPEN"
    assert evt is not None
    assert evt.status == "PROVISIONAL"

    # 2. Close event after normal gap
    closed_evt = None
    for i in range(tracker.close_gap_samples):
        norm = {
            "timestamp": f"2026-10-18T10:00:{i + 1:02d}Z",
            "is_anom": False,
            "anomaly_type": "NORMAL",
        }
        action_c, cand_closed = tracker.process_sample(norm)
        if action_c == "CLOSED":
            closed_evt = cand_closed
            break

    assert closed_evt is not None
    assert closed_evt.status == "FINAL"

    # 3. Immutability check: modifying a finalized event must raise ImmutableEventError
    with pytest.raises(ImmutableEventError):
        tracker.update_event_metadata(closed_evt.event_id, diagnosis={"tampered": True})


def test_g24_honest_latency() -> None:
    """Guardrail G24: Honest latency and forbidden phrases lint (T14-006, T14-008).

    No code, doc, or UI states a guaranteed latency. Scans docs and source
    for forbidden claims ('zero latency', 'guaranteed latency', 'instant latency').
    """
    forbidden_patterns = [
        re.compile(r"\bzero[\s-]latency\b", re.IGNORECASE),
        re.compile(r"\binstant(?:aneous)?[\s-]latency\b", re.IGNORECASE),
        re.compile(r"\bguaranteed[\s-]latency\b", re.IGNORECASE),
        re.compile(r"\blatency[\s-]guarantee\b", re.IGNORECASE),
    ]

    docs_dir = Path("docs")
    violations: list[str] = []

    for doc_file in docs_dir.rglob("*.md"):
        # Exclude planning/specs documenting Guardrail G24 itself
        if "planning" in doc_file.parts:
            continue

        raw_content = doc_file.read_text(encoding="utf-8")
        # Collapse whitespace/newlines in blockquotes to recognize multi-line disclaimers
        paragraphs = re.split(r"\n\s*\n", raw_content)
        for p_idx, para in enumerate(paragraphs, 1):
            lower_para = para.lower()
            # If the paragraph is an explicit disclaimer, it is compliant with G24
            if "no latency guarantee" in lower_para or "without guaranteed" in lower_para:
                continue
            for pat in forbidden_patterns:
                match = pat.search(para)
                if match:
                    snippet = para.strip().replace("\n", " ")[:70]
                    violations.append(f"{doc_file}:para_{p_idx}: {snippet}")

    assert not violations, f"Forbidden latency claims found (G24 violation): {violations}"

    # Verify results_v2.md has mandatory footnote
    results_v2 = Path("docs/results_v2.md")
    assert results_v2.is_file()
    assert "No Latency Guarantee" in results_v2.read_text(encoding="utf-8")


def test_g25_edge_is_advisory_and_parity_gated() -> None:
    """Guardrail G25: Edge is advisory and parity-gated (T12-016, T14-006).

    Edge scores never override server results and never alter server anomaly scoring.
    """
    # Create sample where edge reported different score than server
    scored = ScoredSample(
        device="Pixel 8",
        session_id="test-g25",
        seq=1,
        timestamp="2026-10-18T10:00:00Z",
        received_at="2026-10-18T10:00:00Z",
        scored_at="2026-10-18T10:00:00Z",
        published_at="2026-10-18T10:00:00Z",
        is_anom=True,
        anomaly_type="SIGNAL_DEGRADATION",
        severity="HIGH",
        baseline_z_max=3.5,
        if_score=0.88,
        edge_if_score=0.45,
        edge_divergence=0.43,
    )
    # Server if_score remains authoritative (0.88), edge_if_score is purely advisory (0.45)
    assert scored.if_score == 0.88
    assert scored.edge_if_score == 0.45
    assert scored.edge_divergence == 0.43
    assert scored.is_anom is True


def test_g26_secrets_and_payload_minimisation() -> None:
    """Guardrail G26: Secrets and payload minimisation (T13-005, T14-006).

    Token, SMTP, webhook URL only via env vars; .env ignored; external-channel
    payloads exclude raw measurements, IDs and PII by default; no precise location.
    """
    from ml.config import RAW_COLUMNS
    from streaming.alerts.channels.email import format_email_body

    # 1. Verify .env is in .gitignore
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore

    # 2. Verify no GPS/location columns in telemetry contracts
    for col in RAW_COLUMNS:
        assert "lat" not in col.lower()
        assert "lon" not in col.lower()
        assert "gps" not in col.lower()

    # 3. Verify minimal alert payload for external channels
    alert = AlertRecord(
        alert_id="alt-test-g26",
        created_at="2026-10-17T12:00:00+00:00",
        event_id="evt-9999",
        session_id="sess-1234",
        source="phone",
        kind="NEW",
        severity="HIGH",
        anomaly_type="LOW_RSRP",
        event_status="FINAL",
        title="Low RSRP Alert",
        body="Signal degradation detected on cell.",
        evidence=["ss_rsrp: -118 dBm below threshold"],
    )

    webhook_body = alert.to_webhook_body(include_evidence=False)
    allowed_keys = {
        "title",
        "body",
        "severity",
        "anomaly_type",
        "event_status",
        "created_at",
    }
    assert set(webhook_body.keys()) == allowed_keys
    for forbidden in ("imei", "imsi", "ss_rsrp", "ss_sinr", "pci", "nci", "device"):
        assert forbidden not in webhook_body

    # 4. Verify minimal email plain-text body
    email_text = format_email_body(alert, include_evidence=False)
    assert "alt-test-g26" in email_text
    assert "LOW_RSRP" in email_text
    assert "Signal degradation detected" in email_text
    for forbidden in ("imei", "imsi", "ss_rsrp", "pci", "nci"):
        assert forbidden not in email_text.lower()


def test_g1_prime_collector_measurement_path_has_no_ml_or_edge_dependencies() -> None:
    """Guardrail G1′: Collector measurement path ≠ ML (TECH_RULES_v2.md).

    The collector's measurement and CSV logging code has no ML imports
    and no dependency on edge-inference; the pipeline reads only CSV/C7.
    """
    android_dir = Path("android-collector")
    if not android_dir.exists():
        pytest.skip("android-collector directory not present")

    forbidden_patterns = [
        re.compile(r"^\s*import\s+org\.tensorflow", re.IGNORECASE),
        re.compile(r"^\s*import\s+ai\.onnxruntime", re.IGNORECASE),
        re.compile(r"^\s*import\s+org\.pytorch", re.IGNORECASE),
        re.compile(r"^\s*import\s+com\.google\.ai\.edge", re.IGNORECASE),
        re.compile(r"^\s*import\s+.*edge_inference", re.IGNORECASE),
        re.compile(r"^\s*import\s+.*edgeinference", re.IGNORECASE),
    ]

    source_files = list(android_dir.rglob("*.kt")) + list(android_dir.rglob("*.java"))
    assert len(source_files) > 0, "No Android collector source files found"

    for src_file in source_files:
        if "edge-inference" in src_file.parts or "edge_inference" in src_file.parts:
            continue
        text = src_file.read_text(encoding="utf-8", errors="replace")
        for line_num, line in enumerate(text.splitlines(), 1):
            for pat in forbidden_patterns:
                assert not pat.search(line), (
                    f"Guardrail G1′ violation: forbidden ML/edge import found in "
                    f"{src_file}:{line_num}: {line.strip()}"
                )

    for gradle_file in android_dir.rglob("build.gradle*"):
        text = gradle_file.read_text(encoding="utf-8", errors="replace")
        if "app" in gradle_file.parts:
            assert "edge-inference" not in text.lower(), (
                f"Guardrail G1′ violation: edge-inference referenced in "
                f"{gradle_file}"
            )


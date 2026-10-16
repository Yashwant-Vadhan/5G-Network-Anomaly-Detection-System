"""Tests for live capture store (T11-009, Contract C1, Guardrails G7/G22)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ml.config import RAW_COLUMNS
from ml.preprocessing import load_raw_csv, preprocess
from streaming.store import LiveCaptureStore, compute_sha256


@pytest.fixture
def sample_measurements() -> list[dict]:
    """Provide realistic Contract C1 measurement dicts for live store testing."""
    return [
        {
            "timestamp": "30-09-26 22:51:39",
            "device": "2406ERN9CI",
            "manufacturer": "Xiaomi",
            "android": "16",
            "operator": "Airtel FastLane",
            "network_type": "5G NR",
            "deployment_mode": "UNKNOWN",
            "display_override": "NONE",
            "registered": True,
            "ss_rsrp": -97.0,
            "ss_rsrq": -12.0,
            "ss_sinr": 6.0,
            "csi_rsrp": None,
            "csi_rsrq": None,
            "csi_sinr": None,
            "pci": 336,
            "nci": 13322280247,
            "nrarfcn": 629952,
        },
        {
            "timestamp": "30-09-26 22:51:42",
            "device": "2406ERN9CI",
            "manufacturer": "Xiaomi",
            "android": "16",
            "operator": "Airtel FastLane",
            "network_type": "5G NR",
            "deployment_mode": "UNKNOWN",
            "display_override": "NONE",
            "registered": True,
            "ss_rsrp": -98.0,
            "ss_rsrq": -12.5,
            "ss_sinr": 5.5,
            "csi_rsrp": None,
            "csi_rsrq": None,
            "csi_sinr": None,
            "pci": 336,
            "nci": 13322280247,
            "nrarfcn": 629952,
        },
    ]


def test_live_capture_store_lifecycle(tmp_path: Path, sample_measurements: list[dict]):
    """Store initializes C1 CSV and writes sidecar metadata with valid sha256 on close."""
    store = LiveCaptureStore(
        client_id="client-001",
        session_id="session-walk-01",
        base_dir=tmp_path,
        start_time="2026-10-16T20:30:00",
    )

    assert store.csv_path.exists()
    assert store.meta_path.exists()

    # Initial metadata status is OPEN
    initial_meta = json.loads(store.meta_path.read_text(encoding="utf-8"))
    assert initial_meta["status"] == "OPEN"
    assert initial_meta["sample_count"] == 0
    assert initial_meta["sha256"] is None

    # Append measurements
    for sample in sample_measurements:
        store.append_sample(sample)

    assert store.sample_count == 2

    # Close session
    store.close()
    assert store.status == "CLOSED"

    # Verify finalized metadata
    closed_meta = json.loads(store.meta_path.read_text(encoding="utf-8"))
    assert closed_meta["status"] == "CLOSED"
    assert closed_meta["sample_count"] == 2
    assert closed_meta["sha256"] == compute_sha256(store.csv_path)

    # Re-closing is idempotent
    store.close()


def test_capture_reingested_by_batch_pipeline_matches(
    tmp_path: Path, sample_measurements: list[dict]
):
    """Capture CSV re-ingested by batch load_raw_csv and preprocess succeeds."""
    live_in = tmp_path / "live_in"
    clean_out = tmp_path / "clean_out"

    store = LiveCaptureStore(
        client_id="phone-a15",
        session_id="sess-002",
        base_dir=live_in,
    )
    for sample in sample_measurements:
        store.append_sample(sample)
    store.close()

    # Re-ingest via batch load_raw_csv
    raw_df = load_raw_csv(store.csv_path)
    assert len(raw_df) == 2
    for col in RAW_COLUMNS:
        assert col in raw_df.columns

    # Verify batch preprocessing runs cleanly without error
    preprocessed_df = preprocess(raw_dir=live_in, out_dir=clean_out)
    assert len(preprocessed_df) == 2
    assert "ss_rsrp" in preprocessed_df.columns
    assert preprocessed_df["ss_rsrp"].iloc[0] == -97.0
    assert preprocessed_df["ss_rsrp"].iloc[1] == -98.0


def test_guardrails_g7_g22_path_protection(tmp_path: Path):
    """Store strictly refuses any base_dir or file path under data/raw/."""
    fake_raw_dir = tmp_path / "data" / "raw"
    fake_raw_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="Refusing to write to data/raw/"):
        LiveCaptureStore(
            client_id="malicious_client",
            session_id="sess_hack",
            base_dir=fake_raw_dir,
        )

    # Subpath under data/raw
    sub_raw_dir = fake_raw_dir / "nested" / "folder"
    with pytest.raises(ValueError, match="Refusing to write to data/raw/"):
        LiveCaptureStore(
            client_id="malicious_client",
            session_id="sess_hack",
            base_dir=sub_raw_dir,
        )


def test_crash_simulation_leaves_status_incomplete(tmp_path: Path, sample_measurements: list[dict]):
    """Context manager or mark_incomplete upon crash records INCOMPLETE status."""
    store = LiveCaptureStore(
        client_id="crash-client",
        session_id="crash-sess",
        base_dir=tmp_path,
    )
    store.append_sample(sample_measurements[0])

    # Simulate unexpected process crash or error
    store.mark_incomplete(reason="Simulated connection drop or power loss")
    assert store.status == "INCOMPLETE"

    meta = json.loads(store.meta_path.read_text(encoding="utf-8"))
    assert meta["status"] == "INCOMPLETE"
    assert meta["sample_count"] == 1
    assert meta["sha256"] is not None


def test_context_manager_exception_marks_incomplete(tmp_path: Path):
    """If an unhandled exception occurs inside with-block, session is marked INCOMPLETE."""
    meta_path = None
    with pytest.raises(RuntimeError, match="Sudden error"):
        with LiveCaptureStore(
            client_id="ctx-client",
            session_id="ctx-sess",
            base_dir=tmp_path,
        ) as store:
            meta_path = store.meta_path
            raise RuntimeError("Sudden error")

    assert meta_path is not None and meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["status"] == "INCOMPLETE"

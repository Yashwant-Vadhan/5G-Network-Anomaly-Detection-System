"""Integration tests for full pipeline execution on real sample data (T7-007)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest

from pipelines.run_pipeline import run_pipeline
from ml.config import RAW_COLUMNS


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def test_full_pipeline_integration(tmp_path):
    """Verify full end-to-end pipeline execution on real sample data."""
    sample_dir = Path("data/sample")
    sample_csv = sample_dir / "sample_measurements.csv"
    assert sample_csv.exists(), "Sample measurements file missing from data/sample/"

    # Check initial sample hash
    initial_sample_hash = compute_file_sha256(sample_csv)

    out_dir_1 = tmp_path / "run1"
    out_dir_2 = tmp_path / "run2"

    # Run 1
    clean_csv1, feat_csv1, scores_csv1, events_json1 = run_pipeline(
        input_dir=sample_dir,
        output_dir=out_dir_1,
        retrain=True,
    )

    # 1. Assert Raw sample file hash is UNCHANGED
    final_sample_hash = compute_file_sha256(sample_csv)
    assert initial_sample_hash == final_sample_hash, "Raw sample file was modified by pipeline execution!"

    # 2. Assert Contract C2 (measurements_clean.csv) column by column
    assert clean_csv1.exists()
    df_clean = pd.read_csv(clean_csv1)
    for col in RAW_COLUMNS:
        assert col in df_clean.columns, f"Contract C2 missing raw column {col}"
    for required_c2 in ["session_id", "sample_idx", "is_valid", "model_eligible", "csi_available", "is_synthetic"]:
        assert required_c2 in df_clean.columns, f"Contract C2 missing engineered column {required_c2}"

    # 3. Assert Contract C3 (features.csv) column by column
    assert feat_csv1.exists()
    df_feat = pd.read_csv(feat_csv1)
    for required_c3 in ["delta_rsrp", "delta_rsrq", "delta_sinr", "pci_changed", "nci_changed", "network_changed", "rolling_mean_rsrp", "weak_rsrp_run"]:
        assert required_c3 in df_feat.columns, f"Contract C3 missing feature column {required_c3}"

    # 4. Assert Contract C4 (scores.csv) column by column
    assert scores_csv1.exists()
    df_scores = pd.read_csv(scores_csv1)
    for required_c4 in ["baseline_z_max", "baseline_flag", "if_score", "if_flag", "anomaly_type", "severity", "event_id"]:
        assert required_c4 in df_scores.columns, f"Contract C4 missing score column {required_c4}"

    # 5. Assert Contract C5 (events_diagnosed.json) schema and contents
    assert events_json1.exists()
    with open(events_json1, encoding="utf-8") as f:
        events = json.load(f)
    assert isinstance(events, list)
    for event in events:
        for c5_key in ["event_id", "session_id", "start", "end", "anomaly_type", "severity", "ml", "signal", "cell", "network", "diagnosis", "recommendation"]:
            assert c5_key in event, f"Contract C5 event missing key {c5_key}"

    # Run 2: Verify Determinism across runs
    clean_csv2, feat_csv2, scores_csv2, events_json2 = run_pipeline(
        input_dir=sample_dir,
        output_dir=out_dir_2,
        retrain=True,
    )

    df_clean2 = pd.read_csv(clean_csv2)
    df_scores2 = pd.read_csv(scores_csv2)

    pd.testing.assert_frame_equal(df_clean, df_clean2)
    pd.testing.assert_frame_equal(df_scores, df_scores2)

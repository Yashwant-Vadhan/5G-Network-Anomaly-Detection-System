"""Unit tests for end-to-end pipeline CLI (T7-001)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

from pipelines.run_pipeline import run_pipeline, main
from ml.schema import ConfigError


def test_run_pipeline_on_sample_data(tmp_path):
    """Verify run_pipeline produces Contract C2-C5 files when run on sample data."""
    sample_dir = Path("data/sample")
    out_dir = tmp_path / "processed"

    clean_csv, features_csv, scores_csv, events_json = run_pipeline(
        input_dir=sample_dir,
        output_dir=out_dir,
        retrain=True,
    )

    # Check contract C2
    assert clean_csv.exists()
    df_clean = pd.read_csv(clean_csv)
    assert "session_id" in df_clean.columns

    # Check contract C3
    assert features_csv.exists()
    df_feat = pd.read_csv(features_csv)
    assert "delta_rsrp" in df_feat.columns

    # Check contract C4
    assert scores_csv.exists()
    df_scores = pd.read_csv(scores_csv)
    assert "anomaly_type" in df_scores.columns
    assert "severity" in df_scores.columns

    # Check contract C5
    assert events_json.exists()
    with open(events_json, encoding="utf-8") as f:
        events = json.load(f)
    assert isinstance(events, list)


def test_run_pipeline_invalid_input_dir(tmp_path):
    """Verify run_pipeline raises ConfigError when input directory is missing."""
    bad_dir = tmp_path / "non_existent"
    out_dir = tmp_path / "out"

    with pytest.raises(ConfigError):
        run_pipeline(input_dir=bad_dir, output_dir=out_dir)


def test_run_pipeline_cli_main_invalid(monkeypatch, tmp_path):
    """Verify CLI main exits with status code 2 on ConfigError."""
    bad_dir = tmp_path / "non_existent"
    monkeypatch.setattr("sys.argv", ["run_pipeline", "--input", str(bad_dir)])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2

"""Unit tests for ml/anomaly_detection.py."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.anomaly_detection import baseline_scores, if_scores
from ml.config import FEATURE_COLUMNS
from ml.train import train_iforest


def test_baseline_scores_flat_signal():
    """Flat signal should yield zero z-scores and no flags."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 10,
            "session_id": ["s1"] * 10,
            "ss_rsrp": [-80.0] * 10,
            "ss_rsrq": [-10.0] * 10,
            "ss_sinr": [20.0] * 10,
        }
    )
    result = baseline_scores(df, window=5)

    assert result["baseline_z_max"].max() == pytest.approx(0.0)
    assert not result["baseline_flag"].any()


def test_baseline_scores_step_change_flagged():
    """A sudden large step drop in RSRP should be flagged by baseline_scores."""
    # 5 steady samples then a sudden drop to -120.0 dBm
    rsrp = [-80.0, -80.0, -80.0, -80.0, -80.0, -120.0]
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 6,
            "session_id": ["s1"] * 6,
            "ss_rsrp": rsrp,
            "ss_rsrq": [-10.0] * 6,
            "ss_sinr": [20.0] * 6,
        }
    )
    result = baseline_scores(df, window=5, threshold=2.5)

    # Warmup samples (idx 0..4 with flat signal) have z=0.0
    assert result.loc[0, "baseline_z_rsrp"] == pytest.approx(0.0)

    # Sample at idx 5 (drop to -120) has large z-score and baseline_flag=True
    assert result.loc[5, "baseline_z_rsrp"] > 2.5
    assert result.loc[5, "baseline_flag"]


def test_if_scores(tmp_path: Path):
    """Test IsolationForest scoring function, score range, and ineligible row handling."""
    data = {col: np.random.RandomState(42).randn(20) * 5 + 50 for col in FEATURE_COLUMNS}
    df = pd.DataFrame(data)
    df["model_eligible"] = True
    df["is_synthetic"] = False

    # Make row 5 ineligible and row 10 missing feature
    df.loc[5, "model_eligible"] = False
    df.loc[10, "ss_rsrp"] = np.nan

    model, _, _ = train_iforest(df, out_dir=tmp_path)
    from joblib import load

    scaler = load(tmp_path / "scaler.joblib")

    scored_df = if_scores(df, model=model, scaler=scaler, threshold=0.5)

    assert "if_score" in scored_df.columns
    assert "if_flag" in scored_df.columns

    valid_scores = scored_df.loc[scored_df["if_score"].notna(), "if_score"]
    assert (valid_scores >= 0.0).all()
    assert (valid_scores <= 1.0).all()

    # Ineligible rows 5 and 10 should be NaN score and False flag
    assert pd.isna(scored_df.loc[5, "if_score"])
    assert not scored_df.loc[5, "if_flag"]
    assert pd.isna(scored_df.loc[10, "if_score"])
    assert not scored_df.loc[10, "if_flag"]


def test_if_scores_determinism(tmp_path: Path):
    """Test that two runs of IsolationForest with fixed seed yield identical scores."""
    from joblib import load

    data = {col: np.random.RandomState(42).randn(30) * 5 + 50 for col in FEATURE_COLUMNS}
    df = pd.DataFrame(data)
    df["model_eligible"] = True
    df["is_synthetic"] = False

    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    model1, _, _ = train_iforest(df, out_dir=dir1)
    scaler1 = load(dir1 / "scaler.joblib")
    scored1 = if_scores(df, model=model1, scaler=scaler1, threshold=0.5)

    model2, _, _ = train_iforest(df, out_dir=dir2)
    scaler2 = load(dir2 / "scaler.joblib")
    scored2 = if_scores(df, model=model2, scaler=scaler2, threshold=0.5)

    pd.testing.assert_series_equal(scored1["if_score"], scored2["if_score"])
    pd.testing.assert_series_equal(scored1["if_flag"], scored2["if_flag"])


def test_if_v1_metadata_completeness(tmp_path: Path):
    """Test that if_v1.meta.json contains all required provenance keys per contract C3."""
    import json

    data = {col: np.random.RandomState(42).randn(20) * 5 + 50 for col in FEATURE_COLUMNS}
    df = pd.DataFrame(data)
    df["model_eligible"] = True
    df["is_synthetic"] = False

    _, _, meta_path = train_iforest(df, out_dir=tmp_path)
    assert meta_path.exists()

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    required_keys = [
        "model_name",
        "feature_columns",
        "random_state",
        "n_estimators",
        "contamination",
        "sklearn_version",
        "training_rows",
        "training_data_sha256",
        "created_at",
    ]
    for key in required_keys:
        assert key in meta, f"Missing required metadata key: {key}"


def test_guardrail_g11_synthetic_training_forbidden(tmp_path: Path):
    """Test Guardrail G11: training IF on synthetic data raises ValueError unless allow_synthetic=True."""
    data = {col: np.random.RandomState(42).randn(20) * 5 + 50 for col in FEATURE_COLUMNS}
    df = pd.DataFrame(data)
    df["model_eligible"] = True
    df["is_synthetic"] = True  # Synthetic data

    with pytest.raises(ValueError, match="Guardrail G11"):
        train_iforest(df, out_dir=tmp_path)

    # Allowed with explicit override
    model, _, _ = train_iforest(df, out_dir=tmp_path, allow_synthetic=True)
    assert model is not None


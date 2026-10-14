"""Unit tests for ml/train.py (T4-008)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.config import FEATURE_COLUMNS, RANDOM_STATE
from ml.train import train_iforest


@pytest.fixture
def dummy_feature_df() -> pd.DataFrame:
    """Create synthetic training DataFrame."""
    np.random.seed(RANDOM_STATE)
    data = {col: np.random.randn(50) * 5 + 50 for col in FEATURE_COLUMNS}
    df = pd.DataFrame(data)
    df["model_eligible"] = True
    df["is_synthetic"] = False
    return df


def test_train_iforest_saves_artifacts(dummy_feature_df: pd.DataFrame, tmp_path: Path):
    """Verify train_iforest saves joblib model and metadata json."""
    model, model_path, meta_path = train_iforest(dummy_feature_df, out_dir=tmp_path)

    assert model_path.exists()
    assert meta_path.exists()
    assert model_path.name == "if_v1.joblib"
    assert meta_path.name == "if_v1.meta.json"

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["model_name"] == "if_v1"
    assert meta["random_state"] == RANDOM_STATE
    assert meta["training_rows"] == 50
    assert "training_data_sha256" in meta


def test_train_iforest_reproducibility(dummy_feature_df: pd.DataFrame, tmp_path: Path):
    """Verify two training runs produce deterministic results."""
    model1, _, _ = train_iforest(dummy_feature_df, out_dir=tmp_path / "run1")
    model2, _, _ = train_iforest(dummy_feature_df, out_dir=tmp_path / "run2")

    test_x = dummy_feature_df[FEATURE_COLUMNS].values
    scores1 = model1.score_samples(test_x)
    scores2 = model2.score_samples(test_x)

    np.testing.assert_array_almost_equal(scores1, scores2)


def test_train_iforest_synthetic_guardrail(dummy_feature_df: pd.DataFrame, tmp_path: Path):
    """Verify training with synthetic data raises error unless allow_synthetic=True (G11)."""
    dummy_feature_df.loc[0, "is_synthetic"] = True

    with pytest.raises(ValueError, match="Guardrail G11"):
        train_iforest(dummy_feature_df, out_dir=tmp_path, allow_synthetic=False)

    # Should succeed when allow_synthetic=True
    model, _, _ = train_iforest(dummy_feature_df, out_dir=tmp_path, allow_synthetic=True)
    assert model is not None


def test_train_iforest_metadata_has_new_fields(dummy_feature_df: pd.DataFrame, tmp_path: Path):
    """Verify trained model metadata contains model_version, feature_hash, and artifact hashes (T10-013)."""
    _, _, meta_path = train_iforest(dummy_feature_df, out_dir=tmp_path)
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["model_version"] == "1.0.0"
    assert "feature_hash" in meta
    assert len(meta["feature_hash"]) == 64
    assert "model_sha256" in meta
    assert len(meta["model_sha256"]) == 64
    assert "scaler_sha256" in meta
    assert meta["scaler_sha256"] is not None


def test_verify_model_metadata_success():
    """Verify verify_model_metadata passes on current models directory."""
    from ml.config import MODELS_DIR
    from ml.train import verify_model_metadata

    meta = verify_model_metadata(MODELS_DIR)
    assert meta["model_version"] == "1.0.0"
    assert "feature_hash" in meta


def test_verify_model_metadata_tampered_features(tmp_path: Path):
    """Verify loader check raises ConfigError on tampered feature list (T10-013)."""
    from ml.schema import ConfigError
    from ml.train import update_model_metadata, verify_model_metadata

    # Copy metadata to tmp_path
    meta = update_model_metadata(
        meta_path=tmp_path / "if_v1.meta.json",
        model_path=tmp_path / "if_v1.joblib",
        scaler_path=tmp_path / "scaler.joblib",
        feature_cols=list(FEATURE_COLUMNS),
    )

    # Tamper with feature list
    tampered_meta = dict(meta)
    tampered_meta["feature_columns"] = list(FEATURE_COLUMNS)[:-1]  # drop one feature
    with open(tmp_path / "if_v1.meta.json", "w", encoding="utf-8") as f:
        json.dump(tampered_meta, f)

    with pytest.raises(ConfigError, match="Model feature columns mismatch"):
        verify_model_metadata(tmp_path)


def test_verify_model_metadata_tampered_hash(tmp_path: Path):
    """Verify loader check raises ConfigError on tampered feature_hash (T10-013)."""
    from ml.schema import ConfigError
    from ml.train import update_model_metadata, verify_model_metadata

    meta = update_model_metadata(
        meta_path=tmp_path / "if_v1.meta.json",
        model_path=tmp_path / "if_v1.joblib",
        scaler_path=tmp_path / "scaler.joblib",
        feature_cols=list(FEATURE_COLUMNS),
    )

    tampered_meta = dict(meta)
    tampered_meta["feature_hash"] = "0" * 64
    with open(tmp_path / "if_v1.meta.json", "w", encoding="utf-8") as f:
        json.dump(tampered_meta, f)

    with pytest.raises(ConfigError, match="Model feature_hash mismatch"):
        verify_model_metadata(tmp_path)

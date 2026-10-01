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

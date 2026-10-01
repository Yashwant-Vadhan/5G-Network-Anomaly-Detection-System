"""Unit tests for ml/scaler.py (T4-006)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import StandardScaler

from ml.config import FEATURE_COLUMNS
from ml.scaler import fit_scaler, transform_features


@pytest.fixture
def sample_feature_df() -> pd.DataFrame:
    """Create sample feature DataFrame with eligible and ineligible rows."""
    data = {col: np.random.RandomState(42).randn(10) * 10 + 50 for col in FEATURE_COLUMNS}
    df = pd.DataFrame(data)
    df["model_eligible"] = True

    # Ineligible row 1: explicit model_eligible = False
    df.loc[2, "model_eligible"] = False

    # Ineligible row 2: missing feature value
    df.loc[5, "ss_rsrp"] = np.nan
    return df


def test_fit_scaler_filters_ineligible(sample_feature_df: pd.DataFrame, tmp_path: Path):
    """Verify scaler fits only on eligible rows and excludes missing values."""
    scaler, path = fit_scaler(sample_feature_df, out_dir=tmp_path)

    assert path.exists()
    assert isinstance(scaler, StandardScaler)
    # Total 10 rows: row 2 is ineligible (False), row 5 has NaN -> 8 fitted rows
    assert scaler.n_samples_seen_ == 8


def test_transform_features_leaves_ineligible_nan(sample_feature_df: pd.DataFrame, tmp_path: Path):
    """Verify transform returns scaled matrix with NaNs for ineligible rows."""
    scaler, _ = fit_scaler(sample_feature_df, out_dir=tmp_path)
    scaled = transform_features(sample_feature_df, scaler)

    assert scaled.shape == (10, len(FEATURE_COLUMNS))
    # Ineligible rows 2 and 5 must be NaN in the output
    assert np.isnan(scaled[2]).all()
    assert np.isnan(scaled[5]).all()
    # Eligible row 0 must be finite scaled numbers
    assert np.isfinite(scaled[0]).all()

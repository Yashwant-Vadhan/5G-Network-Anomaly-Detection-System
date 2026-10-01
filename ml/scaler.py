"""Feature scaling module for 5G-NADS.

Implements StandardScaler fitting and transformation on model_eligible samples
as specified in todo.md T4-006 and project-overview.md §22.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ml.config import FEATURE_COLUMNS, MODELS_DIR

logger = logging.getLogger(__name__)


def fit_scaler(
    df: pd.DataFrame,
    feature_cols: Sequence[str] = FEATURE_COLUMNS,
    out_dir: Path | str = MODELS_DIR,
    filename: str = "scaler.joblib",
) -> tuple[StandardScaler, Path]:
    """Fit a StandardScaler on eligible training rows and save to disk.

    Only rows where `model_eligible == True` (or where `model_eligible` column is absent,
    all feature_cols are non-null) are used for fitting. No imputation is performed (G3).

    Args:
        df: Input DataFrame containing feature_cols.
        feature_cols: List of numerical features to scale.
        out_dir: Directory path where scaler artifact is stored.
        filename: Name of the joblib scaler artifact file.

    Returns:
        Tuple of (fitted StandardScaler instance, Path to saved scaler file).
    """
    out_path = Path(out_dir) / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Filter eligible rows
    eligible_mask = df["model_eligible"].fillna(False) if "model_eligible" in df.columns else pd.Series(True, index=df.index)
    
    # Check for NaN in feature_cols among eligible rows
    feat_df = df.loc[eligible_mask, list(feature_cols)]
    non_null_mask = feat_df.notna().all(axis=1)
    fit_df = feat_df.loc[non_null_mask]

    if fit_df.empty:
        raise ValueError("No eligible rows without missing feature values available to fit scaler.")

    scaler = StandardScaler()
    scaler.fit(fit_df.values)
    
    joblib.dump(scaler, out_path)
    logger.info("Fitted StandardScaler on %d eligible rows, saved to %s", len(fit_df), out_path)

    return scaler, out_path


def transform_features(
    df: pd.DataFrame,
    scaler: StandardScaler,
    feature_cols: Sequence[str] = FEATURE_COLUMNS,
) -> np.ndarray:
    """Transform feature columns using a fitted StandardScaler.

    Eligible rows are scaled; ineligible or missing feature rows receive NaNs.

    Args:
        df: DataFrame containing feature_cols.
        scaler: Fitted StandardScaler instance.
        feature_cols: List of numerical feature columns.

    Returns:
        2D numpy array of shape (len(df), len(feature_cols)) with scaled values.
    """
    scaled_matrix = np.full((len(df), len(feature_cols)), np.nan, dtype=np.float64)

    eligible_mask = df["model_eligible"].fillna(False) if "model_eligible" in df.columns else pd.Series(True, index=df.index)
    feat_df = df[list(feature_cols)]
    valid_mask = eligible_mask & feat_df.notna().all(axis=1)

    if valid_mask.any():
        valid_values = feat_df.loc[valid_mask].values
        scaled_matrix[valid_mask] = scaler.transform(valid_values)

    return scaled_matrix

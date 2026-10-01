"""Anomaly detection module for 5G Network Anomaly Detection System (5G-NADS).

Implements rolling z-score baseline detection and Isolation Forest scoring
per project-overview.md §23-24 and todo.md Phase 4.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ml.config import BASELINE_Z_THRESHOLD, DEFAULT_WINDOW, FEATURE_COLUMNS, MODELS_DIR
from ml.scaler import transform_features

logger = logging.getLogger(__name__)


def baseline_scores(
    df: pd.DataFrame,
    threshold: float = BASELINE_Z_THRESHOLD,
    window: int = DEFAULT_WINDOW,
) -> pd.DataFrame:
    """Compute rolling z-score baseline anomaly detection per session.

    Deviation of current sample from the preceding rolling window statistics
    (excluding the current sample via shift).
    If std == 0 or std is NaN (warm-up) -> z-score = 0.0.

    Origin: project-overview.md §23, todo.md T4-007 — rolling z-score baseline.

    Args:
        df: Input DataFrame with numeric ss_rsrp, ss_rsrq, ss_sinr and session_id.
        threshold: Z-score threshold for anomaly flag (default from config).
        window: Rolling window size for historical statistics.

    Returns:
        DataFrame with added baseline_z_rsrp, baseline_z_rsrq, baseline_z_sinr,
        baseline_z_max, and baseline_flag columns.
    """
    df = df.copy()
    group_cols = ["device", "session_id"] if "session_id" in df.columns else ["device"]
    min_periods = max(2, window // 2)

    z_cols = []
    for metric in ["ss_rsrp", "ss_rsrq", "ss_sinr"]:
        z_col = f"baseline_z_{metric.replace('ss_', '')}"
        z_cols.append(z_col)

        if metric not in df.columns:
            df[z_col] = 0.0
            continue

        # Rolling statistics on PRECEDING samples only (shift by 1)
        roll_mean = df.groupby(group_cols, observed=True)[metric].transform(
            lambda x: x.shift(1).rolling(window=window, min_periods=min_periods).mean()
        )
        roll_std = df.groupby(group_cols, observed=True)[metric].transform(
            lambda x: x.shift(1).rolling(window=window, min_periods=min_periods).std()
        )

        curr = df[metric]
        diff = (curr - roll_mean).abs()

        # Valid historical window where roll_mean is present
        valid_history = roll_mean.notna()

        # Floor roll_std at 1.0 to handle flat constant baselines (std=0) without div by 0
        effective_std = roll_std.fillna(1.0).clip(lower=1.0)

        z_score = pd.Series(0.0, index=df.index, dtype="float64")
        z_score[valid_history] = (diff[valid_history] / effective_std[valid_history]).astype(
            "float64"
        )

        df[z_col] = z_score

    # Compute baseline_z_max and baseline_flag
    df["baseline_z_max"] = df[z_cols].max(axis=1).fillna(0.0)
    df["baseline_flag"] = (df["baseline_z_max"] >= threshold).astype("boolean")

    return df


def if_scores(
    df: pd.DataFrame,
    model: IsolationForest | None = None,
    scaler: StandardScaler | None = None,
    models_dir: Path | str = MODELS_DIR,
    feature_cols: Sequence[str] = FEATURE_COLUMNS,
    threshold: float = 0.6,
) -> pd.DataFrame:
    """Compute Isolation Forest anomaly scores and flags.

    Normalisation Formula (documented in docs/ml_methodology.md):
        raw_score = model.score_samples(scaled_X)  # in range [-1.0, 0.0]
        if_score = np.clip(0.5 - raw_score, 0.0, 1.0)  # higher = more anomalous

    Ineligible rows (`model_eligible == False` or missing features) receive NaN
    for `if_score` and `False` for `if_flag`.

    Origin: todo.md T4-009, project-overview.md §24.

    Args:
        df: DataFrame containing features and model_eligible column.
        model: Trained IsolationForest model instance (or None to load from models_dir).
        scaler: Fitted StandardScaler instance (or None to load from models_dir).
        models_dir: Path to directory holding saved joblib artifacts.
        feature_cols: Sequence of model feature column names.
        threshold: Score threshold for declaring `if_flag = True` (default 0.6).

    Returns:
        DataFrame with added `if_score` (float64) and `if_flag` (boolean) columns.
    """
    df = df.copy()
    models_path = Path(models_dir)

    if model is None:
        model_file = models_path / "if_v1.joblib"
        if not model_file.exists():
            raise FileNotFoundError(f"Saved IsolationForest model not found at {model_file}")
        model = joblib.load(model_file)

    if scaler is None:
        scaler_file = models_path / "scaler.joblib"
        if not scaler_file.exists():
            raise FileNotFoundError(f"Saved StandardScaler not found at {scaler_file}")
        scaler = joblib.load(scaler_file)

    eligible_mask = (
        df["model_eligible"].fillna(False)
        if "model_eligible" in df.columns
        else pd.Series(True, index=df.index)
    )
    feat_df = df[list(feature_cols)]
    valid_mask = eligible_mask & feat_df.notna().all(axis=1)

    if_score = pd.Series(np.nan, index=df.index, dtype="float64")
    if_flag = pd.Series(False, index=df.index, dtype="boolean")

    if valid_mask.any():
        valid_df = df.loc[valid_mask]
        scaled_X = transform_features(valid_df, scaler, feature_cols=feature_cols)

        # IsolationForest score_samples: lower values indicate higher anomaly degree
        raw_scores = model.score_samples(scaled_X)

        # Normalise to [0.0, 1.0] where higher = more anomalous
        # Standard IF score_samples ranges around -0.5 for boundary, -0.7..-0.9 for anomalies
        norm_scores = np.clip(0.5 - raw_scores, 0.0, 1.0)

        if_score.loc[valid_mask] = norm_scores
        if_flag.loc[valid_mask] = norm_scores >= threshold

    df["if_score"] = if_score
    df["if_flag"] = if_flag.astype("boolean")

    return df

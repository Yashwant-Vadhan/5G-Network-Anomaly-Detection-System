"""Anomaly detection module for 5G Network Anomaly Detection System (5G-NADS).

Implements rolling z-score baseline detection and Isolation Forest scoring
per project-overview.md §23-24 and todo.md Phase 4.
"""

from __future__ import annotations

import logging

import pandas as pd

from ml.config import BASELINE_Z_THRESHOLD, DEFAULT_WINDOW

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

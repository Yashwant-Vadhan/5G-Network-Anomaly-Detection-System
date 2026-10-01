"""Feature engineering module for 5G Network Anomaly Detection System (5G-NADS).

Implements delta features, cell/network change indicators, and rolling statistics
as specified in project-overview.md §22-23 and todo.md Phase 4.
"""

from __future__ import annotations

import logging

import pandas as pd

from ml.config import DEFAULT_WINDOW

logger = logging.getLogger(__name__)


def add_deltas(df: pd.DataFrame) -> pd.DataFrame:
    """Compute sample-to-sample signal metric deltas within (device, session_id).

    Adds columns: delta_rsrp, delta_rsrq, delta_sinr = current - previous.
    First sample of each session → missing (pd.NA / NaN).
    If either operand is missing → result is missing (never 0).

    Origin: project-overview.md §23 — temporal delta features.

    Args:
        df: Input DataFrame with numeric ss_rsrp, ss_rsrq, ss_sinr and session_id columns.

    Returns:
        DataFrame with added delta_rsrp, delta_rsrq, delta_sinr columns.
    """
    df = df.copy()
    group_cols = ["device", "session_id"] if "session_id" in df.columns else ["device"]

    for metric, delta_col in [
        ("ss_rsrp", "delta_rsrp"),
        ("ss_rsrq", "delta_rsrq"),
        ("ss_sinr", "delta_sinr"),
    ]:
        if metric in df.columns:
            df[delta_col] = df.groupby(group_cols, observed=True)[metric].diff()
        else:
            df[delta_col] = pd.NA

    return df


def add_change_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Compute cell and network change indicator flags within each session.

    Adds columns: pci_changed, nci_changed, network_changed (int: 0 or 1).
    First sample of each session → 0.
    If either current or previous value is missing → 0 (not a detected change)
    and a change_flag_unknown count is logged.

    Origin: project-overview.md §23 — change indicator features.

    Args:
        df: Input DataFrame with pci, nci, network_type and session_id columns.

    Returns:
        DataFrame with added pci_changed, nci_changed, network_changed columns.
    """
    df = df.copy()
    group_cols = ["device", "session_id"] if "session_id" in df.columns else ["device"]
    change_flag_unknown = 0

    for col, flag_col in [
        ("pci", "pci_changed"),
        ("nci", "nci_changed"),
        ("network_type", "network_changed"),
    ]:
        if col not in df.columns:
            df[flag_col] = 0
            continue

        prev = df.groupby(group_cols, observed=True)[col].shift(1)
        current = df[col]

        # Both present and different → 1
        both_present = current.notna() & prev.notna()
        changed = both_present & (current != prev)
        df[flag_col] = changed.astype(int)

        # Count cases where either value is missing (excluding session starts)
        is_session_start = prev.isna() & df.groupby(group_cols, observed=True).cumcount().eq(0)
        missing_pair = (~both_present) & (~is_session_start)
        unknown_count = int(missing_pair.sum())
        if unknown_count > 0:
            change_flag_unknown += unknown_count

    if change_flag_unknown > 0:
        logger.info(
            "change_flag_unknown: %d comparisons had missing values (treated as no change)",
            change_flag_unknown,
        )

    return df


def add_rolling(df: pd.DataFrame, window: int = DEFAULT_WINDOW) -> pd.DataFrame:
    """Compute rolling mean and standard deviation of signal metrics per session.

    Adds columns: rolling_mean_rsrp, rolling_mean_rsrq, rolling_mean_sinr,
                  rolling_std_rsrp, rolling_std_rsrq, rolling_std_sinr.
    Computed within each (device, session_id) group with no leakage across sessions.
    min_periods = max(2, window // 2) — documented choice to balance early-window
    availability against statistical reliability.
    Std of a single value → missing (not 0), enforced by min_periods >= 2.

    Origin: project-overview.md §24 — rolling window statistics.

    Args:
        df: Input DataFrame with numeric ss_rsrp, ss_rsrq, ss_sinr and session_id columns.
        window: Rolling window size in number of samples (default from config).

    Returns:
        DataFrame with added rolling mean and std columns.
    """
    df = df.copy()
    group_cols = ["device", "session_id"] if "session_id" in df.columns else ["device"]
    min_periods = max(2, window // 2)

    for metric, mean_col, std_col in [
        ("ss_rsrp", "rolling_mean_rsrp", "rolling_std_rsrp"),
        ("ss_rsrq", "rolling_mean_rsrq", "rolling_std_rsrq"),
        ("ss_sinr", "rolling_mean_sinr", "rolling_std_sinr"),
    ]:
        if metric in df.columns:
            grouped_rolling = df.groupby(group_cols, observed=True)[metric].transform(
                lambda x: x.rolling(window=window, min_periods=min_periods).mean()
            )
            df[mean_col] = grouped_rolling

            grouped_std = df.groupby(group_cols, observed=True)[metric].transform(
                lambda x: x.rolling(window=window, min_periods=min_periods).std()
            )
            df[std_col] = grouped_std
    return df


def add_persistence(df: pd.DataFrame) -> pd.DataFrame:
    """Compute run-length persistence features for poor signal conditions within sessions.

    Adds columns: weak_rsrp_run, poor_rsrq_run, poor_sinr_run (int >= 0).
    Thresholds defined in ml.config.PERSIST_THRESHOLDS.
    Reset to 0 at session boundaries and whenever a missing value is encountered.

    Origin: project-overview.md §23, todo.md T4-004 — dataset-specific run-length features.

    Args:
        df: Input DataFrame with numeric ss_rsrp, ss_rsrq, ss_sinr and session_id.

    Returns:
        DataFrame with added persistence run-length columns.
    """
    df = df.copy()
    from ml.config import PERSIST_THRESHOLDS

    group_cols = ["device", "session_id"] if "session_id" in df.columns else ["device"]

    mappings = [
        ("ss_rsrp", "weak_rsrp_run", PERSIST_THRESHOLDS["weak_rsrp"]),
        ("ss_rsrq", "poor_rsrq_run", PERSIST_THRESHOLDS["poor_rsrq"]),
        ("ss_sinr", "poor_sinr_run", PERSIST_THRESHOLDS["poor_sinr"]),
    ]

    for metric, run_col, threshold in mappings:
        if metric not in df.columns:
            df[run_col] = 0
            continue

        def calc_run(series: pd.Series, thresh: float = threshold) -> pd.Series:
            runs = []
            curr = 0
            for val in series:
                if pd.isna(val):
                    curr = 0
                elif val < thresh:
                    curr += 1
                else:
                    curr = 0
                runs.append(curr)
            return pd.Series(runs, index=series.index, dtype="int64")

        df[run_col] = df.groupby(group_cols, observed=True)[metric].transform(calc_run)

    return df


def build_features(df: pd.DataFrame, window: int = DEFAULT_WINDOW) -> pd.DataFrame:
    """Compose all feature engineering transformations raw clean -> feature dataset.

    Origin: todo.md T4-005 — build_features pipeline composition.

    Args:
        df: Preprocessed DataFrame conforming to Contract C2.
        window: Rolling window size in number of samples.

    Returns:
        Feature-engineered DataFrame conforming to Contract C3.
    """
    df = add_deltas(df)
    df = add_change_flags(df)
    df = add_rolling(df, window=window)
    df = add_persistence(df)
    return df

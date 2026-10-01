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
        else:
            df[mean_col] = pd.NA
            df[std_col] = pd.NA

    return df

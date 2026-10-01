"""Unit tests for ml/feature_engineering.py."""

import numpy as np
import pandas as pd
import pytest

from ml.feature_engineering import add_change_flags, add_deltas, add_rolling

# ---------------------------------------------------------------------------
# T4-001: add_deltas
# ---------------------------------------------------------------------------


def test_add_deltas_known_sequence():
    """Known sequence (+4,+3,+2,+3,-7) should give deltas (-1,-1,+1,-10)."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 5,
            "session_id": ["s1"] * 5,
            "ss_rsrp": [-80.0, -81.0, -82.0, -81.0, -91.0],  # diffs: -1, -1, +1, -10
            "ss_rsrq": [-10.0, -10.0, -10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0, 20.0, 20.0],
        }
    )
    result = add_deltas(df)

    assert pd.isna(result.loc[0, "delta_rsrp"])  # first sample → missing
    assert result.loc[1, "delta_rsrp"] == pytest.approx(-1.0)
    assert result.loc[2, "delta_rsrp"] == pytest.approx(-1.0)
    assert result.loc[3, "delta_rsrp"] == pytest.approx(1.0)
    assert result.loc[4, "delta_rsrp"] == pytest.approx(-10.0)


def test_add_deltas_no_cross_session():
    """Delta must NOT be computed across session boundaries."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 4,
            "session_id": ["s1", "s1", "s2", "s2"],
            "ss_rsrp": [-80.0, -85.0, -90.0, -95.0],
            "ss_rsrq": [-10.0, -10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0, 20.0],
        }
    )
    result = add_deltas(df)

    assert pd.isna(result.loc[0, "delta_rsrp"])  # first of s1
    assert result.loc[1, "delta_rsrp"] == pytest.approx(-5.0)
    assert pd.isna(result.loc[2, "delta_rsrp"])  # first of s2 → missing, no cross-session
    assert result.loc[3, "delta_rsrp"] == pytest.approx(-5.0)


def test_add_deltas_missing_yields_missing():
    """Missing input must yield missing output, never 0."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 3,
            "session_id": ["s1"] * 3,
            "ss_rsrp": [-80.0, np.nan, -85.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0],
        }
    )
    result = add_deltas(df)

    assert pd.isna(result.loc[1, "delta_rsrp"])  # prev valid, current NaN → NaN
    assert pd.isna(result.loc[2, "delta_rsrp"])  # prev NaN → NaN


# ---------------------------------------------------------------------------
# T4-002: add_change_flags
# ---------------------------------------------------------------------------


def test_add_change_flags_pci_sequence():
    """PCI 336→336→565 should give flags 0, 0, 1."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 3,
            "session_id": ["s1"] * 3,
            "pci": [336, 336, 565],
            "nci": [100, 100, 100],
            "network_type": ["NR", "NR", "NR"],
        }
    )
    result = add_change_flags(df)

    assert list(result["pci_changed"]) == [0, 0, 1]


def test_add_change_flags_session_start():
    """First sample of a new session → 0 for all change flags."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 3,
            "session_id": ["s1", "s2", "s2"],
            "pci": [336, 565, 565],
            "nci": [100, 200, 200],
            "network_type": ["NR", "NR_NSA", "NR_NSA"],
        }
    )
    result = add_change_flags(df)

    assert result.loc[0, "pci_changed"] == 0  # start of s1
    assert result.loc[1, "pci_changed"] == 0  # start of s2
    assert result.loc[1, "network_changed"] == 0


def test_add_change_flags_missing_pci():
    """Missing PCI must not create a change (flag = 0)."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 3,
            "session_id": ["s1"] * 3,
            "pci": pd.array([336, pd.NA, 565], dtype="Int64"),
            "nci": pd.array([100, 100, 100], dtype="Int64"),
            "network_type": ["NR", "NR", "NR"],
        }
    )
    result = add_change_flags(df)

    assert result.loc[1, "pci_changed"] == 0  # missing current → no change
    assert result.loc[2, "pci_changed"] == 0  # missing prev → no change


# ---------------------------------------------------------------------------
# T4-003: add_rolling
# ---------------------------------------------------------------------------


def test_add_rolling_hand_computed():
    """Test rolling mean/std on 5 values with window=3, min_periods=2."""
    values = [-80.0, -82.0, -84.0, -86.0, -88.0]
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 5,
            "session_id": ["s1"] * 5,
            "ss_rsrp": values,
            "ss_rsrq": [-10.0] * 5,
            "ss_sinr": [20.0] * 5,
        }
    )
    result = add_rolling(df, window=3)

    # min_periods = max(2, 3//2) = 2
    # idx 0: only 1 value → NaN (< min_periods)
    assert pd.isna(result.loc[0, "rolling_mean_rsrp"])

    # idx 1: 2 values [-80, -82] → mean = -81.0
    assert result.loc[1, "rolling_mean_rsrp"] == pytest.approx(-81.0)

    # idx 2: 3 values [-80, -82, -84] → mean = -82.0
    assert result.loc[2, "rolling_mean_rsrp"] == pytest.approx(-82.0)

    # idx 3: 3 values [-82, -84, -86] → mean = -84.0
    assert result.loc[3, "rolling_mean_rsrp"] == pytest.approx(-84.0)

    # std of a single value → missing (enforced by min_periods >= 2)
    assert pd.isna(result.loc[0, "rolling_std_rsrp"])

    # std at idx 1: std([-80, -82]) ≈ 1.4142
    assert result.loc[1, "rolling_std_rsrp"] == pytest.approx(
        np.std([-80.0, -82.0], ddof=1), abs=0.01
    )


def test_add_rolling_no_cross_session():
    """Rolling stats must NOT leak across session boundaries."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 4,
            "session_id": ["s1", "s1", "s2", "s2"],
            "ss_rsrp": [-80.0, -82.0, -90.0, -92.0],
            "ss_rsrq": [-10.0, -10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0, 20.0],
        }
    )
    result = add_rolling(df, window=3)

    # s2 first sample (idx 2): only 1 value in session → NaN
    assert pd.isna(result.loc[2, "rolling_mean_rsrp"])

    # s2 second sample (idx 3): 2 values [-90, -92] → mean = -91.0
    assert result.loc[3, "rolling_mean_rsrp"] == pytest.approx(-91.0)


def test_add_rolling_window_respected():
    """Verify the window parameter is used correctly."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 6,
            "session_id": ["s1"] * 6,
            "ss_rsrp": [-80.0, -82.0, -84.0, -86.0, -88.0, -90.0],
            "ss_rsrq": [-10.0] * 6,
            "ss_sinr": [20.0] * 6,
        }
    )

    result_w5 = add_rolling(df, window=5)
    # With window=5, min_periods = max(2, 5//2) = 2
    # idx 4 uses [-80, -82, -84, -86, -88] → mean = -84.0
    assert result_w5.loc[4, "rolling_mean_rsrp"] == pytest.approx(-84.0)
    # idx 5 uses [-82, -84, -86, -88, -90] → mean = -86.0
    assert result_w5.loc[5, "rolling_mean_rsrp"] == pytest.approx(-86.0)

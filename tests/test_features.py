"""Unit tests for feature engineering module per T7-003 specification."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.feature_engineering import (
    add_deltas,
    build_features,
)


def test_deltas_overview_sequence():
    """Verify deltas on known sequence (+4, +3, +2, +3, -7 dB)."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 5,
            "session_id": ["s1"] * 5,
            "ss_sinr": [4.0, 3.0, 2.0, 3.0, -7.0],
            "ss_rsrp": [-80.0] * 5,
            "ss_rsrq": [-10.0] * 5,
        }
    )
    res = add_deltas(df)
    # expected deltas for SINR: [NaN, -1.0, -1.0, +1.0, -10.0]
    assert pd.isna(res.loc[0, "delta_sinr"])
    assert res.loc[1, "delta_sinr"] == pytest.approx(-1.0)
    assert res.loc[2, "delta_sinr"] == pytest.approx(-1.0)
    assert res.loc[3, "delta_sinr"] == pytest.approx(1.0)
    assert res.loc[4, "delta_sinr"] == pytest.approx(-10.0)


def test_session_boundary_features():
    """Verify session boundaries prevent feature leakage across sessions."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 4,
            "session_id": ["s1", "s1", "s2", "s2"],
            "ss_rsrp": [-80.0, -85.0, -100.0, -105.0],
            "ss_rsrq": [-10.0, -10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0, 20.0],
            "pci": [336, 336, 565, 565],
            "nci": [10, 10, 20, 20],
            "network_type": ["NR", "NR", "NR", "NR"],
        }
    )
    res = build_features(df)

    # First sample of s2 must be NaN for deltas and 0 for change flags
    assert pd.isna(res.loc[2, "delta_rsrp"])
    assert res.loc[2, "pci_changed"] == 0
    assert pd.isna(res.loc[2, "rolling_mean_rsrp"])


def test_build_features_determinism():
    """Verify build_features produces identical output hashes on identical inputs."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 5,
            "session_id": ["s1"] * 5,
            "ss_rsrp": [-80.0, -82.0, -84.0, -86.0, -88.0],
            "ss_rsrq": [-10.0] * 5,
            "ss_sinr": [20.0] * 5,
            "pci": [336] * 5,
            "nci": [100] * 5,
            "network_type": ["NR"] * 5,
        }
    )
    res1 = build_features(df.copy())
    res2 = build_features(df.copy())

    pd.testing.assert_frame_equal(res1, res2)

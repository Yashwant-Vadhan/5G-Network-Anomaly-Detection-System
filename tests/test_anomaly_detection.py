"""Unit tests for ml/anomaly_detection.py."""

import pandas as pd
import pytest

from ml.anomaly_detection import baseline_scores


def test_baseline_scores_flat_signal():
    """Flat signal should yield zero z-scores and no flags."""
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 10,
            "session_id": ["s1"] * 10,
            "ss_rsrp": [-80.0] * 10,
            "ss_rsrq": [-10.0] * 10,
            "ss_sinr": [20.0] * 10,
        }
    )
    result = baseline_scores(df, window=5)

    assert result["baseline_z_max"].max() == pytest.approx(0.0)
    assert not result["baseline_flag"].any()


def test_baseline_scores_step_change_flagged():
    """A sudden large step drop in RSRP should be flagged by baseline_scores."""
    # 5 steady samples then a sudden drop to -120.0 dBm
    rsrp = [-80.0, -80.0, -80.0, -80.0, -80.0, -120.0]
    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 6,
            "session_id": ["s1"] * 6,
            "ss_rsrp": rsrp,
            "ss_rsrq": [-10.0] * 6,
            "ss_sinr": [20.0] * 6,
        }
    )
    result = baseline_scores(df, window=5, threshold=2.5)

    # Warmup samples (idx 0..4 with flat signal) have z=0.0
    assert result.loc[0, "baseline_z_rsrp"] == pytest.approx(0.0)

    # Sample at idx 5 (drop to -120) has large z-score and baseline_flag=True
    assert result.loc[5, "baseline_z_rsrp"] > 2.5
    assert result.loc[5, "baseline_flag"]

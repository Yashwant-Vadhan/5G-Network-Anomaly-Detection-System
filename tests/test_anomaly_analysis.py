"""Unit tests for ml/anomaly_analysis.py (T4-011, T4-013)."""

import pandas as pd
import pytest

from ml.anomaly_analysis import is_signal_degradation, is_sudden_degradation


def test_is_sudden_degradation_sinr_sequence():
    """Verify overview §17.2 SINR sequence (+4 -> -10) is detected as sudden degradation."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -86.0, -88.0],
            "ss_rsrq": [-10.0, -11.0, -12.0],
            "ss_sinr": [4.0, 0.0, -10.0],
        }
    )
    assert is_sudden_degradation(df)


def test_low_rsrp_alone_not_degradation():
    """Guardrail G5: Low RSRP alone with steady/good SINR is NOT degradation."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-118.0, -118.0, -118.0, -118.0, -118.0],
            "ss_rsrq": [-14.0, -14.0, -14.0, -14.0, -14.0],
            "ss_sinr": [15.0, 15.0, 15.0, 15.0, 15.0],
        }
    )
    assert not is_signal_degradation(df)
    assert not is_sudden_degradation(df)


def test_slow_noisy_fluctuation_not_sudden():
    """Slow minor noise fluctuation should not trigger sudden degradation."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-90.0, -91.0, -89.0, -90.0, -92.0],
            "ss_rsrq": [-10.0, -11.0, -10.0, -11.0, -10.0],
            "ss_sinr": [12.0, 11.0, 12.0, 10.0, 11.0],
        }
    )
    assert not is_sudden_degradation(df)

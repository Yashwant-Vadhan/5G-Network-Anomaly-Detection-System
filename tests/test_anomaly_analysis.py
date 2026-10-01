"""Unit tests for ml/anomaly_analysis.py (T4-011, T4-013)."""

import pandas as pd
import pytest

from ml.anomaly_analysis import (
    classify_sample,
    is_cell_transition,
    is_combined_anomaly,
    is_persistent_poor,
    is_signal_degradation,
    is_sudden_degradation,
)


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


def test_cell_change_alone_not_anomaly():
    """Guardrail G6: Cell transition alone is classified as CELL_TRANSITION, not anomaly."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [15.0, 15.0, 15.0],
            "pci_changed": [0, 0, 1],
            "nci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
        }
    )
    anomaly_type = classify_sample(df, is_ml_anomaly=False)
    assert anomaly_type == "CELL_TRANSITION"


def test_combined_anomaly_classification():
    """Verify overview §47 sequence (cell transition + degradation) classifies as COMBINED_ANOMALY."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -90.0, -105.0],
            "ss_rsrq": [-10.0, -12.0, -16.0],
            "ss_sinr": [12.0, 4.0, -8.0],
            "pci_changed": [0, 0, 1],
            "nci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
            "weak_rsrp_run": [0, 0, 1],
            "poor_rsrq_run": [0, 0, 1],
            "poor_sinr_run": [0, 0, 1],
        }
    )
    assert is_combined_anomaly(df)
    assert classify_sample(df) == "COMBINED_ANOMALY"


def test_precedence_order():
    """Verify precedence order COMBINED > PERSISTENT > SUDDEN > DEGRADATION > NETWORK > CELL > NORMAL."""
    df_combined = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -100.0, -115.0],
            "ss_rsrq": [-10.0, -15.0, -18.0],
            "ss_sinr": [12.0, 0.0, -10.0],
            "pci_changed": [0, 0, 1],
            "weak_rsrp_run": [0, 0, 3],
        }
    )
    assert classify_sample(df_combined) == "COMBINED_ANOMALY"

    df_persist = pd.DataFrame(
        {
            "ss_rsrp": [-115.0, -115.0, -115.0],
            "ss_rsrq": [-16.0, -16.0, -16.0],
            "ss_sinr": [-2.0, -2.0, -2.0],
            "weak_rsrp_run": [1, 2, 3],
        }
    )
    assert classify_sample(df_persist) == "PERSISTENT_POOR_QUALITY"

    df_sudden = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [15.0, 5.0, -8.0],
        }
    )
    assert classify_sample(df_sudden) == "SUDDEN_SIGNAL_DEGRADATION"

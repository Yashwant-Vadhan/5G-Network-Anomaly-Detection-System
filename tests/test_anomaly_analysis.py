"""Unit tests for ml/anomaly_analysis.py (T4-011, T4-013)."""

import pandas as pd

from ml.anomaly_analysis import (
    classify_sample,
    is_combined_anomaly,
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


def test_estimate_severity_monotonicity():
    """Verify monotonic severity estimation where higher evidence yields higher severity."""
    from ml.anomaly_analysis import estimate_severity

    assert estimate_severity("NORMAL") == "LOW"
    assert estimate_severity("CELL_TRANSITION") == "LOW"
    assert estimate_severity("SIGNAL_DEGRADATION") == "MEDIUM"
    assert estimate_severity("COMBINED_ANOMALY") == "HIGH"
    assert estimate_severity("SIGNAL_DEGRADATION", persist_run=6) == "HIGH"


def test_detect_end_to_end(tmp_path):
    """Verify detect function runs end-to-end and creates scores.csv and events.json."""
    from ml.anomaly_analysis import detect

    df = pd.DataFrame(
        {
            "device": ["Redmi"] * 10,
            "session_id": ["s1"] * 10,
            "timestamp": pd.date_range("2026-09-28T10:00:00Z", periods=10, freq="3s"),
            "ss_rsrp": [-80.0] * 5 + [-120.0] * 5,
            "ss_rsrq": [-10.0] * 10,
            "ss_sinr": [20.0] * 5 + [-5.0] * 5,
            "pci": [336] * 10,
            "nci": [100] * 10,
            "network_type": ["NR"] * 10,
        }
    )

    scores_df, events = detect(df, out_dir=tmp_path, window_size=5)

    assert "anomaly_type" in scores_df.columns
    assert "severity" in scores_df.columns
    assert (tmp_path / "scores.csv").exists()
    assert (tmp_path / "events.json").exists()
    assert isinstance(events, list)

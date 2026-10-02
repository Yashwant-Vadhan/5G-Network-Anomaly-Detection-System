"""Unit tests for classification rules and precedence matrix per T7-005 specification."""

from __future__ import annotations

import pandas as pd
from ml.anomaly_analysis import classify_sample


# ---------------------------------------------------------------------------
# Negative Cases (Guardrails G5 & G6: Not Anomaly Signals on Their Own)
# ---------------------------------------------------------------------------

def test_negative_1_low_rsrp_only():
    """1. Low RSRP alone (-95 dBm, above persistent threshold -110) with steady SINR is NOT an anomaly."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-95.0, -95.0, -95.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0],
            "pci_changed": [0, 0, 0],
            "nci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
            "weak_rsrp_run": [0, 0, 0],
        }
    )
    assert classify_sample(df, is_ml_anomaly=False) in ("NORMAL", "NONE")


def test_negative_2_low_sinr_only():
    """2. Static low SINR alone (-2 dB, above persistent threshold) without downward trend is NOT an anomaly."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [-2.0, -2.0, -2.0],
            "pci_changed": [0, 0, 0],
            "nci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
            "poor_sinr_run": [0, 0, 0],
        }
    )
    assert classify_sample(df, is_ml_anomaly=False) in ("NORMAL", "NONE")


def test_negative_3_pci_change_only():
    """3. PCI change alone is normal cell handover, NOT an anomaly."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0],
            "pci_changed": [0, 0, 1],
            "nci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
        }
    )
    res = classify_sample(df, is_ml_anomaly=False)
    assert res == "CELL_TRANSITION"


def test_negative_4_nci_change_only():
    """4. NCI change alone is normal cell re-selection, NOT an anomaly."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0],
            "pci_changed": [0, 0, 0],
            "nci_changed": [0, 0, 1],
            "network_changed": [0, 0, 0],
        }
    )
    res = classify_sample(df, is_ml_anomaly=False)
    assert res == "CELL_TRANSITION"


def test_negative_5_network_change_only():
    """5. 5G->LTE network state transition alone is an event, NOT an anomaly."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0],
            "pci_changed": [0, 0, 0],
            "nci_changed": [0, 0, 0],
            "network_changed": [0, 0, 1],
        }
    )
    res = classify_sample(df, is_ml_anomaly=False)
    assert res == "NETWORK_STATE_TRANSITION"


def test_negative_6_unknown_deployment_mode_only():
    """6. UNKNOWN deployment mode alone does NOT trigger any anomaly."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_rsrq": [-10.0, -10.0, -10.0],
            "ss_sinr": [20.0, 20.0, 20.0],
            "deployment_mode": ["UNKNOWN", "UNKNOWN", "UNKNOWN"],
            "pci_changed": [0, 0, 0],
            "nci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
        }
    )
    assert classify_sample(df, is_ml_anomaly=False) in ("NORMAL", "NONE")


# ---------------------------------------------------------------------------
# Positive Cases (All 6 Anomaly Categories)
# ---------------------------------------------------------------------------

def test_positive_signal_degradation():
    """Positive test for SIGNAL_DEGRADATION (gradual drop over 4 samples)."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-80.0, -83.0, -86.0, -90.0],  # RSRP drop 10 dB
            "ss_rsrq": [-10.0, -11.0, -12.0, -13.0],
            "ss_sinr": [15.0, 13.0, 11.0, 9.0],       # SINR drop 6 dB (< 10 dB sudden drop threshold)
            "pci_changed": [0, 0, 0, 0],
            "network_changed": [0, 0, 0, 0],
        }
    )
    assert classify_sample(df, is_ml_anomaly=True) == "SIGNAL_DEGRADATION"


def test_positive_sudden_degradation():
    """Positive test for SUDDEN_SIGNAL_DEGRADATION."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -86.0, -87.0],
            "ss_rsrq": [-10.0, -11.0, -12.0],
            "ss_sinr": [10.0, 8.0, -5.0],  # sudden drop >= 10 dB
            "pci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
        }
    )
    assert classify_sample(df, is_ml_anomaly=True) == "SUDDEN_SIGNAL_DEGRADATION"


def test_positive_cell_transition():
    """Positive test for CELL_TRANSITION."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_sinr": [15.0, 15.0, 15.0],
            "pci_changed": [0, 0, 1],
            "network_changed": [0, 0, 0],
        }
    )
    assert classify_sample(df, is_ml_anomaly=False) == "CELL_TRANSITION"


def test_positive_network_state_transition():
    """Positive test for NETWORK_STATE_TRANSITION."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_sinr": [15.0, 15.0, 15.0],
            "pci_changed": [0, 0, 0],
            "network_changed": [0, 0, 1],
        }
    )
    assert classify_sample(df, is_ml_anomaly=False) == "NETWORK_STATE_TRANSITION"


def test_positive_persistent_poor_quality():
    """Positive test for PERSISTENT_POOR_QUALITY."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-115.0, -115.0, -115.0],
            "ss_sinr": [-5.0, -5.0, -5.0],
            "weak_rsrp_run": [1, 2, 3],
            "pci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
        }
    )
    assert classify_sample(df, is_ml_anomaly=True) == "PERSISTENT_POOR_QUALITY"


def test_positive_combined_anomaly():
    """Positive test for COMBINED_ANOMALY."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -95.0, -115.0],
            "ss_rsrq": [-10.0, -14.0, -18.0],
            "ss_sinr": [10.0, 0.0, -10.0],
            "pci_changed": [0, 0, 1],
            "weak_rsrp_run": [0, 0, 1],
        }
    )
    assert classify_sample(df, is_ml_anomaly=True) == "COMBINED_ANOMALY"


# ---------------------------------------------------------------------------
# Precedence Order Matrix
# Order: COMBINED > PERSISTENT > SUDDEN > DEGRADATION > NETWORK > CELL > NORMAL
# ---------------------------------------------------------------------------

def test_precedence_matrix_pairs():
    """Verify precedence order between adjacent priority categories."""
    # COMBINED beats PERSISTENT
    df_combined_vs_persist = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -95.0, -115.0],
            "ss_rsrq": [-10.0, -14.0, -18.0],
            "ss_sinr": [10.0, 0.0, -10.0],
            "pci_changed": [0, 0, 1],
            "weak_rsrp_run": [1, 2, 3],
        }
    )
    assert classify_sample(df_combined_vs_persist, is_ml_anomaly=True) == "COMBINED_ANOMALY"

    # PERSISTENT beats SUDDEN
    df_persist_vs_sudden = pd.DataFrame(
        {
            "ss_rsrp": [-115.0, -115.0, -115.0],
            "ss_sinr": [10.0, 5.0, -10.0],  # sudden drop
            "weak_rsrp_run": [1, 2, 3],     # persistent run
            "pci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
        }
    )
    assert classify_sample(df_persist_vs_sudden, is_ml_anomaly=True) == "PERSISTENT_POOR_QUALITY"

    # SUDDEN beats DEGRADATION
    df_sudden_vs_gradual = pd.DataFrame(
        {
            "ss_rsrp": [-80.0, -85.0, -92.0],  # gradual RSRP drop
            "ss_rsrq": [-10.0, -12.0, -15.0],
            "ss_sinr": [10.0, 8.0, -5.0],      # sudden SINR drop
            "pci_changed": [0, 0, 0],
            "network_changed": [0, 0, 0],
        }
    )
    assert classify_sample(df_sudden_vs_gradual, is_ml_anomaly=True) == "SUDDEN_SIGNAL_DEGRADATION"

    # DEGRADATION beats STATISTICAL_ONLY / NORMAL
    df_gradual = pd.DataFrame(
        {
            "ss_rsrp": [-80.0, -83.0, -86.0, -90.0],
            "ss_rsrq": [-10.0, -11.0, -12.0, -13.0],
            "ss_sinr": [15.0, 13.0, 11.0, 9.0],
            "pci_changed": [0, 0, 0, 0],
            "network_changed": [0, 0, 0, 0],
        }
    )
    assert classify_sample(df_gradual, is_ml_anomaly=True) == "SIGNAL_DEGRADATION"

    # NETWORK beats CELL
    df_network_vs_cell = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -85.0, -85.0],
            "ss_sinr": [15.0, 15.0, 15.0],
            "pci_changed": [0, 0, 1],
            "network_changed": [0, 0, 1],
        }
    )
    assert classify_sample(df_network_vs_cell, is_ml_anomaly=False) == "NETWORK_STATE_TRANSITION"

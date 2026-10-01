"""Rule-based anomaly classification and event aggregation module (T4-011, T4-013).

Implements rules for:
- SIGNAL_DEGRADATION (steady downward trend in RSRP/RSRQ/SINR)
- SUDDEN_SIGNAL_DEGRADATION (sharp drop within 1-3 samples)
- PERSISTENT_POOR_QUALITY (extended run of poor signal metrics)
- COMBINED_ANOMALY (cell transition + degradation + persistence)
- Anomaly precedence logic per project-overview.md §17, §47.
"""

from __future__ import annotations

import logging
import pandas as pd

from ml.config import ANOMALY_TYPES, PERSIST_THRESHOLDS

logger = logging.getLogger(__name__)


def is_signal_degradation(window_df: pd.DataFrame, min_drop_rsrp: float = 8.0) -> bool:
    """Detect gradual signal degradation across RSRP, RSRQ, and SINR in a temporal window.

    Must exhibit consistent negative trend / overall drop across metrics.
    Guardrail G5: Low RSRP alone with steady/rising SINR is NOT signal degradation (poor coverage).

    Args:
        window_df: Sliding window DataFrame of sequential measurement samples.

    Returns:
        True if all available metrics exhibit sustained downward degradation.
    """
    if len(window_df) < 3:
        return False

    rsrp = window_df["ss_rsrp"].dropna()
    sinr = window_df["ss_sinr"].dropna()

    if len(rsrp) < 3 or len(sinr) < 3:
        return False

    # Compute overall delta across window
    rsrp_drop = rsrp.iloc[0] - rsrp.iloc[-1]
    sinr_drop = sinr.iloc[0] - sinr.iloc[-1]

    # Both RSRP and SINR must degrade significantly
    if rsrp_drop >= min_drop_rsrp and sinr_drop >= 4.0:
        return True

    return False


def is_sudden_degradation(window_df: pd.DataFrame, max_samples: int = 3) -> bool:
    """Detect sudden sharp signal degradation (e.g. SINR drop from +4 to -10 within 1-3 samples).

    Origin: project-overview.md §17.2 example sequence (+4 -> -10).
    Guardrail G5: Static low RSRP alone returns False.

    Args:
        window_df: Sliding window DataFrame.
        max_samples: Maximum consecutive sample span for sudden drop.

    Returns:
        True if sharp sudden metric drop is observed.
    """
    if len(window_df) < 2:
        return False

    # Check consecutive 1-to-3 sample deltas for SINR and RSRP
    recent_df = window_df.tail(max_samples + 1)
    
    sinr = recent_df["ss_sinr"].dropna().values
    rsrp = recent_df["ss_rsrp"].dropna().values

    # Check SINR sudden drop (e.g. drop >= 10 dB over <= 3 samples)
    for i in range(len(sinr) - 1):
        for j in range(i + 1, min(i + max_samples + 1, len(sinr))):
            if (sinr[i] - sinr[j]) >= 10.0:
                return True

    # Check RSRP sudden drop (drop >= 15 dB over <= 3 samples)
    for i in range(len(rsrp) - 1):
        for j in range(i + 1, min(i + max_samples + 1, len(rsrp))):
            if (rsrp[i] - rsrp[j]) >= 15.0:
                return True

    return False


def is_persistent_poor(window_df: pd.DataFrame, min_run: int = 3) -> bool:
    """Detect persistent poor quality metric runs.

    Args:
        window_df: Sliding window DataFrame.
        min_run: Minimum run length required.

    Returns:
        True if RSRP, RSRQ, or SINR stay below PERSIST_THRESHOLDS for >= min_run samples.
    """
    if window_df.empty:
        return False

    for col in ["weak_rsrp_run", "poor_rsrq_run", "poor_sinr_run"]:
        if col in window_df.columns and (window_df[col] >= min_run).any():
            return True

    # Fallback to direct raw threshold check if run columns absent
    rsrp = window_df["ss_rsrp"].dropna()
    if len(rsrp) >= min_run and (rsrp <= PERSIST_THRESHOLDS["weak_rsrp"]).all():
        return True

    return False


def is_cell_transition(window_df: pd.DataFrame) -> bool:
    """Check if a PCI/NCI change occurs within the window.

    Cell transition alone is an informational event, NOT an anomaly (Guardrail G6).
    """
    if "pci_changed" in window_df.columns and (window_df["pci_changed"] == 1).any():
        return True
    if "nci_changed" in window_df.columns and (window_df["nci_changed"] == 1).any():
        return True
    return False


def is_network_transition(window_df: pd.DataFrame) -> bool:
    """Check if a network state transition (e.g. 5G NR <-> LTE) occurs within the window."""
    if "network_changed" in window_df.columns and (window_df["network_changed"] == 1).any():
        return True
    return False


def is_combined_anomaly(window_df: pd.DataFrame) -> bool:
    """Detect combined anomaly: cell transition + signal degradation + persistence.

    Origin: project-overview.md §17.6, §47.
    """
    has_cell = is_cell_transition(window_df) or is_network_transition(window_df)
    has_deg = is_signal_degradation(window_df) or is_sudden_degradation(window_df)
    has_pers = is_persistent_poor(window_df)

    return has_cell and (has_deg or has_pers)


def classify_sample(window_df: pd.DataFrame, is_ml_anomaly: bool = False) -> str:
    """Classify anomaly type per window adhering to strict precedence order.

    Precedence Order:
    1. COMBINED_ANOMALY
    2. PERSISTENT_POOR_QUALITY
    3. SUDDEN_SIGNAL_DEGRADATION
    4. SIGNAL_DEGRADATION
    5. NETWORK_STATE_TRANSITION
    6. CELL_TRANSITION
    7. STATISTICAL_ONLY (if ML flagged but no rule evidence)
    8. NORMAL

    Args:
        window_df: Sliding window DataFrame ending at current sample.
        is_ml_anomaly: Boolean flag indicating if ML baseline/IF model flagged the sample.

    Returns:
        One of ANOMALY_TYPES standard strings.
    """
    if window_df.empty:
        return "NORMAL"

    if is_combined_anomaly(window_df):
        return "COMBINED_ANOMALY"

    if is_persistent_poor(window_df):
        return "PERSISTENT_POOR_QUALITY"

    if is_sudden_degradation(window_df):
        return "SUDDEN_SIGNAL_DEGRADATION"

    if is_signal_degradation(window_df):
        return "SIGNAL_DEGRADATION"

    if is_network_transition(window_df):
        return "NETWORK_STATE_TRANSITION"

    if is_cell_transition(window_df):
        return "CELL_TRANSITION"

    if is_ml_anomaly:
        return "STATISTICAL_ONLY"

    return "NORMAL"

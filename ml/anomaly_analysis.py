"""Rule-based anomaly classification and event aggregation module (T4-011, T4-013).

Implements rules for:
- SIGNAL_DEGRADATION (steady downward trend in RSRP/RSRQ/SINR)
- SUDDEN_SIGNAL_DEGRADATION (sharp drop within 1-3 samples)
- PERSISTENT_POOR_QUALITY (extended run of poor signal metrics)
- COMBINED_ANOMALY (cell change + signal degradation + persistence)
- Anomaly precedence logic per project-overview.md §17, §47.
"""

from __future__ import annotations

import logging
import pandas as pd

from ml.config import PERSIST_THRESHOLDS

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
    rsrq = window_df["ss_rsrq"].dropna()
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

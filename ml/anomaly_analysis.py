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
from pathlib import Path

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


def estimate_severity(
    anomaly_type: str,
    if_score: float | None = None,
    z_max: float = 0.0,
    persist_run: int = 0,
) -> str:
    """Estimate anomaly severity (LOW, MEDIUM, HIGH) based on multi-factor evidence.

    Origin: project-overview.md §46, todo.md T4-014.
    Provisional heuristic: monotonic ranking based on anomaly classification,
    ML score intensity, baseline z-score deviation, and persistence length.

    Args:
        anomaly_type: Categorical anomaly type string.
        if_score: Isolation Forest anomaly score in [0, 1].
        z_max: Maximum baseline z-score deviation.
        persist_run: Maximum persistence run length in samples.

    Returns:
        One of "LOW", "MEDIUM", "HIGH".
    """
    if anomaly_type in ("NORMAL", "CELL_TRANSITION", "NETWORK_STATE_TRANSITION"):
        return "LOW"

    if (
        anomaly_type == "COMBINED_ANOMALY"
        or persist_run >= 5
        or z_max >= 4.0
        or (if_score is not None and if_score >= 0.8)
    ):
        return "HIGH"

    if (
        anomaly_type in ("SUDDEN_SIGNAL_DEGRADATION", "PERSISTENT_POOR_QUALITY")
        or z_max >= 3.0
        or (if_score is not None and if_score >= 0.65)
    ):
        return "MEDIUM"

    if anomaly_type in ("SIGNAL_DEGRADATION", "STATISTICAL_ONLY"):
        return "MEDIUM"

    return "LOW"


def detect(
    df: pd.DataFrame,
    out_dir: str | Path = "data/processed",
    window_size: int = 10,
) -> tuple[pd.DataFrame, list[dict]]:
    """Execute end-to-end anomaly detection pipeline and group contiguous events.

    Origin: project-overview.md §23-25, contract C4, todo.md T4-015.

    Args:
        df: Input DataFrame with C2/C3 preprocessed and feature columns.
        out_dir: Output path directory for scores.csv and events.json.
        window_size: Sliding window size for rule classification.

    Returns:
        Tuple of (scores_df, events_list).
    """
    import json
    from pathlib import Path

    import joblib

    from ml.anomaly_detection import baseline_scores, if_scores
    from ml.config import MODELS_DIR
    from ml.feature_engineering import build_features

    df = build_features(df)
    df = baseline_scores(df)

    # Load model and scaler if present to calculate IF scores
    model_path = Path(MODELS_DIR) / "if_v1.joblib"
    scaler_path = Path(MODELS_DIR) / "scaler.joblib"
    if model_path.exists() and scaler_path.exists():
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        df = if_scores(df, model=model, scaler=scaler)
    else:
        df["if_score"] = pd.NA
        df["if_flag"] = False

    anomaly_types = []
    severities = []

    for idx in range(len(df)):
        start_idx = max(0, idx - window_size + 1)
        sub_df = df.iloc[start_idx : idx + 1]

        is_ml = bool(df.iloc[idx].get("baseline_flag", False) or df.iloc[idx].get("if_flag", False))
        atype = classify_sample(sub_df, is_ml_anomaly=is_ml)

        if_val = df.iloc[idx].get("if_score")
        if_val_float = float(if_val) if pd.notna(if_val) else None
        z_val = float(df.iloc[idx].get("baseline_z_max", 0.0))

        run_val = 0
        for rcol in ["weak_rsrp_run", "poor_rsrq_run", "poor_sinr_run"]:
            if rcol in df.columns and pd.notna(df.iloc[idx][rcol]):
                run_val = max(run_val, int(df.iloc[idx][rcol]))

        sev = estimate_severity(atype, if_score=if_val_float, z_max=z_val, persist_run=run_val)

        anomaly_types.append(atype)
        severities.append(sev)

    df["anomaly_type"] = anomaly_types
    df["severity"] = severities

    df["event_id"] = None

    # Group contiguous events
    events = []
    event_id_counter = 1

    # Anomaly flag if not NORMAL and not simple CELL/NETWORK event
    is_anom = df["anomaly_type"].isin(
        [
            "SIGNAL_DEGRADATION",
            "SUDDEN_SIGNAL_DEGRADATION",
            "PERSISTENT_POOR_QUALITY",
            "COMBINED_ANOMALY",
            "STATISTICAL_ONLY",
        ]
    )

    df["is_anom"] = is_anom

    for session_id, group in df.groupby("session_id", sort=False):
        group = group.sort_values("timestamp")
        in_event = False
        event_rows = []

        for row_idx, row in group.iterrows():
            if row["is_anom"]:
                if not in_event:
                    in_event = True
                    event_rows = [(row_idx, row)]
                else:
                    event_rows.append((row_idx, row))
            else:
                if in_event:
                    # Close event
                    event_indices = [r[0] for r in event_rows]
                    event_df = pd.DataFrame([r[1] for r in event_rows])
                    evt_id = f"evt-{event_id_counter:03d}"
                    df.loc[event_indices, "event_id"] = evt_id
                    evt = {
                        "event_id": evt_id,
                        "session_id": session_id,
                        "device": str(event_df["device"].iloc[0]),
                        "start_time": str(event_df["timestamp"].iloc[0]),
                        "end_time": str(event_df["timestamp"].iloc[-1]),
                        "sample_count": len(event_df),
                        "anomaly_type": str(event_df["anomaly_type"].mode().iloc[0]),
                        "max_severity": str(
                            "HIGH"
                            if "HIGH" in event_df["severity"].values
                            else ("MEDIUM" if "MEDIUM" in event_df["severity"].values else "LOW")
                        ),
                    }
                    events.append(evt)
                    event_id_counter += 1
                    in_event = False
                    event_rows = []

        if in_event and event_rows:
            event_indices = [r[0] for r in event_rows]
            event_df = pd.DataFrame([r[1] for r in event_rows])
            evt_id = f"evt-{event_id_counter:03d}"
            df.loc[event_indices, "event_id"] = evt_id
            evt = {
                "event_id": evt_id,
                "session_id": session_id,
                "device": str(event_df["device"].iloc[0]),
                "start_time": str(event_df["timestamp"].iloc[0]),
                "end_time": str(event_df["timestamp"].iloc[-1]),
                "sample_count": len(event_df),
                "anomaly_type": str(event_df["anomaly_type"].mode().iloc[0]),
                "max_severity": str(
                    "HIGH"
                    if "HIGH" in event_df["severity"].values
                    else ("MEDIUM" if "MEDIUM" in event_df["severity"].values else "LOW")
                ),
            }
            events.append(evt)
            event_id_counter += 1

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    scores_csv = out_path / "scores.csv"
    df.to_csv(scores_csv, index=False)

    events_json = out_path / "events.json"
    with open(events_json, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    logger.info("Saved scores to %s and %d events to %s", scores_csv, len(events), events_json)
    return df, events

"""Real-time streaming ML feature engineering, scoring, and classification (T11-003, T11-005).

Executes incremental preprocessing, feature engineering, statistical baseline
scoring, Isolation Forest scoring, and rule-based anomaly classification on
incoming sample buffers by directly reusing the core batch pipeline functions.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.anomaly_analysis import classify_sample, estimate_severity
from ml.anomaly_detection import (
    baseline_scores,
    if_scores,
    load_model_and_scaler,
)
from ml.config import (
    DEFAULT_WINDOW,
    DEPLOYMENT_MODES,
    MODELS_DIR,
)
from ml.feature_engineering import build_features
from ml.preprocessing import (
    add_missing_flags,
    coerce_numeric,
    flag_invalid,
    parse_timestamps,
)
from ml.schema import (
    SchemaError,
    assert_no_pii_columns,
    validate_raw_columns,
)
from streaming.schema import IngestPayload, IngestSample, ScoredSample
from streaming.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _clean_val(val: Any) -> Any:
    """Convert pandas/numpy NA and NaN to Python None for Pydantic model compatibility."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (np.floating, float)):
        return float(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    return val


def coerce_sample(payload: IngestPayload | dict[str, Any]) -> pd.DataFrame:
    """Build a one-row Contract C1 DataFrame and coerce it via batch preprocessing.

    Reuses existing ml.schema validation and ml.preprocessing functions:
    - Verifies raw C1 columns and rejects forbidden PII columns.
    - Validates deployment_mode against DEPLOYMENT_MODES.
    - Converts 'NA' tokens and sentinel integers to missing (never 0).
    - Preserves 64-bit precision for large NCI values.
    - Flags invalid signal ranges without dropping rows.
    - Adds csi_available and model_eligible policy flags.

    Args:
        payload: IngestPayload model instance or raw dictionary containing 18 C1 fields.

    Returns:
        Single-row pandas DataFrame matching Contract C2 schema and types.

    Raises:
        SchemaError: If columns are missing/extra, PII is detected, deployment_mode
            is invalid, or timestamp cannot be parsed.
    """
    if isinstance(payload, IngestPayload):
        raw_dict = payload.model_dump()
    elif isinstance(payload, dict):
        raw_dict = dict(payload)
    else:
        raise TypeError(f"Expected IngestPayload or dict, got {type(payload).__name__}")

    # Build one-row raw DataFrame
    df = pd.DataFrame([raw_dict])

    # Validate raw C1 column structure and ensure no PII fields (overview §49)
    assert_no_pii_columns(df)
    validate_raw_columns(df)

    # Validate deployment_mode against allowed values
    mode = str(df["deployment_mode"].iloc[0])
    if mode not in DEPLOYMENT_MODES:
        raise SchemaError(f"Invalid deployment_mode '{mode}'; expected one of {DEPLOYMENT_MODES}")

    # Parse timestamps using the batch mixed-format parser
    clean_df, rejected_df = parse_timestamps(df)
    if not rejected_df.empty:
        raise SchemaError(f"Unparseable timestamp: '{raw_dict.get('timestamp')}'")

    # Coerce numeric types, sentinels, and NA tokens via batch code (G3)
    coerced = coerce_numeric(clean_df)

    # Flag out-of-range signal metrics per VALID_RANGES
    flagged = flag_invalid(coerced)

    # Compute csi_available and model_eligible policy flags
    result = add_missing_flags(flagged)

    if "is_synthetic" not in result.columns:
        result["is_synthetic"] = False

    return result


class StreamingEngine:
    """Incremental scoring and anomaly detection engine for real-time telemetry.

    Reuses batch pipeline functions (build_features, baseline_scores, if_scores,
    classify_sample, estimate_severity) on a per-session sliding buffer.
    """

    def __init__(
        self,
        models_dir: Path | str = MODELS_DIR,
        session_manager: SessionManager | None = None,
        window_size: int = DEFAULT_WINDOW,
    ) -> None:
        self.models_dir = Path(models_dir)
        self.window_size = window_size
        self.session_manager = session_manager or SessionManager()

        # Load and verify model metadata and artifacts once at startup (G17 / T10-013)
        self.model, self.scaler = load_model_and_scaler(self.models_dir)

    def process(
        self,
        sample: IngestSample | dict[str, Any],
        client_id: str | None = None,
        session_id: str | None = None,
        received_at: str | None = None,
    ) -> ScoredSample:
        """Process incoming ingest sample through buffer, features, scoring, and classification.

        Args:
            sample: IngestSample instance or raw dictionary.
            client_id: Optional client ID override (defaults to device name).
            session_id: Optional explicit session ID override.
            received_at: Optional ISO-8601 server receipt timestamp.

        Returns:
            ScoredSample adhering to Contract C4 and C8 specifications.
        """
        now_iso = datetime.now(UTC).isoformat()
        rec_time = received_at or now_iso

        # Extract sequence and payload
        edge_if_score: float | None = None
        if isinstance(sample, IngestSample):
            seq = sample.seq
            payload = sample.payload
            cid = client_id or sample.payload.device
            if sample.edge is not None:
                edge_if_score = sample.edge.if_score
        elif isinstance(sample, dict):
            seq = int(sample.get("seq", 0))
            payload = sample.get("payload", sample)
            cid = client_id or (
                payload.get("device", "device") if isinstance(payload, dict) else "device"
            )
            edge = sample.get("edge")
            if isinstance(edge, dict):
                edge_if_score = edge.get("if_score")
        else:
            raise TypeError(f"Expected IngestSample or dict, got {type(sample).__name__}")

        # 1. Coerce and validate sample via batch preprocessing logic
        coerced_df = coerce_sample(payload)
        coerced_row = coerced_df.iloc[0]

        # 2. Append to session buffer
        buffer, _ = self.session_manager.append_sample(
            client_id=cid,
            row=coerced_row,
            seq=seq,
            session_id=session_id,
        )

        # 3. Compute features on session buffer (no fillna / interpolation per G2)
        buf_df = buffer.to_dataframe()
        feat_df = build_features(buf_df, window=self.window_size)

        # 4. Compute baseline scores and Isolation Forest scores
        scored_df = baseline_scores(feat_df, window=self.window_size)
        scored_df = if_scores(scored_df, model=self.model, scaler=self.scaler)

        # 5. Classify and estimate severity on current sliding window
        curr_idx = len(scored_df) - 1
        start_idx = max(0, curr_idx - self.window_size + 1)
        sub_df = scored_df.iloc[start_idx : curr_idx + 1]
        curr_row = scored_df.iloc[curr_idx]

        is_ml = bool(curr_row.get("baseline_flag", False) or curr_row.get("if_flag", False))
        anomaly_type = classify_sample(sub_df, is_ml_anomaly=is_ml)

        if_val = curr_row.get("if_score")
        if_val_float = float(if_val) if pd.notna(if_val) else None
        z_val = float(curr_row.get("baseline_z_max", 0.0))

        run_val = 0
        for rcol in ["weak_rsrp_run", "poor_rsrq_run", "poor_sinr_run"]:
            if rcol in scored_df.columns and pd.notna(curr_row.get(rcol)):
                run_val = max(run_val, int(curr_row[rcol]))

        severity = estimate_severity(
            anomaly_type,
            if_score=if_val_float,
            z_max=z_val,
            persist_run=run_val,
        )

        is_anom = anomaly_type in {
            "SIGNAL_DEGRADATION",
            "SUDDEN_SIGNAL_DEGRADATION",
            "PERSISTENT_POOR_QUALITY",
            "COMBINED_ANOMALY",
            "STATISTICAL_ONLY",
        }

        score_time = datetime.now(UTC).isoformat()
        pub_time = score_time

        edge_divergence = (
            abs(edge_if_score - if_val_float)
            if (edge_if_score is not None and if_val_float is not None)
            else None
        )

        # Extract timestamp string for Contract C8
        ts_val = curr_row.get("timestamp")
        ts_str = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val)

        return ScoredSample(
            # Raw measurement columns
            timestamp=ts_str,
            device=str(curr_row.get("device", "device")),
            manufacturer=_clean_val(curr_row.get("manufacturer")),
            android=str(_clean_val(curr_row.get("android")))
            if _clean_val(curr_row.get("android")) is not None
            else None,
            operator=_clean_val(curr_row.get("operator")),
            network_type=_clean_val(curr_row.get("network_type")),
            deployment_mode=_clean_val(curr_row.get("deployment_mode")),
            display_override=_clean_val(curr_row.get("display_override")),
            registered=_clean_val(curr_row.get("registered")),
            ss_rsrp=_clean_val(curr_row.get("ss_rsrp")),
            ss_rsrq=_clean_val(curr_row.get("ss_rsrq")),
            ss_sinr=_clean_val(curr_row.get("ss_sinr")),
            csi_rsrp=_clean_val(curr_row.get("csi_rsrp")),
            csi_rsrq=_clean_val(curr_row.get("csi_rsrq")),
            csi_sinr=_clean_val(curr_row.get("csi_sinr")),
            pci=_clean_val(curr_row.get("pci")),
            nci=_clean_val(curr_row.get("nci")),
            nrarfcn=_clean_val(curr_row.get("nrarfcn")),
            # Session & validity flags
            session_id=str(session_id or curr_row.get("session_id", buffer.session_id)),
            sample_idx=int(curr_row.get("sample_idx", curr_idx)),
            is_valid=bool(curr_row.get("is_valid", True)),
            model_eligible=bool(curr_row.get("model_eligible", True)),
            csi_available=bool(curr_row.get("csi_available", False)),
            is_synthetic=bool(curr_row.get("is_synthetic", False)),
            source_file=_clean_val(curr_row.get("source_file")),
            dup_ts=bool(curr_row.get("dup_ts", False)),
            # Features
            delta_rsrp=_clean_val(curr_row.get("delta_rsrp")),
            delta_rsrq=_clean_val(curr_row.get("delta_rsrq")),
            delta_sinr=_clean_val(curr_row.get("delta_sinr")),
            pci_changed=_clean_val(curr_row.get("pci_changed")),
            nci_changed=_clean_val(curr_row.get("nci_changed")),
            network_changed=_clean_val(curr_row.get("network_changed")),
            rolling_mean_rsrp=_clean_val(curr_row.get("rolling_mean_rsrp")),
            rolling_std_rsrp=_clean_val(curr_row.get("rolling_std_rsrp")),
            rolling_mean_rsrq=_clean_val(curr_row.get("rolling_mean_rsrq")),
            rolling_std_rsrq=_clean_val(curr_row.get("rolling_std_rsrq")),
            rolling_mean_sinr=_clean_val(curr_row.get("rolling_mean_sinr")),
            rolling_std_sinr=_clean_val(curr_row.get("rolling_std_sinr")),
            weak_rsrp_run=_clean_val(curr_row.get("weak_rsrp_run")),
            poor_rsrq_run=_clean_val(curr_row.get("poor_rsrq_run")),
            poor_sinr_run=_clean_val(curr_row.get("poor_sinr_run")),
            # Scores & anomaly classification
            baseline_z_rsrp=_clean_val(curr_row.get("baseline_z_rsrp")),
            baseline_z_rsrq=_clean_val(curr_row.get("baseline_z_rsrq")),
            baseline_z_sinr=_clean_val(curr_row.get("baseline_z_sinr")),
            baseline_z_max=_clean_val(curr_row.get("baseline_z_max")),
            baseline_flag=bool(curr_row.get("baseline_flag", False)),
            if_score=if_val_float,
            if_flag=bool(curr_row.get("if_flag", False)),
            anomaly_type=anomaly_type,
            severity=severity,
            event_id=_clean_val(curr_row.get("event_id")),
            is_anom=is_anom,
            # Streaming C8 metadata
            seq=seq,
            received_at=rec_time,
            scored_at=score_time,
            published_at=pub_time,
            edge_if_score=edge_if_score,
            edge_divergence=edge_divergence,
        )

"""Training module for 5G-NADS Isolation Forest model (T4-008).

Trains IsolationForest model with provenance metadata per project-overview.md §23-24,
todo.md T4-008, and Guardrail G11 (real data only unless explicit flag).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Sequence

import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest

from ml.config import FEATURE_COLUMNS, MODELS_DIR, RANDOM_STATE
from ml.scaler import fit_scaler, transform_features

logger = logging.getLogger(__name__)


def compute_df_sha256(df: pd.DataFrame) -> str:
    """Compute SHA-256 hash of DataFrame representation for data provenance."""
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def train_iforest(
    df: pd.DataFrame,
    out_dir: Path | str = MODELS_DIR,
    feature_cols: Sequence[str] = FEATURE_COLUMNS,
    n_estimators: int = 100,
    contamination: float = 0.05,
    allow_synthetic: bool = False,
) -> tuple[IsolationForest, Path, Path]:
    """Train Isolation Forest anomaly detection model on real eligible data.

    Args:
        df: Input features DataFrame containing feature_cols and model_eligible.
        out_dir: Directory path to save model and metadata artifacts.
        feature_cols: Features list used for training.
        n_estimators: Number of trees in IsolationForest.
        contamination: Expected anomaly fraction contamination rate.
        allow_synthetic: Explicit override flag allowing synthetic rows (Guardrail G11).

    Returns:
        Tuple of (trained IsolationForest model, Path to model file, Path to metadata file).
    """
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # Check for synthetic data (Guardrail G11)
    if "is_synthetic" in df.columns:
        synthetic_count = df["is_synthetic"].fillna(False).astype(bool).sum()
        if synthetic_count > 0 and not allow_synthetic:
            raise ValueError(
                f"Training dataset contains {synthetic_count} synthetic samples, "
                "which is forbidden by Guardrail G11 unless allow_synthetic=True."
            )

    # Fit feature scaler on eligible rows
    scaler, _ = fit_scaler(df, feature_cols=feature_cols, out_dir=out_dir_path)

    # Prepare training dataset
    eligible_mask = df["model_eligible"].fillna(False) if "model_eligible" in df.columns else pd.Series(True, index=df.index)
    feat_df = df.loc[eligible_mask, list(feature_cols)]
    valid_mask = feat_df.notna().all(axis=1)
    train_df = feat_df.loc[valid_mask]

    if train_df.empty:
        raise ValueError("No valid eligible samples available to train IsolationForest.")

    # Scale training features
    scaled_train_X = scaler.transform(train_df.values)

    # Fit IsolationForest model
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(scaled_train_X)

    # File paths
    model_path = out_dir_path / "if_v1.joblib"
    meta_path = out_dir_path / "if_v1.meta.json"

    # Save model
    joblib.dump(model, model_path)

    # Compute provenance metadata
    data_sha256 = compute_df_sha256(train_df)
    meta = {
        "model_name": "if_v1",
        "feature_columns": list(feature_cols),
        "random_state": RANDOM_STATE,
        "n_estimators": n_estimators,
        "contamination": contamination,
        "sklearn_version": sklearn.__version__,
        "training_rows": len(train_df),
        "training_data_sha256": data_sha256,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    logger.info("Trained IsolationForest model on %d rows, saved to %s", len(train_df), model_path)

    return model, model_path, meta_path

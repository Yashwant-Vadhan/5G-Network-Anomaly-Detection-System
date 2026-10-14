"""Training module for 5G-NADS Isolation Forest model (T4-008).

Trains IsolationForest model with provenance metadata per project-overview.md §23-24,
todo.md T4-008, and Guardrail G11 (real data only unless explicit flag).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ml.config import FEATURE_COLUMNS, MODELS_DIR, RANDOM_STATE
from ml.scaler import fit_scaler
from ml.schema import ConfigError

logger = logging.getLogger(__name__)


def compute_df_sha256(df: pd.DataFrame) -> str:
    """Compute SHA-256 hash of DataFrame representation for data provenance."""
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def compute_feature_hash(feature_cols: Sequence[str] = FEATURE_COLUMNS) -> str:
    """Compute SHA-256 hash of ordered feature columns."""
    feat_bytes = ",".join(feature_cols).encode("utf-8")
    return hashlib.sha256(feat_bytes).hexdigest()


def compute_file_sha256(path: Path | str) -> str:
    """Compute SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def update_model_metadata(
    meta_path: Path | str = MODELS_DIR / "if_v1.meta.json",
    model_path: Path | str = MODELS_DIR / "if_v1.joblib",
    scaler_path: Path | str = MODELS_DIR / "scaler.joblib",
    model_version: str = "1.0.0",
    feature_cols: Sequence[str] = FEATURE_COLUMNS,
) -> dict:
    """Update or enrich model metadata JSON with version and integrity hashes."""
    meta_p = Path(meta_path)
    model_p = Path(model_path)
    scaler_p = Path(scaler_path)

    if meta_p.exists():
        with open(meta_p, encoding="utf-8") as f:
            meta = json.load(f)
    else:
        meta = {}

    feat_cols = (
        list(feature_cols)
        if feature_cols
        else meta.get("feature_columns", list(FEATURE_COLUMNS))
    )
    meta["model_name"] = meta.get("model_name", "if_v1")
    meta["model_version"] = model_version
    meta["feature_columns"] = feat_cols
    meta["feature_hash"] = compute_feature_hash(feat_cols)
    if model_p.exists():
        meta["model_sha256"] = compute_file_sha256(model_p)
    if scaler_p.exists():
        meta["scaler_sha256"] = compute_file_sha256(scaler_p)

    with open(meta_p, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def verify_model_metadata(
    models_dir: Path | str = MODELS_DIR,
    expected_feature_cols: Sequence[str] = FEATURE_COLUMNS,
) -> dict:
    """Validate model metadata integrity and feature alignment, raising ConfigError on mismatch."""
    models_path = Path(models_dir)
    meta_path = models_path / "if_v1.meta.json"
    if not meta_path.exists():
        raise ConfigError(f"Model metadata file missing at {meta_path}")

    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as exc:
        raise ConfigError(f"Failed to read model metadata: {exc}") from exc

    feat_cols = meta.get("feature_columns")
    if feat_cols != list(expected_feature_cols):
        raise ConfigError(
            f"Model feature columns mismatch. "
            f"Expected {list(expected_feature_cols)}, got {feat_cols}"
        )

    expected_hash = compute_feature_hash(expected_feature_cols)
    actual_hash = meta.get("feature_hash")
    if actual_hash != expected_hash:
        raise ConfigError(
            f"Model feature_hash mismatch. Expected {expected_hash}, got {actual_hash}"
        )

    # Verify model and scaler SHA-256 hashes if recorded
    model_path = models_path / "if_v1.joblib"
    if "model_sha256" in meta and model_path.exists():
        actual_model_sha = compute_file_sha256(model_path)
        if actual_model_sha != meta["model_sha256"]:
            raise ConfigError(
                f"Model file SHA-256 mismatch: "
                f"expected {meta['model_sha256']}, got {actual_model_sha}"
            )

    scaler_path = models_path / "scaler.joblib"
    if "scaler_sha256" in meta and scaler_path.exists():
        actual_scaler_sha = compute_file_sha256(scaler_path)
        if actual_scaler_sha != meta["scaler_sha256"]:
            raise ConfigError(
                f"Scaler file SHA-256 mismatch: "
                f"expected {meta['scaler_sha256']}, got {actual_scaler_sha}"
            )

    return meta


def load_model_and_scaler(
    models_dir: Path | str = MODELS_DIR,
) -> tuple[IsolationForest, StandardScaler, dict]:
    """Verify metadata integrity and load Isolation Forest model and StandardScaler."""
    models_path = Path(models_dir)
    meta = verify_model_metadata(models_path)

    model_path = models_path / "if_v1.joblib"
    if not model_path.exists():
        raise ConfigError(f"Model file not found at {model_path}")
    scaler_path = models_path / "scaler.joblib"
    if not scaler_path.exists():
        raise ConfigError(f"Scaler file not found at {scaler_path}")

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    return model, scaler, meta


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
    eligible_mask = (
        df["model_eligible"].fillna(False)
        if "model_eligible" in df.columns
        else pd.Series(True, index=df.index)
    )
    feat_df = df.loc[eligible_mask, list(feature_cols)]
    valid_mask = feat_df.notna().all(axis=1)
    train_df = feat_df.loc[valid_mask]

    if train_df.empty:
        raise ValueError("No valid eligible samples available to train IsolationForest.")

    # Scale training features
    scaled_train_x = scaler.transform(train_df.values)

    # Fit IsolationForest model
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(scaled_train_x)

    # File paths
    model_path = out_dir_path / "if_v1.joblib"
    meta_path = out_dir_path / "if_v1.meta.json"

    # Save model
    joblib.dump(model, model_path)

    # Compute provenance metadata
    data_sha256 = compute_df_sha256(train_df)
    scaler_path = out_dir_path / "scaler.joblib"
    meta = {
        "model_name": "if_v1",
        "model_version": "1.0.0",
        "feature_columns": list(feature_cols),
        "feature_hash": compute_feature_hash(feature_cols),
        "model_sha256": compute_file_sha256(model_path),
        "scaler_sha256": compute_file_sha256(scaler_path) if scaler_path.exists() else None,
        "random_state": RANDOM_STATE,
        "n_estimators": n_estimators,
        "contamination": contamination,
        "sklearn_version": sklearn.__version__,
        "training_rows": len(train_df),
        "training_data_sha256": data_sha256,
        "created_at": datetime.now(UTC).isoformat(),
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    logger.info("Trained IsolationForest model on %d rows, saved to %s", len(train_df), model_path)

    return model, model_path, meta_path

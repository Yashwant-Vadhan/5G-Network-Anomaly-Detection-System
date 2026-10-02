"""End-to-End Pipeline CLI for 5G-NADS (T7-001).

Runs full automated pipeline:
1. Verify raw data manifest (if present).
2. Preprocess raw CSVs -> measurements_clean.csv (Contract C2) & preprocess_log.json.
3. Engineer temporal features -> features.csv (Contract C3).
4. Train Isolation Forest model if needed or requested (--retrain).
5. Detect anomalies & classify -> scores.csv (Contract C4) & events.json.
6. Execute multi-agent diagnostic layer -> events_diagnosed.json (Contract C5).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from agents.orchestrator import run_all_events, write_events_diagnosed
from ml.anomaly_analysis import detect
from ml.config import MODELS_DIR
from ml.feature_engineering import build_features
from ml.preprocessing import preprocess
from ml.schema import ConfigError, DataQualityError, SchemaError
from ml.train import train_iforest
from scripts.make_manifest import verify_manifest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline(
    input_dir: Path | str,
    output_dir: Path | str,
    retrain: bool = False,
) -> tuple[Path, Path, Path, Path]:
    """Execute end-to-end 5G-NADS processing pipeline.

    Args:
        input_dir: Input directory containing raw CSV measurements.
        output_dir: Output directory for processed dataset artifacts.
        retrain: Force retraining of Isolation Forest model.

    Returns:
        Tuple of (measurements_clean_path, features_path, scores_path, events_diagnosed_path).
    """
    in_path = Path(input_dir)
    out_path = Path(output_dir)

    if not in_path.exists():
        raise ConfigError(f"Input directory '{in_path}' does not exist.")

    # 1. Manifest verification (if present)
    manifest_file = in_path / "MANIFEST.sha256"
    if manifest_file.exists():
        logger.info("Verifying raw data manifest at %s...", manifest_file)
        if not verify_manifest(in_path):
            logger.warning("Manifest checksum verification failed or reported missing files.")
    else:
        logger.info("No MANIFEST.sha256 found in %s; skipping verification.", in_path)

    # 2. Preprocessing
    logger.info("Starting preprocessing step on %s...", in_path)
    clean_df = preprocess(in_path, out_path)
    logger.info("Preprocessing complete: %d rows produced.", len(clean_df))

    # 3. Feature Engineering
    logger.info("Starting feature engineering step...")
    features_df = build_features(clean_df)
    features_csv = out_path / "features.csv"
    features_df.to_csv(features_csv, index=False)
    logger.info(
        "Feature engineering complete: %d feature rows written to %s.",
        len(features_df),
        features_csv,
    )

    # 4. Model Training (if retrain requested or model missing)
    model_file = Path(MODELS_DIR) / "if_v1.joblib"
    scaler_file = Path(MODELS_DIR) / "scaler.joblib"

    if retrain or not (model_file.exists() and scaler_file.exists()):
        logger.info("Training Isolation Forest model...")
        train_iforest(features_df, out_dir=MODELS_DIR)
        logger.info("Model training complete.")
    else:
        logger.info("Existing model found at %s; skipping training.", model_file)

    # 5. Detection & Classification
    logger.info("Executing anomaly detection and rule classification...")
    scores_df, events = detect(features_df, out_dir=out_path)
    logger.info(
        "Detection complete: %d scored samples, %d candidate events.",
        len(scores_df),
        len(events),
    )

    # 6. Multi-Agent Diagnostic Layer
    logger.info("Running multi-agent diagnostic layer on %d events...", len(events))
    diagnosed_events = run_all_events(scores_df, events)
    events_diagnosed_file = out_path / "events_diagnosed.json"
    write_events_diagnosed(diagnosed_events, events_diagnosed_file)
    logger.info("Multi-agent diagnosis complete: written to %s.", events_diagnosed_file)

    clean_csv = out_path / "measurements_clean.csv"
    scores_csv = out_path / "scores.csv"

    return clean_csv, features_csv, scores_csv, events_diagnosed_file


def main() -> None:
    """CLI entrypoint for run_pipeline."""
    parser = argparse.ArgumentParser(
        description="Run end-to-end 5G-NADS anomaly detection and multi-agent pipeline.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/raw",
        help="Input directory containing raw CSV measurements (default: data/raw).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/processed",
        help="Output directory for processed CSV and JSON artifacts (default: data/processed).",
    )
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Force retraining of Isolation Forest model on input features.",
    )

    args = parser.parse_args()

    try:
        run_pipeline(input_dir=args.input, output_dir=args.output, retrain=args.retrain)
        print("Pipeline execution succeeded.")
    except (SchemaError, DataQualityError, ConfigError) as exc:
        print(f"Pipeline Error: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"Unexpected Pipeline Exception: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build demo data bundle for the static React dashboard (Contract C11, T16-002).

Usage:
    python scripts/build_demo_bundle.py --source processed --out frontend/public/demo-bundle.json
    python scripts/build_demo_bundle.py --source sample --out frontend/public/demo-bundle.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path for direct CLI execution
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml.transitions import compute_transitions  # noqa: E402
from pipelines.run_pipeline import run_pipeline  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Columns used by dashboard per docs/inventory/dashboard_inventory.md §4
DASHBOARD_SAMPLE_COLUMNS = [
    "timestamp",
    "device",
    "operator",
    "network_type",
    "deployment_mode",
    "registered",
    "ss_rsrp",
    "ss_rsrq",
    "ss_sinr",
    "pci",
    "nci",
    "nrarfcn",
    "session_id",
    "sample_idx",
    "is_anom",
    "anomaly_type",
    "severity",
    "baseline_flag",
    "if_flag",
    "if_score",
]


def clean_json_value(val: Any) -> Any:
    """Convert pandas/numpy NaN and numpy scalar types to standard JSON-compatible Python types."""
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        return float(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    return str(val)


def extract_sessions(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Extract session metadata summary from scored DataFrame."""
    if "session_id" not in df.columns or df.empty:
        return []

    sessions: list[dict[str, Any]] = []
    for session_id, group in df.groupby("session_id", sort=False):
        row_0 = group.iloc[0]
        row_last = group.iloc[-1]
        sessions.append(
            {
                "session_id": str(session_id),
                "device": str(row_0.get("device", "Unknown")),
                "operator": str(row_0.get("operator", "Unknown")),
                "n": int(len(group)),
                "start": str(row_0.get("timestamp", "")),
                "end": str(row_last.get("timestamp", "")),
            }
        )
    return sessions


def build_samples_block(df: pd.DataFrame) -> dict[str, Any]:
    """Build columnar samples block matching Contract C11."""
    cols_to_use = [col for col in DASHBOARD_SAMPLE_COLUMNS if col in df.columns]
    sub_df = df[cols_to_use]

    rows: list[list[Any]] = []
    for row in sub_df.itertuples(index=False):
        clean_row = [clean_json_value(v) for v in row]
        rows.append(clean_row)

    return {
        "columns": cols_to_use,
        "rows": rows,
    }


def build_quality_block(
    df: pd.DataFrame,
    preprocess_log: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute data quality statistics block."""
    missing_cols = ["ss_rsrp", "ss_rsrq", "ss_sinr", "csi_rsrp", "csi_rsrq", "csi_sinr"]
    missing = {col: int(df[col].isna().sum()) for col in missing_cols if col in df.columns}

    csi_available: dict[str, bool] = {}
    if "device" in df.columns and "csi_available" in df.columns:
        for dev, group in df.groupby("device"):
            csi_available[str(dev)] = bool(group["csi_available"].any())

    deployment_modes: dict[str, int] = {}
    if "deployment_mode" in df.columns:
        counts = df["deployment_mode"].value_counts().to_dict()
        deployment_modes = {str(k): int(v) for k, v in counts.items()}

    log_summary: dict[str, Any] = {}
    if preprocess_log:
        total_raw = preprocess_log.get(
            "total_raw_rows_loaded", preprocess_log.get("total_raw", len(df))
        )
        dropped = preprocess_log.get("invalid_range_rows_dropped", preprocess_log.get("dropped", 0))
        clean_rows = preprocess_log.get(
            "clean_output_rows", preprocess_log.get("clean_rows", len(df))
        )
        log_summary = {
            "total_raw": int(total_raw),
            "dropped": int(dropped),
            "clean_rows": int(clean_rows),
        }

    return {
        "missing": missing,
        "csi_available": csi_available,
        "deployment_modes": deployment_modes,
        "preprocess_log": log_summary,
    }


def build_bundle(
    source: str = "processed",
    base_dir: Path | str = ".",
) -> dict[str, Any]:
    """Build Contract C11 demo data bundle from source files.

    Args:
        source: 'processed' or 'sample'.
        base_dir: Repository root directory.

    Returns:
        Contract C11 dictionary structure.
    """
    root = Path(base_dir)

    temp_dir_obj = None
    if source == "sample":
        sample_scores = root / "data/sample/scores.csv"
        if sample_scores.exists():
            scores_path = sample_scores
            events_path = root / "data/sample/events_diagnosed.json"
            prep_log_path = root / "data/sample/preprocess_log.json"
        else:
            # Process sample_measurements.csv into a temporary directory
            temp_dir_obj = tempfile.TemporaryDirectory()
            temp_out = Path(temp_dir_obj.name)
            logger.info("Running pipeline on data/sample to generate scores artifact...")
            run_pipeline(input_dir=root / "data/sample", output_dir=temp_out, retrain=False)
            scores_path = temp_out / "scores.csv"
            events_path = temp_out / "events_diagnosed.json"
            prep_log_path = temp_out / "preprocess_log.json"
    elif source == "processed":
        scores_path = root / "data/processed/scores.csv"
        events_path = root / "data/processed/events_diagnosed.json"
        prep_log_path = root / "data/processed/preprocess_log.json"
    else:
        raise ValueError(f"Unknown source '{source}'. Expected 'processed' or 'sample'.")

    if not scores_path.exists():
        raise FileNotFoundError(f"Scores file not found at {scores_path}")

    logger.info("Loading scores from %s...", scores_path)
    df = pd.read_csv(scores_path)

    events: list[dict[str, Any]] = []
    if events_path.exists():
        with open(events_path, encoding="utf-8") as f:
            events = json.load(f)

    prep_log: dict[str, Any] = {}
    if prep_log_path.exists():
        with open(prep_log_path, encoding="utf-8") as f:
            prep_log = json.load(f)

    model_meta: dict[str, Any] = {}
    model_meta_path = root / "models/if_v1.meta.json"
    if model_meta_path.exists():
        with open(model_meta_path, encoding="utf-8") as f:
            model_meta = json.load(f)

    # Precomputed transitions (T16-002)
    logger.info("Precomputing transitions...")
    transitions = compute_transitions(df)

    # Sessions metadata
    sessions = extract_sessions(df)

    # Columnar samples
    samples = build_samples_block(df)

    # Quality stats
    quality = build_quality_block(df, prep_log)

    # Deterministic timestamp for generated_at
    if "SOURCE_DATE_EPOCH" in os.environ:
        generated_at = os.environ["SOURCE_DATE_EPOCH"]
    elif "timestamp" in model_meta and model_meta["timestamp"]:
        generated_at = str(model_meta["timestamp"])
    elif not df.empty and "timestamp" in df.columns:
        generated_at = str(df["timestamp"].dropna().iloc[-1])
    else:
        generated_at = "2026-10-12T10:00:00Z"

    model_version = model_meta.get("model_version", "1.0.0")

    bundle: dict[str, Any] = {
        "bundle_version": 1,
        "generated_at": generated_at,
        "model_version": model_version,
        "source": source,
        "privacy": {
            "cell_ids": "raw",
            "time": "device-local, no timezone",
        },
        "sessions": sessions,
        "samples": samples,
        "transitions": transitions,
        "events": events,
        "quality": quality,
        "model_meta": model_meta,
    }

    if temp_dir_obj is not None:
        temp_dir_obj.cleanup()

    return bundle


def main() -> None:
    """CLI entrypoint for demo-bundle builder."""
    parser = argparse.ArgumentParser(
        description="Build Contract C11 demo data bundle for the static React dashboard.",
    )
    parser.add_argument(
        "--source",
        choices=["processed", "sample"],
        default="processed",
        help="Data source to bundle: 'processed' (default) or 'sample'.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="frontend/public/demo-bundle.json",
        help="Destination JSON file path (default: frontend/public/demo-bundle.json).",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Base repository directory (default: current directory).",
    )

    args = parser.parse_args()

    try:
        bundle = build_bundle(source=args.source, base_dir=args.base_dir)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        json_bytes = json.dumps(bundle, indent=2, sort_keys=True).encode("utf-8")
        out_path.write_bytes(json_bytes)

        size_kb = len(json_bytes) / 1024.0
        size_mb = size_kb / 1024.0
        print(
            f"Successfully built demo bundle ({args.source}): {out_path} "
            f"({len(bundle['samples']['rows'])} samples, {len(bundle['transitions'])} transitions, "
            f"{len(bundle['events'])} events) -> {size_kb:.1f} KB ({size_mb:.2f} MB)"
        )
    except Exception as exc:
        print(f"Error building demo bundle: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

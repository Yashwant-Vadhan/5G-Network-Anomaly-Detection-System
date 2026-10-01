"""Data preprocessing pipeline for 5G-NADS.

Implements raw CSV loading, validation, timestamp parsing/sorting, numeric coercion,
missing-value policy, validity checks, sessionization, and clean artifact output.

Fulfills contract C2 and guardrails G2, G3, G7, G8, G12.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

from ml.config import (
    NA_TOKENS,
    PROCESSED_DIR,
    RAW_DIR,
    SENTINEL_INTS,
    SESSION_GAP_SECONDS,
    VALID_RANGES,
)
from ml.schema import (
    C2_DTYPES,
    ConfigError,
    DataQualityError,
    SchemaError,
    assert_no_pii_columns,
    validate_raw_columns,
)

logger = logging.getLogger(__name__)


def load_raw_csv(filepath: Path | str) -> pd.DataFrame:
    """Load a single raw measurement CSV as strings and validate schema & PII.

    Args:
        filepath: Path to the raw CSV file.

    Returns:
        DataFrame containing 18 Contract C1 columns + `source_file`.

    Raises:
        SchemaError: If column headers do not match C1 or contain PII.
        DataQualityError: If the file is empty.
    """
    path = Path(filepath)
    if not path.is_file():
        raise SchemaError(f"File not found: '{path}'")

    try:
        df = pd.read_csv(path, dtype=str, skipinitialspace=True)
    except Exception as e:
        raise DataQualityError(f"Failed to read CSV '{path.name}': {e}") from e

    if df.empty:
        raise DataQualityError(f"File '{path.name}' is empty.")

    validate_raw_columns(df)
    assert_no_pii_columns(df)

    df["source_file"] = path.name
    return df


def load_raw_dir(raw_dir: Path | str) -> pd.DataFrame:
    """Load and concatenate all raw CSV files in directory deterministically.

    Args:
        raw_dir: Path to directory containing raw CSV files.

    Returns:
        Concatenated DataFrame of all loaded CSVs.

    Raises:
        ConfigError: If directory is missing.
        DataQualityError: If no valid CSV files are found or loaded DataFrame is empty.
    """
    dir_path = Path(raw_dir)
    if not dir_path.is_dir():
        raise ConfigError(f"Directory not found: '{dir_path}'")

    csv_files = sorted(dir_path.glob("*.csv"))
    if not csv_files:
        raise DataQualityError(f"No CSV files found in '{dir_path}'")

    dfs: list[pd.DataFrame] = []
    for csv_path in csv_files:
        try:
            df = load_raw_csv(csv_path)
            dfs.append(df)
        except Exception as e:
            logger.warning("Failed to load raw file %s: %s", csv_path.name, e)

    if not dfs:
        raise DataQualityError(f"No valid CSV files could be loaded from '{dir_path}'")

    return pd.concat(dfs, ignore_index=True)


def parse_timestamps(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse timestamps, stably sort by (device, timestamp), and isolate unparseable rows.

    Args:
        df: Input DataFrame containing string `timestamp` and `device` columns.

    Returns:
        Tuple of (sorted valid DataFrame, rejected rows DataFrame).
    """
    if "timestamp" not in df.columns or "device" not in df.columns:
        raise SchemaError("DataFrame missing 'timestamp' or 'device' columns.")

    parsed_ts = pd.to_datetime(
        df["timestamp"],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )

    unparseable_mask = parsed_ts.isna()
    rejected_df = df[unparseable_mask].copy()
    if not rejected_df.empty:
        rejected_df["reject_reason"] = "unparseable_timestamp"

    clean_df = df[~unparseable_mask].copy()
    clean_df["timestamp"] = parsed_ts[~unparseable_mask]

    # Flag duplicate timestamps within (device, timestamp)
    clean_df["dup_ts"] = clean_df.duplicated(subset=["device", "timestamp"], keep=False)

    # Stable sort by device, timestamp
    clean_df = clean_df.sort_values(by=["device", "timestamp"], kind="stable").reset_index(
        drop=True
    )
    return clean_df, rejected_df


def coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce numeric columns to nullable dtypes and replace NA/sentinels with NaN/<NA>.

    Never converts missing values to 0 (Guardrails G2, G3).
    """
    df = df.copy()

    # Replace string NA tokens
    df = df.replace(NA_TOKENS, np.nan)

    # Float columns
    float_cols = ["ss_rsrp", "ss_rsrq", "ss_sinr", "csi_rsrp", "csi_rsrq", "csi_sinr"]
    for col in float_cols:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").astype("float64")
            for sentinel in SENTINEL_INTS:
                s = s.replace(sentinel, np.nan)
            df[col] = s

    # Integer columns (nullable Int64 for 64-bit precision safety e.g. NCI)
    int_cols = ["pci", "nci", "nrarfcn"]
    for col in int_cols:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            for sentinel in SENTINEL_INTS:
                s = s.replace(sentinel, pd.NA)
            df[col] = s

    # Boolean registered column
    if "registered" in df.columns:
        reg_map = {
            "TRUE": True,
            "True": True,
            "true": True,
            "1": True,
            "FALSE": False,
            "False": False,
            "false": False,
            "0": False,
        }
        df["registered"] = df["registered"].map(reg_map).astype("boolean")

    return df


def flag_invalid(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean `is_valid` flag indicating whether radio metrics fall within plausible ranges.

    Missing values do NOT make a row invalid.
    """
    df = df.copy()
    is_valid_series = pd.Series(True, index=df.index)

    for metric, (low, high) in VALID_RANGES.items():
        if metric in df.columns:
            val = df[metric]
            out_of_bounds = val.notna() & ((val < low) | (val > high))
            is_valid_series = is_valid_series & (~out_of_bounds)

    df["is_valid"] = is_valid_series
    return df


def add_missing_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add csi_available and model_eligible boolean policy flags.

    No imputation is performed (Guardrail G2).
    """
    df = df.copy()

    csi_cols = [c for c in ["csi_rsrp", "csi_rsrq", "csi_sinr"] if c in df.columns]
    if csi_cols:
        df["csi_available"] = df[csi_cols].notna().any(axis=1)
    else:
        df["csi_available"] = False

    base_cols = [c for c in ["ss_rsrp", "ss_rsrq", "ss_sinr"] if c in df.columns]
    if len(base_cols) == 3:
        df["model_eligible"] = df[base_cols].notna().all(axis=1)
    else:
        df["model_eligible"] = False

    return df


def add_sessions(df: pd.DataFrame, gap_seconds: int = SESSION_GAP_SECONDS) -> pd.DataFrame:
    """Group consecutive records per device into sessions separated by gap_seconds or file changes."""
    df = df.copy()

    if df.empty:
        df["session_id"] = pd.Series(dtype="string")
        df["sample_idx"] = pd.Series(dtype="int64")
        return df

    session_ids: list[str] = []
    sample_indices: list[int] = []

    for device, group in df.groupby("device", sort=False):
        device_slug = str(device).lower().replace(" ", "_")
        current_session_num = 1
        current_sample_idx = 0

        prev_time = None
        prev_source = None

        for _, row in group.iterrows():
            curr_time = row["timestamp"]
            curr_source = row.get("source_file", "")

            time_gap = (curr_time - prev_time).total_seconds() if prev_time is not None else 0

            if prev_time is not None and (time_gap > gap_seconds or curr_source != prev_source):
                current_session_num += 1
                current_sample_idx = 0

            session_id = f"{device_slug}-{current_session_num}"
            session_ids.append(session_id)
            sample_indices.append(current_sample_idx)

            current_sample_idx += 1
            prev_time = curr_time
            prev_source = curr_source

    df["session_id"] = pd.Series(session_ids, index=df.index, dtype="string")
    df["sample_idx"] = pd.Series(sample_indices, index=df.index, dtype="int64")
    return df


def preprocess(raw_dir: Path | str, out_dir: Path | str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Execute end-to-end preprocessing pipeline raw -> clean (Contract C2 & Log)."""
    raw_path = Path(raw_dir).resolve()
    out_path = Path(out_dir).resolve()

    # Guardrail G7: Refuse writing output into raw directory
    try:
        out_path.relative_to(raw_path)
        raise ConfigError(
            f"Output directory '{out_path}' cannot be inside raw data directory '{raw_path}'."
        )
    except ValueError:
        pass

    raw_df = load_raw_dir(raw_path)
    total_loaded = len(raw_df)

    clean_df, rejected_ts_df = parse_timestamps(raw_df)
    clean_df = coerce_numeric(clean_df)
    clean_df = flag_invalid(clean_df)
    clean_df = add_missing_flags(clean_df)
    clean_df = add_sessions(clean_df)

    # Flag synthetic rows (Guardrail G12)
    clean_df["is_synthetic"] = clean_df["source_file"].apply(lambda f: "_synthetic" in str(f))

    invalid_count = int((~clean_df["is_valid"]).sum())

    # Drop invalid rows for clean output
    final_clean_df = clean_df[clean_df["is_valid"]].copy().reset_index(drop=True)

    out_path.mkdir(parents=True, exist_ok=True)
    clean_csv_path = out_path / "measurements_clean.csv"

    # Enforce C2 dtypes
    final_clean_df = final_clean_df.astype(
        {k: v for k, v in C2_DTYPES.items() if k in final_clean_df.columns}
    )
    final_clean_df.to_csv(clean_csv_path, index=False)

    log_data = {
        "loaded_rows": total_loaded,
        "unparseable_timestamp_rows": len(rejected_ts_df),
        "invalid_range_rows": invalid_count,
        "clean_rows": len(final_clean_df),
        "synthetic_rows": int(final_clean_df["is_synthetic"].sum()),
        "sessions_count": int(final_clean_df["session_id"].nunique()),
    }

    log_path = out_path / "preprocess_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

    logger.info(
        "Preprocessed %d rows -> %d clean rows saved to %s",
        total_loaded,
        len(final_clean_df),
        clean_csv_path,
    )
    return final_clean_df, log_data


def main() -> None:
    """CLI entry point for ml.preprocessing."""
    parser = argparse.ArgumentParser(description="Run 5G-NADS raw to clean preprocessing pipeline.")
    parser.add_argument(
        "--input",
        type=Path,
        default=RAW_DIR,
        help="Input directory containing raw CSV files (default: data/raw).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR,
        help="Output directory for clean CSV and log (default: data/processed).",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        preprocess(args.input, args.output)
        print("Preprocessing completed successfully.")
        sys.exit(0)
    except (SchemaError, DataQualityError, ConfigError) as e:
        print(f"PREPROCESSING ERROR: {e}", file=sys.stderr)
        print("Fix Hint: Check raw CSV headers, file integrity, and paths.", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

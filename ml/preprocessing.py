"""Preprocessing module for 5G Network Anomaly Detection System (5G-NADS).

Handles CSV loading, schema validation, timestamp parsing, numeric coercion,
range validation, missing value policies, sessionization, and pipeline execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from ml.config import NA_TOKENS, RAW_DIR, REPO_ROOT, SAMPLING_SECONDS, SENTINEL_INTS, SESSION_GAP_SECONDS, VALID_RANGES
from ml.schema import C2_DTYPES, ConfigError, DataQualityError, SchemaError, assert_no_pii_columns, validate_raw_columns


def load_raw_csv(path: str | Path) -> pd.DataFrame:
    """Read a raw CSV measurement file, validate schema and PII rules, and attach source_file.

    All columns are initially read as strings to preserve literal 'NA' tokens and avoid
    unintended type coercion prior to explicit numeric handling.

    Args:
        path: Path to the raw CSV file.

    Returns:
        DataFrame containing all 18 raw columns as strings plus a 'source_file' column.

    Raises:
        DataQualityError: If the file is empty or contains no data rows.
        SchemaError: If column header validation fails or forbidden PII columns are present.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_path.stat().st_size == 0:
        raise DataQualityError(f"Raw CSV file is empty (0 bytes): {file_path}")

    try:
        df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as err:
        raise DataQualityError(f"Raw CSV file contains no data rows: {file_path}") from err
    except Exception as err:
        raise SchemaError(f"Failed to parse CSV file: {file_path}") from err

    if df.empty:
        raise DataQualityError(f"Raw CSV file contains no data rows: {file_path}")

    validate_raw_columns(df)
    assert_no_pii_columns(df)

    df["source_file"] = file_path.name
    return df


def load_raw_dir(dir_path: str | Path) -> pd.DataFrame:
    """Load and concatenate all raw CSV files in a directory deterministically by sorted filename.

    Args:
        dir_path: Path to the directory containing raw CSV files.

    Returns:
        Concatenated DataFrame containing all loaded raw measurements.

    Raises:
        DataQualityError: If no CSV files are found in the directory or if loading fails.
    """
    directory = Path(dir_path)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    csv_paths = sorted(directory.glob("*.csv"))
    if not csv_paths:
        raise DataQualityError(f"No CSV files found in directory: {directory}")

    dfs = [load_raw_csv(p) for p in csv_paths]
    return pd.concat(dfs, ignore_index=True)


def parse_timestamps(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse timestamp column, reject unparseable rows, flag duplicate timestamps, and sort.

    Supports collector local timestamp format ('dd-MM-yy HH:mm:ss') and ISO-8601 strings.
    Rows with unparseable timestamps are extracted into a separate rejected DataFrame with reason.
    Valid rows are flagged for duplicate timestamps via 'dup_ts' and stably sorted by
    ['device', 'timestamp'].

    Args:
        df: Input DataFrame containing raw string 'timestamp' and 'device' columns.

    Returns:
        Tuple of (clean_sorted_df, rejected_rows_df).
    """
    df = df.copy()
    parsed_ts = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce", utc=True)

    invalid_mask = parsed_ts.isna()
    rejected_df = df[invalid_mask].copy()
    if not rejected_df.empty:
        rejected_df["reject_reason"] = "unparseable_timestamp"

    clean_df = df[~invalid_mask].copy()
    clean_df["timestamp"] = parsed_ts[~invalid_mask]

    # Flag duplicate timestamps within the same device
    clean_df["dup_ts"] = clean_df.duplicated(subset=["device", "timestamp"], keep=False)

    # Stable sort by device, then timestamp
    sorted_df = clean_df.sort_values(by=["device", "timestamp"], kind="stable", ignore_index=True)
    return sorted_df, rejected_df


def coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce signal metrics, cell identifiers, and boolean flags to proper nullable types.

    Converts 'NA' tokens and sentinel integers (e.g. 2147483647) to missing (NaN/pd.NA),
    preserving 64-bit precision for large NCI values. Missing values are never filled with 0.

    Args:
        df: Input DataFrame with raw string values.

    Returns:
        DataFrame with coerced numeric, boolean, and string dtypes per Contract C2.
    """
    df = df.copy()

    float_cols = ["ss_rsrp", "ss_rsrq", "ss_sinr", "csi_rsrp", "csi_rsrq", "csi_sinr"]
    int_cols = ["pci", "nci", "nrarfcn"]

    sentinel_str_set = {str(s) for s in SENTINEL_INTS} | set(NA_TOKENS) | {"", "None", "null"}

    # Process float signal columns
    for col in float_cols:
        if col in df.columns:
            series = df[col].astype(str).str.strip()
            series = series.apply(lambda x: pd.NA if x in sentinel_str_set else x)
            df[col] = pd.to_numeric(series, errors="coerce").astype("float64")

    # Process nullable Int64 cell columns (64-bit precision for NCI)
    for col in int_cols:
        if col in df.columns:
            series = df[col].astype(str).str.strip()
            series = series.apply(lambda x: pd.NA if x in sentinel_str_set else x)
            df[col] = pd.to_numeric(series, errors="coerce").astype("Int64")

    # Process registered boolean column
    if "registered" in df.columns:
        series = df["registered"].astype(str).str.strip().str.lower()
        bool_map = {"true": True, "1": True, "false": False, "0": False}
        df["registered"] = series.map(bool_map).astype("boolean")

    return df


def flag_invalid(df: pd.DataFrame) -> pd.DataFrame:
    """Flag rows containing non-missing signal metric values that fall outside plausible ranges.

    Ranges are defined in ml.config.VALID_RANGES based on official Android CellSignalStrengthNr API bounds.
    Missing values (NaN/pd.NA) do NOT trigger an invalid flag (is_valid remains True).

    Args:
        df: Input DataFrame with numeric signal metric columns.

    Returns:
        DataFrame with an added boolean 'is_valid' column.
    """
    df = df.copy()
    is_valid_mask = pd.Series(True, index=df.index, dtype="boolean")

    for col, (min_val, max_val) in VALID_RANGES.items():
        if col in df.columns:
            series = df[col]
            out_of_bounds = series.notna() & ((series < min_val) | (series > max_val))
            is_valid_mask = is_valid_mask & (~out_of_bounds)

    df["is_valid"] = is_valid_mask
    return df


def add_missing_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add informational missing-value policy flags without imputing measurement values.

    MISSING VALUE POLICY (Guardrail G2/G3 & overview §13):
    Missing radio measurements are NEVER imputed (no standard replacement or estimation functions).
    - 'csi_available': True if any of csi_rsrp, csi_rsrq, csi_sinr is non-null.
    - 'model_eligible': True if all base model signal metrics (ss_rsrp, ss_rsrq, ss_sinr) are non-null.

    Args:
        df: Input DataFrame with numeric signal columns.

    Returns:
        DataFrame with added 'csi_available' and 'model_eligible' boolean columns.
    """
    df = df.copy()

    csi_cols = [c for c in ["csi_rsrp", "csi_rsrq", "csi_sinr"] if c in df.columns]
    if csi_cols:
        df["csi_available"] = df[csi_cols].notna().any(axis=1).astype("boolean")
    else:
        df["csi_available"] = pd.Series(False, index=df.index, dtype="boolean")

    base_cols = [c for c in ["ss_rsrp", "ss_rsrq", "ss_sinr"] if c in df.columns]
    if len(base_cols) == 3:
        df["model_eligible"] = df[base_cols].notna().all(axis=1).astype("boolean")
    else:
        df["model_eligible"] = pd.Series(False, index=df.index, dtype="boolean")

    return df


def add_sessions(df: pd.DataFrame, gap_seconds: int = SESSION_GAP_SECONDS) -> pd.DataFrame:
    """Group continuous measurements into device sessions based on time gaps or source files.

    A new session is started whenever:
    1. The device changes.
    2. The source_file changes.
    3. The time gap between consecutive records exceeds gap_seconds.

    Args:
        df: Input DataFrame sorted by ['device', 'timestamp'].
        gap_seconds: Time gap threshold in seconds to delimit sessions.

    Returns:
        DataFrame with added 'session_id' (string) and 'sample_idx' (int64) columns.
    """
    df = df.copy()

    device_series = df["device"].astype(str)
    file_series = df["source_file"].astype(str) if "source_file" in df.columns else pd.Series("", index=df.index)

    time_diff = df.groupby("device")["timestamp"].diff().dt.total_seconds()
    gap_break = time_diff > gap_seconds
    device_break = device_series != device_series.shift(1)
    file_break = file_series != file_series.shift(1)

    new_session_mask = device_break | file_break | gap_break
    session_num = new_session_mask.cumsum()

    # Format session_id as <device_slug>-<session_num>
    def slugify(val: str) -> str:
        return "".join(c.lower() if c.isalnum() else "-" for c in val).strip("-")

    device_slugs = device_series.apply(slugify)
    df["session_id"] = device_slugs + "-" + session_num.astype(str)

    # Calculate sample_idx within each session
    df["sample_idx"] = df.groupby("session_id").cumcount()
    return df


def preprocess(raw_dir: str | Path, out_dir: str | Path) -> pd.DataFrame:
    """Execute full preprocessing pipeline from raw CSV directory to clean dataset.

    Args:
        raw_dir: Path to directory containing raw CSV files.
        out_dir: Path to output directory for clean dataset and preprocessing logs.

    Returns:
        Cleaned pandas DataFrame conforming to Contract C2.

    Raises:
        ConfigError: If out_dir attempts to write inside raw_dir (Guardrail G7).
    """
    raw_path = Path(raw_dir).resolve()
    out_path = Path(out_dir).resolve()

    if out_path == raw_path or raw_path in out_path.parents:
        raise ConfigError(f"Output directory {out_path} cannot be inside raw directory {raw_path} (Guardrail G7).")

    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Load raw files
    raw_df = load_raw_dir(raw_path)
    total_loaded = len(raw_df)

    # 2. Parse timestamps and extract unparseable
    valid_ts_df, unparseable_df = parse_timestamps(raw_df)
    unparseable_count = len(unparseable_df)

    # 3. Numeric coercion
    coerced_df = coerce_numeric(valid_ts_df)

    # 4. Range validation
    flagged_df = flag_invalid(coerced_df)

    # 5. Missing value policy flags
    missing_flagged_df = add_missing_flags(flagged_df)

    # 6. Sessionization
    sessionized_df = add_sessions(missing_flagged_df)

    # 7. Add synthetic indicator
    if "source_file" in sessionized_df.columns:
        sessionized_df["is_synthetic"] = sessionized_df["source_file"].str.contains("_synthetic", case=False, na=False)
    else:
        sessionized_df["is_synthetic"] = False

    # Filter out invalid rows for final clean output
    invalid_mask = ~sessionized_df["is_valid"]
    invalid_rows_count = int(invalid_mask.sum())
    clean_df = sessionized_df[~invalid_mask].copy()

    # Reorder columns per Contract C2 specification
    c2_order = [
        "timestamp",
        "device",
        "manufacturer",
        "android",
        "operator",
        "network_type",
        "deployment_mode",
        "display_override",
        "registered",
        "ss_rsrp",
        "ss_rsrq",
        "ss_sinr",
        "csi_rsrp",
        "csi_rsrq",
        "csi_sinr",
        "pci",
        "nci",
        "nrarfcn",
        "session_id",
        "sample_idx",
        "is_valid",
        "model_eligible",
        "csi_available",
        "is_synthetic",
        "source_file",
        "dup_ts",
    ]
    present_c2 = [c for c in c2_order if c in clean_df.columns]
    clean_df = clean_df[present_c2]

    # Save measurements_clean.csv
    csv_file = out_path / "measurements_clean.csv"
    clean_df.to_csv(csv_file, index=False)

    # Save preprocess_log.json
    log_data = {
        "total_raw_rows_loaded": total_loaded,
        "unparseable_timestamp_rows": unparseable_count,
        "invalid_range_rows_dropped": invalid_rows_count,
        "clean_output_rows": len(clean_df),
        "total_sessions": clean_df["session_id"].nunique() if "session_id" in clean_df.columns else 0,
    }
    log_file = out_path / "preprocess_log.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

    return clean_df


def main() -> None:
    """CLI entrypoint for ml.preprocessing module."""
    parser = argparse.ArgumentParser(description="5G-NADS Preprocessing Pipeline")
    parser.add_argument("--input", "-i", default="data/raw", help="Path to input raw CSV directory")
    parser.add_argument("--output", "-o", default="data/processed", help="Path to output processed directory")
    args = parser.parse_args()

    try:
        clean_df = preprocess(args.input, args.output)
        print(f"Successfully preprocessed {len(clean_df)} records from '{args.input}' to '{args.output}'.")
    except (SchemaError, DataQualityError) as err:
        print(f"PREPROCESSING ERROR: {err}", file=sys.stderr)
        print("Hint: Verify input header matches Contract C1 and CSV files are non-empty.", file=sys.stderr)
        sys.exit(2)
    except ConfigError as err:
        print(f"CONFIGURATION ERROR: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

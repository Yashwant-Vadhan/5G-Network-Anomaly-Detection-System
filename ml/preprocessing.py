"""Preprocessing module for 5G Network Anomaly Detection System (5G-NADS).

Handles CSV loading, schema validation, timestamp parsing, numeric coercion,
range validation, missing value policies, sessionization, and pipeline execution.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.config import NA_TOKENS, SENTINEL_INTS
from ml.schema import DataQualityError, SchemaError, assert_no_pii_columns, validate_raw_columns


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

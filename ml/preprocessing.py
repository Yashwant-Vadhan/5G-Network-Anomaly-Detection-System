"""Preprocessing module for 5G Network Anomaly Detection System (5G-NADS).

Handles CSV loading, schema validation, timestamp parsing, numeric coercion,
range validation, missing value policies, sessionization, and pipeline execution.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

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

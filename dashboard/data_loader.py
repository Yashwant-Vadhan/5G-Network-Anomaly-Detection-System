"""Cached Data Loaders and Validation for 5G-NADS Dashboard (T6-001, T6-009).

Loads processed datasets, diagnosed events, and metadata with Streamlit caching.
Handles uploaded CSVs, enforcing <= 20 MB size limit, .csv extension, and column validation.
Handles missing files gracefully with empty state defaults per DESIGN.md.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ml.schema import DataQualityError, SchemaError, assert_no_pii_columns, validate_raw_columns

logger = logging.getLogger(__name__)

DEFAULT_PROCESSED_PATH = Path("data/processed/scores.csv")
DEFAULT_SAMPLE_PATH = Path("data/sample/sample_measurements.csv")
DEFAULT_EVENTS_PATH = Path("data/processed/events_diagnosed.json")
DEFAULT_MODEL_META_PATH = Path("models/if_v1.meta.json")
DEFAULT_PREPROCESS_LOG_PATH = Path("data/processed/preprocess_log.json")

MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB limit (T6-009)


@st.cache_data
def load_scores_data(path: str | Path | None = None) -> pd.DataFrame | None:
    """Load scores.csv dataframe or fallback to sample_measurements.csv if missing.

    Returns None if neither file is available.
    """
    target_path = Path(path) if path else DEFAULT_PROCESSED_PATH

    if not target_path.exists():
        if target_path == DEFAULT_PROCESSED_PATH and DEFAULT_SAMPLE_PATH.exists():
            target_path = DEFAULT_SAMPLE_PATH
        else:
            return None

    try:
        df = pd.read_csv(target_path)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as exc:
        logger.warning("Error loading dataframe from %s: %s", target_path, exc)
        return None


@st.cache_data
def load_events_diagnosed(path: str | Path | None = None) -> list[dict[str, Any]] | None:
    """Load events_diagnosed.json.

    Returns None if file is missing or invalid.
    """
    target_path = Path(path) if path else DEFAULT_EVENTS_PATH

    if not target_path.exists():
        return None

    try:
        with open(target_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Error loading events_diagnosed from %s: %s", target_path, exc)
        return None


@st.cache_data
def load_model_metadata(path: str | Path | None = None) -> dict[str, Any] | None:
    """Load models/if_v1.meta.json metadata file.

    Returns None if file is missing or invalid.
    """
    target_path = Path(path) if path else DEFAULT_MODEL_META_PATH

    if not target_path.exists():
        return None

    try:
        with open(target_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Error loading model metadata from %s: %s", target_path, exc)
        return None


@st.cache_data
def load_preprocess_log(path: str | Path | None = None) -> dict[str, Any] | None:
    """Load preprocess_log.json log file.

    Returns None if file is missing or invalid.
    """
    target_path = Path(path) if path else DEFAULT_PREPROCESS_LOG_PATH

    if not target_path.exists():
        return None

    try:
        with open(target_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Error loading preprocess log from %s: %s", target_path, exc)
        return None


def validate_and_load_uploaded_csv(uploaded_file: Any) -> pd.DataFrame | None:
    """Validate and parse an uploaded CSV file per T6-009.

    Checks:
    - File extension must be .csv
    - File size must be <= 20 MB
    - Schema must contain required raw columns or clean processed columns
    - Must not contain PII columns

    Returns:
        DataFrame if valid, None if validation fails (renders st.error with explanation).
    """
    if uploaded_file is None:
        return None

    file_name = getattr(uploaded_file, "name", "uploaded.csv")
    if not file_name.lower().endswith(".csv"):
        st.error(
            f"❌ Invalid file format for `{file_name}`. Only CSV files (`.csv`) are supported."
            " Please upload a valid CSV measurement file."
        )
        return None

    file_size = getattr(uploaded_file, "size", 0)
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        st.error(
            f"❌ File size error: `{file_name}` is {size_mb:.1f} MB, which exceeds the 20 MB limit."
            " Please compress or filter the file before uploading."
        )
        return None

    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        st.error(f"❌ Could not parse `{file_name}` as a valid CSV: {exc}")
        return None

    if df.empty:
        st.error(f"❌ Uploaded file `{file_name}` is empty. Please upload a file with data.")
        return None

    # Validate schema if it's raw data
    try:
        assert_no_pii_columns(df)
        if "ss_rsrp" not in df.columns:
            validate_raw_columns(df)
    except (SchemaError, DataQualityError) as err:
        st.error(f"❌ Schema validation failed for `{file_name}`: {err}")
        return None
    except Exception as exc:
        st.error(f"❌ Data quality validation error: {exc}")
        return None

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return df

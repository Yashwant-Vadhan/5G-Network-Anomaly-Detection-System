"""Cached Data Loaders for 5G-NADS Dashboard (T6-001).

Loads processed datasets, diagnosed events, and metadata with Streamlit caching.
Handles missing files gracefully with empty state defaults per DESIGN.md.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

DEFAULT_PROCESSED_PATH = Path("data/processed/scores.csv")
DEFAULT_SAMPLE_PATH = Path("data/sample/sample_measurements.csv")
DEFAULT_EVENTS_PATH = Path("data/processed/events_diagnosed.json")
DEFAULT_MODEL_META_PATH = Path("models/if_v1.meta.json")
DEFAULT_PREPROCESS_LOG_PATH = Path("data/processed/preprocess_log.json")


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

"""Unit tests for dashboard data loader module (T6-001)."""

from __future__ import annotations

import json
import pandas as pd
from dashboard.data_loader import (
    load_events_diagnosed,
    load_model_metadata,
    load_preprocess_log,
    load_scores_data,
)


def test_data_loader_handles_missing_files(tmp_path):
    """Verify data loaders return None when files are missing."""
    non_existent = tmp_path / "does_not_exist.csv"

    assert load_scores_data(non_existent) is None
    assert load_events_diagnosed(non_existent) is None
    assert load_model_metadata(non_existent) is None
    assert load_preprocess_log(non_existent) is None


def test_load_scores_data_valid(tmp_path):
    """Verify load_scores_data loads CSV and parses timestamp."""
    csv_file = tmp_path / "test_scores.csv"
    df_raw = pd.DataFrame(
        {
            "timestamp": ["2026-09-28T10:00:00Z", "2026-09-28T10:00:03Z"],
            "ss_rsrp": [-80.0, -85.0],
            "ss_sinr": [20.0, 15.0],
        }
    )
    df_raw.to_csv(csv_file, index=False)

    df_loaded = load_scores_data(csv_file)
    assert df_loaded is not None
    assert len(df_loaded) == 2
    assert pd.api.types.is_datetime64_any_dtype(df_loaded["timestamp"])


def test_load_json_data_valid(tmp_path):
    """Verify json data loaders load dictionaries and lists correctly."""
    events_file = tmp_path / "events.json"
    meta_file = tmp_path / "meta.json"

    events_data = [{"event_id": "evt-1"}]
    meta_data = {"version": "v1"}

    with open(events_file, "w", encoding="utf-8") as f:
        json.dump(events_data, f)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta_data, f)

    assert load_events_diagnosed(events_file) == events_data
    assert load_model_metadata(meta_file) == meta_data

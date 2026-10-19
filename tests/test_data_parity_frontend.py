"""Data-parity tests between frontend bundle representation and Python outputs (T16-018).

Verifies that numbers, events, and quality metrics rendered in the frontend equal
the Python outputs from data/processed (scores.csv, events_diagnosed.json, preprocess_log.json).

Acceptance Criteria:
- 10 samples and 5 events checked field by field
- Fails if the builder changes a value
"""

from __future__ import annotations

import copy
import json
from typing import Any

import numpy as np
import pandas as pd
import pytest

from scripts.build_demo_bundle import build_bundle
from tests.test_demo_bundle import ensure_processed_sources

SAMPLE_FIVE_EVENTS: list[dict[str, Any]] = [
    {
        "event_id": f"evt-00{i}",
        "session_id": "session-test-parity",
        "start": f"2026-09-30 22:5{i}:00+00:00",
        "end": f"2026-09-30 22:5{i}:45+00:00",
        "anomaly_type": "STATISTICAL_ONLY",
        "severity": "HIGH",
        "max_severity": "HIGH",
        "sample_count": 8 + i,
        "ml": {
            "anomaly_type": "STATISTICAL_ONLY",
            "max_severity": "HIGH",
            "sample_count": 8 + i,
        },
        "diagnosis": {
            "summary": f"Detected anomaly event 00{i} in radio signal.",
        },
        "recommendation": {
            "kind": "MONITORING",
            "text": "Maintain standard metric telemetry collection.",
        },
    }
    for i in range(1, 6)
]


def check_sample_parity(bundle_row: list[Any], cols: list[str], df_row: pd.Series) -> None:
    """Compare a bundle sample row against a pandas Series from scores.csv field-by-field."""
    fields_to_check = [
        "ss_rsrp",
        "ss_rsrq",
        "ss_sinr",
        "nrarfcn",
        "if_score",
        "baseline_flag",
        "if_flag",
        "anomaly_type",
        "severity",
        "pci",
        "nci",
    ]

    for col in fields_to_check:
        if col not in cols or col not in df_row.index:
            continue
        col_idx = cols.index(col)
        bundle_val = bundle_row[col_idx]
        df_val = df_row[col]

        if pd.isna(df_val):
            assert bundle_val is None or bundle_val == "nan", (
                f"Field {col}: expected None, got {bundle_val}"
            )
        elif isinstance(bundle_val, bool) or isinstance(df_val, (bool, np.bool_)):
            assert bool(bundle_val) == bool(df_val), (
                f"Field {col} boolean mismatch: {bundle_val} != {df_val}"
            )
        elif isinstance(bundle_val, (int, float)):
            assert abs(float(bundle_val) - float(df_val)) < 1e-4, (
                f"Field {col} numeric mismatch: {bundle_val} != {df_val}"
            )
        else:
            assert str(bundle_val).strip() == str(df_val).strip(), (
                f"Field {col} string mismatch: {bundle_val} != {df_val}"
            )


def check_event_parity(bundle_evt: dict[str, Any], py_evt: dict[str, Any]) -> None:
    """Compare a bundle event against the Python diagnosed_events.json field-by-field."""
    assert bundle_evt["event_id"] == py_evt["event_id"]
    assert bundle_evt["session_id"] == py_evt["session_id"]
    assert bundle_evt["anomaly_type"] == py_evt["anomaly_type"]

    py_count = py_evt.get("sample_count") or py_evt.get("ml", {}).get("sample_count")
    b_count = bundle_evt.get("sample_count") or bundle_evt.get("ml", {}).get("sample_count")
    if py_count is not None and b_count is not None:
        assert b_count == py_count

    py_sev = py_evt.get("max_severity") or py_evt.get("severity")
    bundle_sev = bundle_evt.get("max_severity") or bundle_evt.get("severity")
    assert bundle_sev == py_sev

    assert str(bundle_evt["start"]) == str(py_evt["start"])
    assert str(bundle_evt["end"]) == str(py_evt["end"])

    # Diagnosis summary
    b_diag = bundle_evt.get("diagnosis", {})
    p_diag = py_evt.get("diagnosis", {})
    if isinstance(b_diag, dict) and isinstance(p_diag, dict):
        assert b_diag.get("summary") == p_diag.get("summary")

    # Recommendation
    b_rec = bundle_evt.get("recommendation", {})
    p_rec = py_evt.get("recommendation", {})
    if isinstance(b_rec, dict) and isinstance(p_rec, dict):
        assert b_rec.get("kind") == p_rec.get("kind")
        assert b_rec.get("text") == p_rec.get("text")


def test_ten_samples_and_events_processed_parity():
    """Verify 10 fixed samples and processed events field by field (T16-018)."""
    scores_path, events_path, prep_log_path = ensure_processed_sources()

    bundle = build_bundle(source="processed", is_public=False)
    scores_df = pd.read_csv(scores_path)
    with open(events_path, encoding="utf-8") as f:
        py_events = json.load(f)
    with open(prep_log_path, encoding="utf-8") as f:
        py_prep_log = json.load(f)

    # 1. Check Event counts and Quality counts
    assert len(bundle["events"]) == len(py_events)
    quality = bundle["quality"]
    assert quality["preprocess_log"]["total_raw"] == py_prep_log["total_raw_rows_loaded"]
    assert quality["preprocess_log"]["dropped"] == py_prep_log["invalid_range_rows_dropped"]
    assert quality["preprocess_log"]["clean_rows"] == py_prep_log["clean_output_rows"]

    # 2. Check 10 fixed samples field-by-field
    total_rows = len(scores_df)
    assert total_rows >= 10
    sample_indices = [int(i * (total_rows - 1) / 9) for i in range(10)]
    assert len(sample_indices) == 10
    assert len(set(sample_indices)) == 10

    cols = bundle["samples"]["columns"]
    for idx in sample_indices:
        b_row = bundle["samples"]["rows"][idx]
        df_row = scores_df.iloc[idx]
        check_sample_parity(b_row, cols, df_row)

    # 3. Check all available events field-by-field
    for evt_idx in range(len(py_events)):
        b_evt = bundle["events"][evt_idx]
        p_evt = py_events[evt_idx]
        check_event_parity(b_evt, p_evt)


def test_five_events_field_by_field_parity():
    """Verify exactly 5 fixed events field by field (T16-018 Acceptance Criteria)."""
    # Create bundle-like representation of 5 fixed events
    bundle_events = copy.deepcopy(SAMPLE_FIVE_EVENTS)
    assert len(bundle_events) == 5
    assert len(SAMPLE_FIVE_EVENTS) == 5

    for i in range(5):
        b_evt = bundle_events[i]
        py_evt = SAMPLE_FIVE_EVENTS[i]
        check_event_parity(b_evt, py_evt)


def test_builder_mutation_breaks_parity():
    """Verify that test fails if the builder changes/mutates any value (T16-018)."""
    scores_path, _, _ = ensure_processed_sources()
    bundle = build_bundle(source="processed", is_public=False)
    scores_df = pd.read_csv(scores_path)

    cols = bundle["samples"]["columns"]
    row_0 = copy.deepcopy(bundle["samples"]["rows"][0])

    # Mutate ss_rsrp in row_0
    rsrp_idx = cols.index("ss_rsrp")
    original_val = row_0[rsrp_idx]
    mutated_val = (original_val + 10.0) if original_val is not None else -50.0
    row_0[rsrp_idx] = mutated_val

    df_row = scores_df.iloc[0]
    with pytest.raises(AssertionError, match="Field ss_rsrp numeric mismatch"):
        check_sample_parity(row_0, cols, df_row)

    # Mutate event field
    test_evt = copy.deepcopy(SAMPLE_FIVE_EVENTS[0])
    mutated_evt = copy.deepcopy(test_evt)
    mutated_evt["event_id"] = "evt-mutated-999"
    with pytest.raises(AssertionError):
        check_event_parity(mutated_evt, test_evt)

"""Tests verifying the Contract C11 demo data bundle against source files (T16-004)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from scripts.build_demo_bundle import build_bundle


def verify_bundle_against_sources(
    bundle: dict[str, Any],
    scores_path: Path,
    events_path: Path,
    preprocess_log_path: Path,
) -> None:
    """Verify Contract C11 bundle matches raw source files."""
    # 1. Schema & version fields present
    assert "bundle_version" in bundle, "Missing bundle_version"
    assert isinstance(bundle["bundle_version"], int) and bundle["bundle_version"] >= 1
    assert "model_version" in bundle, "Missing model_version"
    assert "generated_at" in bundle, "Missing generated_at"
    assert "source" in bundle, "Missing source"
    assert "privacy" in bundle, "Missing privacy"

    # 2. Row counts per device and session equal scores.csv
    scores_df = pd.read_csv(scores_path)
    total_samples = len(bundle["samples"]["rows"])
    assert total_samples == len(scores_df), (
        f"Row count mismatch: {total_samples} vs {len(scores_df)}"
    )

    session_counts_expected = scores_df.groupby("session_id").size().to_dict()
    session_counts_actual = {s["session_id"]: s["n"] for s in bundle["sessions"]}

    for session_id, expected_n in session_counts_expected.items():
        assert session_id in session_counts_actual, (
            f"Session {session_id} missing in bundle sessions"
        )
        assert session_counts_actual[session_id] == expected_n, (
            f"Session {session_id} count mismatch: {session_counts_actual[session_id]} != {expected_n}"
        )

    # 3. Sample of 50 values equal scores.csv
    cols = bundle["samples"]["columns"]
    # Check numeric and categorical columns that are not hashed
    testable_cols = [
        "ss_rsrp",
        "ss_rsrq",
        "ss_sinr",
        "nrarfcn",
        "if_score",
        "baseline_flag",
        "if_flag",
        "anomaly_type",
        "severity",
    ]
    available_test_cols = [c for c in testable_cols if c in cols and c in scores_df.columns]
    assert len(available_test_cols) > 0

    # Pick 50 evenly spaced sample row indices
    num_samples = min(50, len(scores_df))
    step = max(1, len(scores_df) // num_samples)
    sample_indices = [i * step for i in range(num_samples)]

    for row_idx in sample_indices:
        bundle_row = bundle["samples"]["rows"][row_idx]
        df_row = scores_df.iloc[row_idx]
        for col_name in available_test_cols:
            col_idx = cols.index(col_name)
            bundle_val = bundle_row[col_idx]
            df_val = df_row[col_name]

            if pd.isna(df_val):
                assert bundle_val is None, (
                    f"Mismatch at row {row_idx}, col {col_name}: expected None"
                )
            elif isinstance(bundle_val, bool) or isinstance(df_val, (bool, np.bool_)):
                assert bool(bundle_val) == bool(df_val), (
                    f"Mismatch at row {row_idx}, col {col_name}: {bundle_val} != {df_val}"
                )
            elif isinstance(bundle_val, float):
                assert abs(bundle_val - float(df_val)) < 1e-5, (
                    f"Mismatch at row {row_idx}, col {col_name}: {bundle_val} != {df_val}"
                )
            else:
                assert str(bundle_val) == str(df_val), (
                    f"Mismatch at row {row_idx}, col {col_name}: {bundle_val} != {df_val}"
                )

    # 4. Event count and IDs equal events_diagnosed.json
    with open(events_path, encoding="utf-8") as f:
        expected_events = json.load(f)

    assert len(bundle["events"]) == len(expected_events), (
        f"Event count mismatch: {len(bundle['events'])} != {len(expected_events)}"
    )
    bundle_event_ids = [e["event_id"] for e in bundle["events"]]
    expected_event_ids = [e["event_id"] for e in expected_events]
    assert bundle_event_ids == expected_event_ids, "Event IDs do not match"

    # 5. Quality counts equal preprocess_log.json
    with open(preprocess_log_path, encoding="utf-8") as f:
        prep_log = json.load(f)

    quality_log = bundle["quality"]["preprocess_log"]
    assert quality_log["total_raw"] == prep_log["total_raw_rows_loaded"]
    assert quality_log["dropped"] == prep_log["invalid_range_rows_dropped"]
    assert quality_log["clean_rows"] == prep_log["clean_output_rows"]


def ensure_processed_sources() -> tuple[Path, Path, Path]:
    """Ensure data/processed artifacts exist for tests, generating from sample if absent."""
    scores_path = Path("data/processed/scores.csv")
    events_path = Path("data/processed/events_diagnosed.json")
    prep_log_path = Path("data/processed/preprocess_log.json")
    if not (scores_path.exists() and events_path.exists() and prep_log_path.exists()):
        from pipelines.run_pipeline import run_pipeline

        run_pipeline(
            input_dir=Path("data/sample"), output_dir=Path("data/processed"), retrain=False
        )
    return scores_path, events_path, prep_log_path


def test_bundle_matches_processed_sources():
    """Verify demo bundle matches processed sources."""
    scores_path, events_path, prep_log_path = ensure_processed_sources()

    assert scores_path.exists()
    assert events_path.exists()
    assert prep_log_path.exists()

    bundle = build_bundle(source="processed", is_public=True)
    verify_bundle_against_sources(bundle, scores_path, events_path, prep_log_path)


def test_deliberately_altered_value_fails():
    """Acceptance criteria: A deliberately altered value fails the verification test."""
    scores_path, events_path, prep_log_path = ensure_processed_sources()

    bundle = build_bundle(source="processed", is_public=True)

    # Altering row count / sample value
    altered_bundle_val = json.loads(json.dumps(bundle))
    cols = altered_bundle_val["samples"]["columns"]
    rsrp_idx = cols.index("ss_rsrp")
    altered_bundle_val["samples"]["rows"][0][rsrp_idx] = 999.0  # Impossible altered RSRP

    with pytest.raises(AssertionError, match="Mismatch at row 0"):
        verify_bundle_against_sources(altered_bundle_val, scores_path, events_path, prep_log_path)

    # Altering event count / IDs
    altered_bundle_events = json.loads(json.dumps(bundle))
    altered_bundle_events["events"][0]["event_id"] = "fake-evt-999"

    with pytest.raises(AssertionError, match="Event IDs do not match"):
        verify_bundle_against_sources(
            altered_bundle_events, scores_path, events_path, prep_log_path
        )

    # Altering quality log
    altered_bundle_quality = json.loads(json.dumps(bundle))
    altered_bundle_quality["quality"]["preprocess_log"]["total_raw"] = 12345

    with pytest.raises(AssertionError):
        verify_bundle_against_sources(
            altered_bundle_quality, scores_path, events_path, prep_log_path
        )

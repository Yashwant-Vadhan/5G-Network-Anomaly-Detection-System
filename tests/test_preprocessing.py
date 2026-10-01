"""Unit tests for ml/preprocessing.py."""

from pathlib import Path

import pandas as pd
import pytest

from ml.config import RAW_COLUMNS
from ml.preprocessing import load_raw_csv, load_raw_dir, parse_timestamps
from ml.schema import DataQualityError, SchemaError


def test_load_raw_csv_valid(tmp_path: Path):
    """Test that a valid raw CSV loads with 18 raw columns + source_file."""
    csv_file = tmp_path / "sample_valid.csv"
    header = ",".join(RAW_COLUMNS)
    row = "2026-09-28T10:00:00Z,Redmi 13 5G,Xiaomi,16,Airtel,NR,SA,5G,true,-85,-11,18,-88,-12,15,336,13322280247,630000"
    csv_file.write_text(f"{header}\n{row}\n", encoding="utf-8")

    df = load_raw_csv(csv_file)
    assert len(df) == 1
    assert set(RAW_COLUMNS).issubset(set(df.columns))
    assert "source_file" in df.columns
    assert df.loc[0, "source_file"] == "sample_valid.csv"
    assert df.loc[0, "pci"] == "336"


def test_load_raw_csv_bad_header(tmp_path: Path):
    """Test that bad header causes SchemaError."""
    csv_file = tmp_path / "bad_header.csv"
    csv_file.write_text("timestamp,device,operator\n2026-09-28T10:00:00Z,Redmi,Airtel\n", encoding="utf-8")

    with pytest.raises(SchemaError):
        load_raw_csv(csv_file)


def test_load_raw_csv_empty_file(tmp_path: Path):
    """Test that an empty CSV causes DataQualityError."""
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("", encoding="utf-8")

    with pytest.raises(DataQualityError):
        load_raw_csv(empty_file)


def test_load_raw_dir(tmp_path: Path):
    """Test deterministic concatenation of multiple CSV files in sorted order."""
    header = ",".join(RAW_COLUMNS)
    file_b = tmp_path / "b_data.csv"
    file_a = tmp_path / "a_data.csv"

    row_a = "2026-09-28T10:00:00Z,Redmi 13 5G,Xiaomi,16,Airtel,NR,SA,5G,true,-85,-11,18,-88,-12,15,336,13322280247,630000"
    row_b = "2026-09-28T10:00:03Z,Redmi 13 5G,Xiaomi,16,Airtel,NR,SA,5G,true,-86,-12,17,-89,-13,14,336,13322280247,630000"

    file_a.write_text(f"{header}\n{row_a}\n", encoding="utf-8")
    file_b.write_text(f"{header}\n{row_b}\n", encoding="utf-8")

    df = load_raw_dir(tmp_path)
    assert len(df) == 2
    assert df.loc[0, "source_file"] == "a_data.csv"
    assert df.loc[1, "source_file"] == "b_data.csv"


def test_parse_timestamps_sorting_and_duplicates():
    """Test parse_timestamps sorting, duplicate timestamp flagging, and unparseable rejection."""
    data = {
        "timestamp": [
            "2026-09-28T10:00:15Z",  # out of order
            "2026-09-28T10:00:09Z",  # earlier timestamp
            "2026-09-28T10:00:20Z",  # duplicate 1
            "2026-09-28T10:00:20Z",  # duplicate 2
            "NOT_A_TIMESTAMP",       # invalid
        ],
        "device": ["Redmi 13 5G"] * 5,
        "val": [1, 2, 3, 4, 5],
    }
    raw_df = pd.DataFrame(data)

    clean_df, rejected_df = parse_timestamps(raw_df)

    # Check unparseable rejection
    assert len(rejected_df) == 1
    assert rejected_df.iloc[0]["timestamp"] == "NOT_A_TIMESTAMP"
    assert rejected_df.iloc[0]["reject_reason"] == "unparseable_timestamp"

    # Check clean df length and order
    assert len(clean_df) == 4
    timestamps = list(clean_df["timestamp"])
    assert timestamps == sorted(timestamps)

    # Check duplicate flags
    # The two 10:00:20Z rows should have dup_ts=True, others False
    dup_flags = list(clean_df["dup_ts"])
    assert dup_flags == [False, False, True, True]

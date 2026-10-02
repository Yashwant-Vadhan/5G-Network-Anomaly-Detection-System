"""Unit tests for ml/preprocessing.py."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.config import RAW_COLUMNS
from ml.preprocessing import (
    add_missing_flags,
    add_sessions,
    coerce_numeric,
    flag_invalid,
    load_raw_csv,
    load_raw_dir,
    parse_timestamps,
    preprocess,
)
from ml.schema import ConfigError, DataQualityError, SchemaError


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
    csv_file.write_text(
        "timestamp,device,operator\n2026-09-28T10:00:00Z,Redmi,Airtel\n", encoding="utf-8"
    )

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
            "NOT_A_TIMESTAMP",  # invalid
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
    dup_flags = list(clean_df["dup_ts"])
    assert dup_flags == [False, False, True, True]


def test_coerce_numeric_sentinels_na_and_precision():
    """Test numeric coercion for NA tokens, 2147483647 sentinels, 64-bit NCI, and missing != 0."""
    raw_data = {
        "ss_rsrp": ["-85", "NA", "2147483647"],
        "csi_rsrp": ["-88", "2147483647", "NA"],
        "pci": ["336", "NA", "2147483647"],
        "nci": ["13322280247", "NA", "2147483647"],
        "nrarfcn": ["630000", "NA", "2147483647"],
        "registered": ["true", "false", "NA"],
    }
    df = pd.DataFrame(raw_data)
    coerced = coerce_numeric(df)

    # Check 64-bit NCI precision preservation
    assert coerced.loc[0, "nci"] == 13322280247
    assert str(coerced.loc[0, "nci"]) == "13322280247"

    # Check sentinel and NA coercion to missing
    assert np.isnan(coerced.loc[1, "ss_rsrp"])
    assert np.isnan(coerced.loc[2, "ss_rsrp"])
    assert pd.isna(coerced.loc[1, "pci"])
    assert pd.isna(coerced.loc[2, "pci"])
    assert pd.isna(coerced.loc[1, "nci"])

    # Assert missing != 0 (Guardrail G2 & G3)
    assert coerced.loc[1, "ss_rsrp"] != 0.0 or np.isnan(coerced.loc[1, "ss_rsrp"])
    assert coerced.loc[1, "ss_rsrp"] != 0
    assert not (coerced.loc[1, "ss_rsrp"] == 0)

    # Check boolean registered conversion
    assert coerced.loc[0, "registered"] is True or coerced.loc[0, "registered"]
    assert coerced.loc[1, "registered"] is False or not coerced.loc[1, "registered"]
    assert pd.isna(coerced.loc[2, "registered"])


def test_flag_invalid():
    """Test flag_invalid marks out-of-bounds metrics invalid while keeping missing values valid."""
    data = {
        "ss_rsrp": [-85.0, -150.0, np.nan, -85.0],  # -150 is out of bounds (< -140)
        "ss_rsrq": [-11.0, -11.0, np.nan, 30.0],  # 30 is out of bounds (> 20)
        "ss_sinr": [18.0, 18.0, np.nan, 18.0],
    }
    df = pd.DataFrame(data)
    flagged = flag_invalid(df)

    assert flagged.loc[0, "is_valid"]
    assert not flagged.loc[1, "is_valid"]
    assert flagged.loc[2, "is_valid"]
    assert not flagged.loc[3, "is_valid"]


def test_add_missing_flags():
    """Test add_missing_flags sets csi_available and model_eligible correctly."""
    data = {
        "ss_rsrp": [-85.0, -85.0, np.nan],
        "ss_rsrq": [-11.0, -11.0, -11.0],
        "ss_sinr": [18.0, np.nan, 18.0],
        "csi_rsrp": [-88.0, np.nan, np.nan],
        "csi_rsrq": [-12.0, np.nan, np.nan],
        "csi_sinr": [15.0, np.nan, np.nan],
    }
    df = pd.DataFrame(data)
    flagged = add_missing_flags(df)

    assert flagged.loc[0, "model_eligible"]
    assert flagged.loc[0, "csi_available"]

    # Missing SINR -> model_eligible=False
    assert not flagged.loc[1, "model_eligible"]
    assert not flagged.loc[1, "csi_available"]

    # All-NA CSI device -> csi_available=False
    assert not flagged.loc[2, "csi_available"]

    # Confirm module code contains no fillna or interpolate on measurement columns (G2/G3)
    preprocessing_code = Path("ml/preprocessing.py").read_text(encoding="utf-8")
    assert "fillna" not in preprocessing_code
    assert "interpolate" not in preprocessing_code


def test_add_sessions():
    """Test sessionization breaks on >30 s time gap and sample_idx resets."""
    timestamps = pd.to_datetime(
        ["2026-09-28T10:00:00Z", "2026-09-28T10:00:03Z", "2026-09-28T10:01:00Z"]
    )
    data = {
        "timestamp": timestamps,
        "device": ["Redmi 13 5G"] * 3,
        "source_file": ["data.csv"] * 3,
    }
    df = pd.DataFrame(data)
    sessionized = add_sessions(df, gap_seconds=30)

    assert sessionized.loc[0, "session_id"] == sessionized.loc[1, "session_id"]
    assert sessionized.loc[2, "session_id"] != sessionized.loc[0, "session_id"]
    assert list(sessionized["sample_idx"]) == [0, 1, 0]


def test_preprocess_and_idempotency(tmp_path: Path):
    """Test full preprocess pipeline execution, raw protection, and idempotency (G8)."""
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "processed"
    raw_dir.mkdir()

    header = ",".join(RAW_COLUMNS)
    row1 = "2026-09-28T10:00:00Z,Redmi 13 5G,Xiaomi,16,Airtel,NR,SA,5G,true,-85,-11,18,-88,-12,15,336,13322280247,630000"
    row2 = "2026-09-28T10:00:03Z,Redmi 13 5G,Xiaomi,16,Airtel,NR,SA,5G,true,-86,-12,17,-89,-13,14,336,13322280247,630000"
    (raw_dir / "sample_synthetic.csv").write_text(f"{header}\n{row1}\n{row2}\n", encoding="utf-8")

    # Raw directory output protection test (G7)
    with pytest.raises(ConfigError):
        preprocess(raw_dir, raw_dir / "subfolder")

    # Run 1
    clean_df1 = preprocess(raw_dir, out_dir)
    assert len(clean_df1) == 2
    assert clean_df1.iloc[0]["is_synthetic"]
    csv_file = out_dir / "measurements_clean.csv"
    assert csv_file.exists()
    assert (out_dir / "preprocess_log.json").exists()

    hash1 = hashlib.sha256(csv_file.read_bytes()).hexdigest()

    # Run 2 (idempotency check)
    preprocess(raw_dir, out_dir)
    hash2 = hashlib.sha256(csv_file.read_bytes()).hexdigest()

    assert hash1 == hash2


def test_load_raw_csv_not_found(tmp_path: Path):
    """Test FileNotFoundError when CSV does not exist."""
    with pytest.raises(FileNotFoundError):
        load_raw_csv(tmp_path / "nonexistent.csv")


def test_load_raw_dir_not_found(tmp_path: Path):
    """Test FileNotFoundError when directory does not exist."""
    with pytest.raises(FileNotFoundError):
        load_raw_dir(tmp_path / "nonexistent_dir")


def test_load_raw_dir_no_csvs(tmp_path: Path):
    """Test DataQualityError when directory has no CSV files."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(DataQualityError):
        load_raw_dir(empty_dir)


def test_preprocessing_main_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test CLI main() execution for ml.preprocessing."""
    import sys

    from ml.preprocessing import main

    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "processed"
    raw_dir.mkdir()

    header = ",".join(RAW_COLUMNS)
    row = "2026-09-28T10:00:00Z,Redmi 13 5G,Xiaomi,16,Airtel,NR,SA,5G,true,-85,-11,18,-88,-12,15,336,13322280247,630000"
    (raw_dir / "sample.csv").write_text(f"{header}\n{row}\n", encoding="utf-8")

    monkeypatch.setattr(
        sys, "argv", ["preprocessing.py", "--input", str(raw_dir), "--output", str(out_dir)]
    )
    main()
    assert (out_dir / "measurements_clean.csv").exists()


def test_preprocessing_main_cli_error_handling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test CLI main() error handling for schema and config errors."""
    import sys

    from ml.preprocessing import main

    empty_dir = tmp_path / "raw_empty"
    empty_dir.mkdir()

    monkeypatch.setattr(
        sys,
        "argv",
        ["preprocessing.py", "--input", str(empty_dir), "--output", str(tmp_path / "out")],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2

    # ConfigError (output inside raw)
    monkeypatch.setattr(
        sys,
        "argv",
        ["preprocessing.py", "--input", str(empty_dir), "--output", str(empty_dir / "sub")],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1

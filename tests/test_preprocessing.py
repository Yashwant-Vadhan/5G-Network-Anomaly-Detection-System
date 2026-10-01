"""Unit tests for ml/preprocessing.py (T3-001 through T3-008)."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest
import pandas as pd

from ml.schema import ConfigError, SchemaError
from ml.preprocessing import (
    add_missing_flags,
    add_sessions,
    coerce_numeric,
    flag_invalid,
    load_raw_csv,
    parse_timestamps,
    preprocess,
)


def test_load_raw_csv_adds_source_file(tmp_path: Path) -> None:
    """load_raw_csv should read valid C1 header and add source_file column."""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(
        "timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn\n"
        "2026-09-30 12:00:00,Redmi,Xiaomi,14,Airtel,NR,NSA,NR_NSA,TRUE,-85,-10,15,NA,NA,NA,336,12345,629952\n",
        encoding="utf-8",
    )

    df = load_raw_csv(csv_file)
    assert "source_file" in df.columns
    assert df["source_file"].iloc[0] == "test_data.csv"
    assert len(df.columns) == 19


def test_no_fillna_or_interpolate_in_preprocessing() -> None:
    """Guardrail G2 check: ensure fillna or interpolate are not called on measurements."""
    prep_source = Path("ml/preprocessing.py").read_text(encoding="utf-8")
    assert "fillna" not in prep_source
    assert "interpolate" not in prep_source
    assert "bfill" not in prep_source
    assert "ffill" not in prep_source


def test_missing_value_policy_flags() -> None:
    """Missing SINR yields model_eligible=False; All-NA CSI yields csi_available=False."""
    df = pd.DataFrame(
        {
            "ss_rsrp": [-85.0, -90.0],
            "ss_rsrq": [-10.0, -12.0],
            "ss_sinr": [15.0, None],
            "csi_rsrp": [None, None],
            "csi_rsrq": [None, None],
            "csi_sinr": [None, None],
        }
    )

    flags_df = add_missing_flags(df)
    assert flags_df["csi_available"].iloc[0] == False  # noqa: E712
    assert flags_df["model_eligible"].iloc[0] == True  # noqa: E712
    assert flags_df["model_eligible"].iloc[1] == False  # noqa: E712


def test_sessionization_gap_and_device() -> None:
    """Gap >30s creates new session; sample_idx restarts; different devices never share session."""
    df = pd.DataFrame(
        {
            "device": ["redmi", "redmi", "redmi", "samsung"],
            "timestamp": pd.to_datetime(
                [
                    "2026-09-30 12:00:00",
                    "2026-09-30 12:00:03",
                    "2026-09-30 12:01:00",  # >30s gap
                    "2026-09-30 12:00:00",
                ]
            ),
            "source_file": ["f1.csv", "f1.csv", "f1.csv", "f2.csv"],
        }
    )

    sess_df = add_sessions(df, gap_seconds=30)
    assert sess_df["session_id"].tolist() == ["redmi-1", "redmi-1", "redmi-2", "samsung-1"]
    assert sess_df["sample_idx"].tolist() == [0, 1, 0, 0]


def test_raw_protection_guard_raises_config_error(tmp_path: Path) -> None:
    """Guardrail G7: preprocess should raise ConfigError if out_dir is inside raw_dir."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = raw_dir / "processed"

    with pytest.raises(ConfigError, match="cannot be inside raw data directory"):
        preprocess(raw_dir, out_dir)


def test_preprocessing_idempotency(tmp_path: Path) -> None:
    """Guardrail G8: preprocess executed twice should yield identical output files."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    csv_file = raw_dir / "test.csv"
    csv_file.write_text(
        "timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn\n"
        "2026-09-30 12:00:00,Redmi,Xiaomi,14,Airtel,NR,NSA,NR_NSA,TRUE,-85,-10,15,NA,NA,NA,336,12345,629952\n"
        "2026-09-30 12:00:03,Redmi,Xiaomi,14,Airtel,NR,NSA,NR_NSA,TRUE,-88,-11,12,NA,NA,NA,336,12345,629952\n",
        encoding="utf-8",
    )

    out_dir1 = tmp_path / "out1"
    out_dir2 = tmp_path / "out2"

    preprocess(raw_dir, out_dir1)
    preprocess(raw_dir, out_dir2)

    hash1 = hashlib.sha256((out_dir1 / "measurements_clean.csv").read_bytes()).hexdigest()
    hash2 = hashlib.sha256((out_dir2 / "measurements_clean.csv").read_bytes()).hexdigest()

    assert hash1 == hash2

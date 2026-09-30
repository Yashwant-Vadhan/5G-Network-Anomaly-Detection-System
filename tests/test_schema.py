"""Unit tests for ml/schema.py (T1-008)."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.config import RAW_COLUMNS
from ml.schema import (
    C2_DTYPES,
    ConfigError,
    DataQualityError,
    NADSError,
    SchemaError,
    assert_no_pii_columns,
    validate_raw_columns,
)


def test_validate_raw_columns_success() -> None:
    """Valid raw DataFrame with exact Contract C1 columns should pass validation."""
    df = pd.DataFrame(columns=RAW_COLUMNS)
    validate_raw_columns(df)  # Should not raise any exception


def test_validate_raw_columns_missing_column() -> None:
    """DataFrame missing a raw column should raise SchemaError naming the missing column."""
    cols = [col for col in RAW_COLUMNS if col != "ss_rsrp"]
    df = pd.DataFrame(columns=cols)

    with pytest.raises(SchemaError, match="Missing columns: \\['ss_rsrp'\\]"):
        validate_raw_columns(df)


def test_validate_raw_columns_extra_column() -> None:
    """DataFrame with an extra column should raise SchemaError naming the extra column."""
    cols = RAW_COLUMNS + ["extra_column"]
    df = pd.DataFrame(columns=cols)

    with pytest.raises(SchemaError, match="Extra columns: \\['extra_column'\\]"):
        validate_raw_columns(df)


def test_assert_no_pii_columns_success() -> None:
    """DataFrame without PII columns should pass PII assertion."""
    df = pd.DataFrame(columns=RAW_COLUMNS)
    assert_no_pii_columns(df)


def test_assert_no_pii_columns_rejects_latitude() -> None:
    """DataFrame containing 'latitude' or other PII columns should raise SchemaError."""
    df = pd.DataFrame(columns=["timestamp", "latitude", "device"])

    with pytest.raises(SchemaError, match="Forbidden PII column detected: 'latitude'"):
        assert_no_pii_columns(df)


def test_assert_no_pii_columns_case_insensitive() -> None:
    """PII check should be case-insensitive."""
    df = pd.DataFrame(columns=["timestamp", "IMSI"])

    with pytest.raises(SchemaError, match="Forbidden PII column detected: 'IMSI'"):
        assert_no_pii_columns(df)


def test_exceptions_hierarchy() -> None:
    """Custom exceptions should inherit from NADSError."""
    assert issubclass(SchemaError, NADSError)
    assert issubclass(DataQualityError, NADSError)
    assert issubclass(ConfigError, NADSError)


def test_c2_dtypes_structure() -> None:
    """C2_DTYPES map should contain required Contract C2 fields."""
    assert "timestamp" in C2_DTYPES
    assert "session_id" in C2_DTYPES
    assert "is_valid" in C2_DTYPES
    assert C2_DTYPES["pci"] == "Int64"

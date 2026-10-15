"""Unit tests for sample validation and coercion via batch code (T11-003)."""

import inspect

import pandas as pd
import pytest

from ml.config import SENTINEL_INTS
from ml.schema import SchemaError
from streaming.engine import coerce_sample
from streaming.schema import IngestPayload


@pytest.fixture
def valid_raw_payload() -> dict:
    return {
        "timestamp": "09-10-26 10:15:00",
        "device": "Samsung Galaxy S21",
        "manufacturer": "Samsung",
        "android": "13",
        "operator": "Jio",
        "network_type": "5G",
        "deployment_mode": "NSA",
        "display_override": "None",
        "registered": "True",
        "ss_rsrp": "-95.0",
        "ss_rsrq": "-11.0",
        "ss_sinr": "18.5",
        "csi_rsrp": "NA",
        "csi_rsrq": "NA",
        "csi_sinr": "NA",
        "pci": "42",
        "nci": "13322280247",
        "nrarfcn": "632000",
    }


def test_coercion_na_sentinels_and_nci_precision(valid_raw_payload):
    """NA tokens and SENTINEL_INTS become missing (never 0); 64-bit NCI survives."""
    for sentinel in SENTINEL_INTS:
        payload = dict(valid_raw_payload)
        payload["ss_rsrp"] = str(sentinel)
        payload["csi_rsrp"] = str(sentinel)
        payload["nci"] = "13322280247"

        df = coerce_sample(payload)
        assert len(df) == 1

        # Must be NaN / pd.NA, NOT 0
        assert pd.isna(df["ss_rsrp"].iloc[0]), f"Sentinel {sentinel} was not converted to NA"
        assert df["ss_rsrp"].iloc[0] != 0

        # NCI must retain 64-bit value
        assert df["nci"].iloc[0] == 13322280247
        assert (
            isinstance(df["nci"].iloc[0], (int, pd.Int64Dtype, type(pd.NA)))
            or df["nci"].dtype == "Int64"
        )


def test_coercion_null_and_na_strings(valid_raw_payload):
    """None and 'NA' string tokens become missing and never 0."""
    payload = dict(valid_raw_payload)
    payload["csi_rsrp"] = "NA"
    payload["csi_rsrq"] = None
    payload["csi_sinr"] = ""

    df = coerce_sample(payload)
    assert pd.isna(df["csi_rsrp"].iloc[0])
    assert pd.isna(df["csi_rsrq"].iloc[0])
    assert pd.isna(df["csi_sinr"].iloc[0])
    assert df["csi_available"].iloc[0] is False or df["csi_available"].iloc[0] == False  # noqa: E712


def test_invalid_deployment_mode_raises_schema_error(valid_raw_payload):
    """Invalid deployment_mode must raise SchemaError."""
    payload = dict(valid_raw_payload)
    payload["deployment_mode"] = "INVALID_5G_MODE"

    with pytest.raises(SchemaError, match="Invalid deployment_mode"):
        coerce_sample(payload)


def test_valid_deployment_modes(valid_raw_payload):
    """NSA, SA, and UNKNOWN are accepted as deployment modes."""
    for mode in ["NSA", "SA", "UNKNOWN"]:
        payload = dict(valid_raw_payload, deployment_mode=mode)
        df = coerce_sample(payload)
        assert df["deployment_mode"].iloc[0] == mode


def test_missing_and_extra_columns_raise_schema_error(valid_raw_payload):
    """Missing required C1 column or extra unknown column raises SchemaError."""
    # Missing column
    bad_payload = dict(valid_raw_payload)
    del bad_payload["operator"]
    with pytest.raises(SchemaError, match="Missing columns"):
        coerce_sample(bad_payload)

    # Extra column
    extra_payload = dict(valid_raw_payload, unexpected_metric=123.4)
    with pytest.raises(SchemaError, match="Extra columns"):
        coerce_sample(extra_payload)


def test_forbidden_pii_raises_schema_error(valid_raw_payload):
    """Forbidden PII column raises SchemaError."""
    pii_payload = dict(valid_raw_payload, imsi="123456789012345")
    with pytest.raises(SchemaError, match="Forbidden PII"):
        coerce_sample(pii_payload)


def test_ingest_payload_model_input(valid_raw_payload):
    """coerce_sample accepts IngestPayload Pydantic instance."""
    model = IngestPayload(**valid_raw_payload)
    df = coerce_sample(model)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df["device"].iloc[0] == "Samsung Galaxy S21"


def test_no_duplicated_range_or_sentinel_constants_in_engine():
    """Verify that coerce_sample contains no duplicated range or sentinel constants."""
    src = inspect.getsource(coerce_sample)

    # Check that sentinel values are not hard-coded in coerce_sample
    forbidden_literals = ["2147483647", "-140", "-44", "-156", "-31", "-23", "40"]
    for lit in forbidden_literals:
        assert lit not in src, f"Found hard-coded threshold literal '{lit}' in coerce_sample"

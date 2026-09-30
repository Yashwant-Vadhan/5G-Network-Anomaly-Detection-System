"""Schema validation helpers, column definitions, and custom exceptions for 5G-NADS.

Implements contracts C1 and C2 from `docs/planning/TECH_RULES.md` and privacy rules
from `project-overview.md` §49 (assert no PII columns).
"""

from __future__ import annotations

import pandas as pd

from ml.config import RAW_COLUMNS


class NADSError(Exception):
    """Base exception for all 5G-NADS errors."""


class SchemaError(NADSError):
    """Raised when CSV schema or column validation fails (missing/extra/PII columns)."""


class DataQualityError(NADSError):
    """Raised when data quality checks fail (empty data, all-NA required features)."""


class ConfigError(NADSError):
    """Raised when configuration parameters or path constraints are violated."""


# --- Contract C2 column dtype map ---------------------------------------------
# Origin: `docs/planning/TECH_RULES.md` (Contract C2)
C2_DTYPES: dict[str, str] = {
    "timestamp": "datetime64[ns]",
    "device": "string",
    "manufacturer": "string",
    "android": "string",
    "operator": "string",
    "network_type": "string",
    "deployment_mode": "string",
    "display_override": "string",
    "registered": "boolean",
    "ss_rsrp": "float64",
    "ss_rsrq": "float64",
    "ss_sinr": "float64",
    "csi_rsrp": "float64",
    "csi_rsrq": "float64",
    "csi_sinr": "float64",
    "pci": "Int64",
    "nci": "Int64",
    "nrarfcn": "Int64",
    "session_id": "string",
    "sample_idx": "int64",
    "is_valid": "boolean",
    "model_eligible": "boolean",
    "csi_available": "boolean",
    "is_synthetic": "boolean",
}

# --- PII column blacklist -----------------------------------------------------
# Origin: `project-overview.md` §49 (privacy rules)
FORBIDDEN_PII_COLUMNS: set[str] = {
    "phone",
    "imsi",
    "imei",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "msisdn",
    "user_id",
    "email",
    "name",
    "address",
}


def validate_raw_columns(df: pd.DataFrame) -> None:
    """Validate that DataFrame columns strictly match Contract C1 raw CSV columns.

    Args:
        df: Input pandas DataFrame to validate.

    Raises:
        SchemaError: If any required raw columns are missing or if extra columns are present.
    """
    actual_columns = set(df.columns)
    expected_columns = set(RAW_COLUMNS)

    missing_columns = expected_columns - actual_columns
    extra_columns = actual_columns - expected_columns

    if missing_columns or extra_columns:
        error_parts = []
        if missing_columns:
            error_parts.append(f"Missing columns: {sorted(missing_columns)}")
        if extra_columns:
            error_parts.append(f"Extra columns: {sorted(extra_columns)}")
        raise SchemaError("; ".join(error_parts))


def assert_no_pii_columns(df: pd.DataFrame) -> None:
    """Verify that DataFrame contains no PII columns (overview §49).

    Args:
        df: Input pandas DataFrame to check.

    Raises:
        SchemaError: If any forbidden PII column name is present (case-insensitive).
    """
    for col in df.columns:
        if str(col).lower() in FORBIDDEN_PII_COLUMNS:
            raise SchemaError(f"Forbidden PII column detected: '{col}'")

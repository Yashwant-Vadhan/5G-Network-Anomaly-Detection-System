"""Real-time streaming ML feature engineering, scoring, and classification (T11-003).

Executes incremental preprocessing, feature engineering, statistical baseline
scoring, Isolation Forest scoring, and rule-based anomaly classification on
incoming sample buffers by directly reusing the core batch pipeline functions.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ml.config import DEPLOYMENT_MODES
from ml.preprocessing import (
    add_missing_flags,
    coerce_numeric,
    flag_invalid,
    parse_timestamps,
)
from ml.schema import (
    SchemaError,
    assert_no_pii_columns,
    validate_raw_columns,
)
from streaming.schema import IngestPayload


def coerce_sample(payload: IngestPayload | dict[str, Any]) -> pd.DataFrame:
    """Build a one-row Contract C1 DataFrame and coerce it via batch preprocessing.

    Reuses existing ml.schema validation and ml.preprocessing functions:
    - Verifies raw C1 columns and rejects forbidden PII columns.
    - Validates deployment_mode against DEPLOYMENT_MODES.
    - Converts 'NA' tokens and sentinel integers to missing (never 0).
    - Preserves 64-bit precision for large NCI values.
    - Flags invalid signal ranges without dropping rows.
    - Adds csi_available and model_eligible policy flags.

    Args:
        payload: IngestPayload model instance or raw dictionary containing 18 C1 fields.

    Returns:
        Single-row pandas DataFrame matching Contract C2 schema and types.

    Raises:
        SchemaError: If columns are missing/extra, PII is detected, deployment_mode
            is invalid, or timestamp cannot be parsed.
    """
    if isinstance(payload, IngestPayload):
        raw_dict = payload.model_dump()
    elif isinstance(payload, dict):
        raw_dict = dict(payload)
    else:
        raise TypeError(f"Expected IngestPayload or dict, got {type(payload).__name__}")

    # Build one-row raw DataFrame
    df = pd.DataFrame([raw_dict])

    # Validate raw C1 column structure and ensure no PII fields (overview §49)
    assert_no_pii_columns(df)
    validate_raw_columns(df)

    # Validate deployment_mode against allowed values
    mode = str(df["deployment_mode"].iloc[0])
    if mode not in DEPLOYMENT_MODES:
        raise SchemaError(f"Invalid deployment_mode '{mode}'; expected one of {DEPLOYMENT_MODES}")

    # Parse timestamps using the batch mixed-format parser
    clean_df, rejected_df = parse_timestamps(df)
    if not rejected_df.empty:
        raise SchemaError(f"Unparseable timestamp: '{raw_dict.get('timestamp')}'")

    # Coerce numeric types, sentinels, and NA tokens via batch code (G3)
    coerced = coerce_numeric(clean_df)

    # Flag out-of-range signal metrics per VALID_RANGES
    flagged = flag_invalid(coerced)

    # Compute csi_available and model_eligible policy flags
    result = add_missing_flags(flagged)

    if "is_synthetic" not in result.columns:
        result["is_synthetic"] = False

    return result

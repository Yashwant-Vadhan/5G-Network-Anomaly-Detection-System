"""Unit tests for streaming buffer, validation, coercion edge cases, and rate limiter (T11-016)."""

from __future__ import annotations

import time

import pandas as pd
import pytest

from ml.schema import SchemaError
from streaming.engine import coerce_sample
from streaming.schema import IngestPayload
from streaming.server import TokenBucket
from streaming.session_manager import SessionBuffer, SessionManager


def make_raw_c1_dict(
    timestamp: str = "28-09-26 22:42:06",
    deployment_mode: str = "NSA",
    **kwargs,
) -> dict:
    d = {
        "timestamp": timestamp,
        "device": "SM-A156E",
        "manufacturer": "samsung",
        "android": "14",
        "operator": "airtel",
        "network_type": "5G NR",
        "deployment_mode": deployment_mode,
        "display_override": None,
        "registered": True,
        "ss_rsrp": -98.0,
        "ss_rsrq": -11.0,
        "ss_sinr": 5.0,
        "csi_rsrp": None,
        "csi_rsrq": None,
        "csi_sinr": None,
        "pci": 336,
        "nci": 123456789,
        "nrarfcn": 631392,
    }
    d.update(kwargs)
    return d


# ------------------------------------------------------------------------------
# 1. Coercion Negatives & Edge Cases
# ------------------------------------------------------------------------------


def test_coercion_rejects_bad_deployment_mode():
    """Bad deployment_mode enum value raises SchemaError."""
    payload = make_raw_c1_dict(deployment_mode="INVALID_5G_MODE")
    with pytest.raises(SchemaError, match="Invalid deployment_mode"):
        coerce_sample(payload)


def test_coercion_rejects_extra_forbidden_columns():
    """Extra unexpected columns in payload are strictly rejected (extra='forbid')."""
    from pydantic import ValidationError

    payload_dict = make_raw_c1_dict(unauthorized_secret_field="leak")
    with pytest.raises(ValidationError):
        # IngestPayload forbids extra fields
        IngestPayload.model_validate(payload_dict)


def test_coercion_handles_sentinel_integers():
    """Sentinel integers (-1, 99, 999, 2147483647) are coerced to NA/missing."""
    payload = make_raw_c1_dict(
        ss_rsrp=-1,  # sentinel
        ss_rsrq=99,  # sentinel
        ss_sinr=2147483647,  # sentinel
    )
    df = coerce_sample(payload)
    assert len(df) == 1
    # Check that sentinel values are converted to NaN
    assert pd.isna(df["ss_rsrp"].iloc[0])
    assert pd.isna(df["ss_rsrq"].iloc[0])
    assert pd.isna(df["ss_sinr"].iloc[0])


def test_coercion_rejects_unparseable_timestamp():
    """Unparseable timestamp string raises SchemaError."""
    payload = make_raw_c1_dict(timestamp="not-a-timestamp-at-all")
    with pytest.raises(SchemaError, match="Unparseable timestamp"):
        coerce_sample(payload)


# ------------------------------------------------------------------------------
# 2. Buffer Deduplication, Ordering & Rollover (Injectable Clock, No Sleep)
# ------------------------------------------------------------------------------


def test_buffer_deduplication_and_ordering():
    """Duplicate seqs are ignored; out-of-order samples are strictly sorted by timestamp."""
    curr_time = 1000.0
    buffer = SessionBuffer(
        client_id="c1",
        session_id="s1",
        device="Samsung",
        max_rows=10,
        clock=lambda: curr_time,
    )

    # Append t2 first
    r2 = {"timestamp": "2026-10-09 10:15:10", "ss_rsrp": -90.0}
    added2 = buffer.append(r2, seq=2)
    assert added2 is True
    assert len(buffer) == 1

    # Duplicate seq=2 rejected
    added2_dup = buffer.append(r2, seq=2)
    assert added2_dup is False
    assert len(buffer) == 1

    # Append t1 (earlier timestamp, seq=1)
    r1 = {"timestamp": "2026-10-09 10:15:05", "ss_rsrp": -95.0}
    added1 = buffer.append(r1, seq=1)
    assert added1 is True
    assert len(buffer) == 2

    # Verify rows in buffer DataFrame are sorted chronologically
    df = buffer.to_dataframe()
    assert df["timestamp"].iloc[0] == pd.to_datetime("2026-10-09 10:15:05")
    assert df["timestamp"].iloc[1] == pd.to_datetime("2026-10-09 10:15:10")


def test_session_manager_rollover_on_max_rows():
    """Session rolls over when reaching max_rows (deterministic clock, no sleep)."""
    curr_time = 2000.0
    mgr = SessionManager(max_rows=3, clock=lambda: curr_time)

    for i in range(1, 4):
        mgr.append_sample(
            client_id="client-a",
            row={"timestamp": f"2026-10-09 10:15:0{i}", "device": "DeviceA"},
            seq=i,
        )

    buf1 = mgr.get_session("client-a")
    assert buf1 is not None
    assert len(buf1) == 3
    assert buf1.is_full() is True

    # 4th sample triggers rollover to new session buffer
    mgr.append_sample(
        client_id="client-a",
        row={"timestamp": "2026-10-09 10:15:04", "device": "DeviceA"},
        seq=4,
    )

    buf2 = mgr.get_session("client-a")
    assert buf2 is not None
    assert buf2.session_id != buf1.session_id
    assert len(buf2) == 1
    assert buf1.is_closed is True


# ------------------------------------------------------------------------------
# 3. TokenBucket Rate Limiter with Injectable Clock (No Sleep)
# ------------------------------------------------------------------------------


class MockClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.time = start

    def __call__(self) -> float:
        return self.time

    def advance(self, seconds: float) -> None:
        self.time += seconds


def test_token_bucket_deterministic_rate_and_burst():
    """TokenBucket refills deterministically per second with zero sleep calls."""
    clock = MockClock(100.0)

    # Monkeypatch time.monotonic inside TokenBucket test
    orig_monotonic = time.monotonic
    time.monotonic = clock

    try:
        # Rate: 1 token/sec, Capacity (burst): 2 tokens
        bucket = TokenBucket(rate=1.0, capacity=2.0)

        # 1. Burst of 2 tokens allowed immediately
        assert bucket.allow(1.0) is True
        assert bucket.allow(1.0) is True

        # 2. 3rd token immediately requested -> rejected
        assert bucket.allow(1.0) is False

        # 3. Advance clock by 0.5s -> 0.5 tokens refilled, need 1.0 -> rejected
        clock.advance(0.5)
        assert bucket.allow(1.0) is False

        # 4. Advance clock by another 0.5s (total 1.0s elapsed) -> allowed
        clock.advance(0.5)
        assert bucket.allow(1.0) is True

        # 5. Advance clock by 10.0s -> capped at capacity 2.0
        clock.advance(10.0)
        assert bucket.allow(1.0) is True
        assert bucket.allow(1.0) is True
        assert bucket.allow(1.0) is False
    finally:
        time.monotonic = orig_monotonic

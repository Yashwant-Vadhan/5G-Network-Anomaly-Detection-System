"""Unit tests for streaming session-gap rule and warm-up semantics (T11-004)."""

import pandas as pd

from ml.feature_engineering import build_features
from ml.preprocessing import add_sessions
from streaming.session_manager import (
    SessionManager,
    apply_session_gap,
)


def test_session_gap_yields_two_sessions_matching_batch():
    """A >30 s gap fixture yields 2 sessions with the same IDs and sample_idx as batch."""
    records = [
        # Session 1: 3 samples spaced by 3s
        {
            "timestamp": "2026-10-09 10:15:00",
            "device": "Samsung Galaxy S21",
            "ss_rsrp": -95.0,
            "ss_rsrq": -11.0,
            "ss_sinr": 18.5,
            "pci": 42,
            "nci": 13322280247,
            "network_type": "5G",
        },
        {
            "timestamp": "2026-10-09 10:15:03",
            "device": "Samsung Galaxy S21",
            "ss_rsrp": -94.0,
            "ss_rsrq": -10.5,
            "ss_sinr": 19.0,
            "pci": 42,
            "nci": 13322280247,
            "network_type": "5G",
        },
        {
            "timestamp": "2026-10-09 10:15:06",
            "device": "Samsung Galaxy S21",
            "ss_rsrp": -96.0,
            "ss_rsrq": -11.2,
            "ss_sinr": 17.8,
            "pci": 42,
            "nci": 13322280247,
            "network_type": "5G",
        },
        # >30s gap: 54 seconds later (10:16:00)
        # Session 2: 2 samples spaced by 3s
        {
            "timestamp": "2026-10-09 10:16:00",
            "device": "Samsung Galaxy S21",
            "ss_rsrp": -98.0,
            "ss_rsrq": -12.0,
            "ss_sinr": 15.0,
            "pci": 43,
            "nci": 13322280248,
            "network_type": "5G",
        },
        {
            "timestamp": "2026-10-09 10:16:03",
            "device": "Samsung Galaxy S21",
            "ss_rsrp": -99.0,
            "ss_rsrq": -12.5,
            "ss_sinr": 14.5,
            "pci": 43,
            "nci": 13322280248,
            "network_type": "5G",
        },
    ]

    # 1. Batch computation
    batch_df = pd.DataFrame(records)
    batch_df["timestamp"] = pd.to_datetime(batch_df["timestamp"])
    batch_df = add_sessions(batch_df, gap_seconds=30)

    # 2. Streaming computation via SessionManager
    mgr = SessionManager(gap_seconds=30)
    session_buffers = []

    for idx, row in enumerate(records):
        buf, appended = mgr.append_sample(
            client_id="client-samsung",
            row=row,
            seq=idx + 1,
            device="Samsung Galaxy S21",
        )
        assert appended is True
        if buf not in session_buffers:
            session_buffers.append(buf)

    assert len(session_buffers) == 2
    buf1, buf2 = session_buffers

    df_stream1 = buf1.to_dataframe()
    df_stream2 = buf2.to_dataframe()

    # Session IDs match batch
    assert buf1.session_id == "samsung-galaxy-s21-1"
    assert buf2.session_id == "samsung-galaxy-s21-2"
    assert list(batch_df["session_id"].unique()) == [buf1.session_id, buf2.session_id]

    # Sample indexes match batch
    assert list(df_stream1["sample_idx"]) == [0, 1, 2]
    assert list(df_stream2["sample_idx"]) == [0, 1]
    assert list(batch_df["sample_idx"]) == [0, 1, 2, 0, 1]


def test_warmup_semantics_identical_at_session_start():
    """First sample of a new session after a gap has warm-up features matching batch."""
    records = [
        # Session 1 sample
        {
            "timestamp": "2026-10-09 10:15:00",
            "device": "Samsung",
            "ss_rsrp": -95.0,
            "ss_rsrq": -11.0,
            "ss_sinr": 18.5,
            "pci": 42,
            "nci": 1000,
            "network_type": "5G",
        },
        # Gap > 30s
        # Session 2 sample 1 (should have warm-up: pci_changed=0, nci_changed=0)
        {
            "timestamp": "2026-10-09 10:16:00",
            "device": "Samsung",
            "ss_rsrp": -98.0,
            "ss_rsrq": -12.0,
            "ss_sinr": 15.0,
            "pci": 43,  # Changed PCI from session 1, but session boundary resets change flags
            "nci": 1001,
            "network_type": "5G",
        },
    ]

    # Batch features
    batch_df = pd.DataFrame(records)
    batch_df["timestamp"] = pd.to_datetime(batch_df["timestamp"])
    batch_df = add_sessions(batch_df, gap_seconds=30)
    batch_feat = build_features(batch_df)

    # In batch, row 1 (session 2 start) has pci_changed = 0 and nci_changed = 0
    assert batch_feat["pci_changed"].iloc[1] == 0
    assert batch_feat["nci_changed"].iloc[1] == 0
    assert pd.isna(batch_feat["rolling_std_rsrp"].iloc[1])

    # In streaming buffer for session 2:
    mgr = SessionManager(gap_seconds=30)
    for idx, row in enumerate(records):
        buf, _ = mgr.append_sample("c1", row, seq=idx + 1, device="Samsung")

    # Buffer for session 2
    stream_feat = build_features(buf.to_dataframe())
    assert stream_feat["pci_changed"].iloc[0] == 0
    assert stream_feat["nci_changed"].iloc[0] == 0
    assert pd.isna(stream_feat["rolling_std_rsrp"].iloc[0])


def test_apply_session_gap_helper():
    """apply_session_gap produces identical results to ml.preprocessing.add_sessions."""
    df = pd.DataFrame(
        [
            {"timestamp": "2026-10-09 10:15:00", "device": "Pixel"},
            {"timestamp": "2026-10-09 10:16:00", "device": "Pixel"},
        ]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    res = apply_session_gap(df, gap_seconds=30)
    expected = add_sessions(df, gap_seconds=30)
    pd.testing.assert_frame_equal(res, expected)

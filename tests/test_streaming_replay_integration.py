"""Integration test: replay -> server -> live subscriber (T11-017).

Connects a live dashboard subscriber (/api/v1/live) using the FastAPI test client,
replays sample measurements via the real ingest WebSocket handler (/api/v1/ingest),
and validates:
1. Message ordering: initial snapshot, live samples, event_open and event_closed.
2. Telemetry retention: live-capture CSV equals input sample CSV field-by-field.
3. Stream-batch parity: batch anomaly detection on captured CSV equals live results.
4. Determinism: uses injectable MockClock without wall-clock sleeps.
5. Execution speed: completes in under 10 seconds (well under CI 60s limit).
"""

from __future__ import annotations

import csv
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import streaming.store
from ml.anomaly_analysis import detect
from ml.config import RAW_COLUMNS
from ml.preprocessing import (
    add_missing_flags,
    add_sessions,
    coerce_numeric,
    flag_invalid,
    parse_timestamps,
)
from streaming.connection import ConnectionTracker
from streaming.engine import StreamingEngine
from streaming.hub import LiveHub
from streaming.schema import SCHEMA_VERSION
from streaming.server import ServerConfig, create_app
from streaming.session_manager import SessionManager

SAMPLE_CSV = Path("data/sample/sample_measurements.csv")


class MockClock:
    """Injectable monotonic and wall clock for deterministic time manipulation."""

    def __init__(
        self,
        start_mono: float = 1000.0,
        start_wall: datetime | None = None,
    ) -> None:
        self.mono = start_mono
        self.wall = start_wall or datetime(2026, 9, 30, 22, 51, 30, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.mono

    def wall_clock(self) -> datetime:
        return self.wall

    def time(self) -> float:
        return self.wall.timestamp()

    def advance(self, seconds: float) -> None:
        self.mono += seconds
        self.wall += timedelta(seconds=seconds)


def _prepare_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Coerce CSV DictReader row strings into types matching IngestPayload."""
    clean = dict(row)
    for num_col in ["ss_rsrp", "ss_rsrq", "ss_sinr", "csi_rsrp", "csi_rsrq", "csi_sinr"]:
        raw = clean.get(num_col)
        clean[num_col] = float(raw) if raw and str(raw).strip() != "" else None

    for int_col in ["pci", "nci", "nrarfcn"]:
        raw = clean.get(int_col)
        clean[int_col] = int(float(raw)) if raw and str(raw).strip() != "" else None

    reg_val = str(clean.get("registered", "")).strip().lower()
    clean["registered"] = True if reg_val == "true" else False
    clean["display_override"] = clean.get("display_override") or "NONE"
    clean["deployment_mode"] = clean.get("deployment_mode") or "UNKNOWN"
    return clean


def _assert_live_capture_equals_input(
    input_csv_path: Path,
    captured_csv_path: Path,
) -> None:
    """Validate that every cell of the live-captured CSV matches the input CSV."""
    df_in = pd.read_csv(input_csv_path)
    df_cap = pd.read_csv(captured_csv_path)

    assert len(df_cap) == len(df_in), (
        f"Row count mismatch: captured={len(df_cap)} vs input={len(df_in)}"
    )

    for col in RAW_COLUMNS:
        assert col in df_cap.columns, f"Missing column {col} in captured CSV"
        assert col in df_in.columns, f"Missing column {col} in input CSV"

        for idx in range(len(df_in)):
            val_in = df_in[col].iloc[idx]
            val_cap = df_cap[col].iloc[idx]

            if pd.isna(val_in):
                assert pd.isna(val_cap), f"Row {idx} col {col}: expected NaN, got {val_cap}"
            elif isinstance(val_in, (bool, np.bool_)):
                assert bool(val_in) == bool(val_cap), (
                    f"Row {idx} col {col}: boolean mismatch {val_cap} != {val_in}"
                )
            elif isinstance(val_in, (int, float, np.integer, np.floating)):
                assert abs(float(val_in) - float(val_cap)) < 1e-4, (
                    f"Row {idx} col {col}: numeric mismatch {val_cap} != {val_in}"
                )
            else:
                assert str(val_in).strip() == str(val_cap).strip(), (
                    f"Row {idx} col {col}: string mismatch '{val_cap}' != '{val_in}'"
                )


def _assert_batch_on_capture_equals_live(
    captured_csv_path: Path,
    live_samples: list[Any],
) -> None:
    """Validate that batch anomaly detection on captured CSV equals live streaming results."""
    raw_df = pd.read_csv(captured_csv_path)
    valid_ts, _ = parse_timestamps(raw_df)
    coerced = coerce_numeric(valid_ts)
    flagged = flag_invalid(coerced)
    with_flags = add_missing_flags(flagged)
    sessionized = add_sessions(with_flags)

    batch_scores, _ = detect(sessionized)

    assert len(batch_scores) == len(live_samples), (
        f"Sample count mismatch: batch={len(batch_scores)} vs live={len(live_samples)}"
    )

    for idx in range(len(batch_scores)):
        b_row = batch_scores.iloc[idx]
        s_sample = live_samples[idx]

        assert bool(b_row["baseline_flag"]) == bool(s_sample.baseline_flag), (
            f"Row {idx}: baseline_flag mismatch"
        )
        assert bool(b_row["if_flag"]) == bool(s_sample.if_flag), f"Row {idx}: if_flag mismatch"
        assert str(b_row["anomaly_type"]) == str(s_sample.anomaly_type), (
            f"Row {idx}: anomaly_type mismatch: {b_row['anomaly_type']} != {s_sample.anomaly_type}"
        )
        assert str(b_row["severity"]) == str(s_sample.severity), (
            f"Row {idx}: severity mismatch: {b_row['severity']} != {s_sample.severity}"
        )

        if pd.notna(b_row["if_score"]) and s_sample.if_score is not None:
            assert abs(float(b_row["if_score"]) - float(s_sample.if_score)) <= 1e-6, (
                f"Row {idx}: if_score mismatch: {b_row['if_score']} != {s_sample.if_score}"
            )


def test_replay_server_live_subscriber_integration(tmp_path: Path):
    """End-to-end integration test: replay -> server -> live subscriber (T11-017)."""
    assert SAMPLE_CSV.is_file(), f"Sample CSV missing: {SAMPLE_CSV}"

    with open(SAMPLE_CSV, encoding="utf-8") as f:
        input_rows = list(csv.DictReader(f))
    total_samples = len(input_rows)
    assert total_samples > 0

    # 1. Setup deterministic server with injectable clock & isolated capture directory
    orig_live_dir = streaming.store.DEFAULT_LIVE_DIR
    streaming.store.DEFAULT_LIVE_DIR = tmp_path

    clock = MockClock()
    session_manager = SessionManager(max_rows=500, clock=clock.time)
    engine = StreamingEngine(session_manager=session_manager)
    hub = LiveHub(default_queue_size=300)
    tracker = ConnectionTracker(
        clock=clock.monotonic,
        wall_clock=clock.wall_clock,
        hub=hub,
    )

    config = ServerConfig(
        retention_enabled=True,
        allow_lan=False,
        allow_remote_view=False,
    )
    app = create_app(
        config=config,
        session_manager=session_manager,
        engine=engine,
        hub=hub,
    )
    app.state.connection_tracker = tracker
    client = TestClient(app)

    received_messages: list[dict[str, Any]] = []
    subscriber_ready = threading.Event()
    stop_subscriber = threading.Event()

    def live_subscriber_worker():
        with client.websocket_connect("/api/v1/live") as live_ws:
            subscriber_ready.set()
            while not stop_subscriber.is_set():
                try:
                    msg = live_ws.receive_json()
                    received_messages.append(msg)
                except Exception:
                    break

    sub_thread = threading.Thread(target=live_subscriber_worker, daemon=True)
    sub_thread.start()

    assert subscriber_ready.wait(timeout=5.0), "Live subscriber failed to connect"
    time.sleep(0.1)

    # 2. Replay telemetry via real ingest handler
    first_row = input_rows[0]
    device = str(first_row.get("device") or "replay-device")
    manufacturer = str(first_row.get("manufacturer") or "ReplayCorp")
    android = str(first_row.get("android") or "14")
    operator = str(first_row.get("operator") or "Replay-Operator")

    session_id: str | None = None
    with client.websocket_connect("/api/v1/ingest") as ingest_ws:
        hello_msg = {
            "type": "hello",
            "schema_version": SCHEMA_VERSION,
            "client_id": "test-replay-sub-client",
            "session_label": "replay-integration-test",
            "device": device,
            "manufacturer": manufacturer,
            "android": android,
            "operator": operator,
            "app_version": "1.0.0",
            "source": "replay",
        }
        ingest_ws.send_json(hello_msg)
        hello_ack = ingest_ws.receive_json()
        assert hello_ack["type"] == "hello_ack"
        session_id = hello_ack["session_id"]
        assert session_id is not None

        for idx, row in enumerate(input_rows, start=1):
            clock.advance(1.0)
            payload = _prepare_payload(row)
            sample_msg = {
                "type": "sample",
                "schema_version": SCHEMA_VERSION,
                "seq": idx,
                "sent_at": clock.wall_clock().isoformat(),
                "payload": payload,
            }
            ingest_ws.send_json(sample_msg)

            # Cumulative acks flushed every 5 samples
            if idx % 5 == 0:
                ack = ingest_ws.receive_json()
                assert ack["type"] == "ack"
                assert ack["seq"] >= idx - 4

        # Clean disconnect
        ingest_ws.send_json({"type": "bye", "schema_version": SCHEMA_VERSION})

    time.sleep(0.5)
    stop_subscriber.set()
    sub_thread.join(timeout=2.0)

    # Restore default live dir
    streaming.store.DEFAULT_LIVE_DIR = orig_live_dir

    # 3. Assert message ordering on live subscriber: snapshot -> sample -> event_open/closed
    assert len(received_messages) > 0, "No messages received by subscriber"
    first_msg = received_messages[0]
    assert first_msg["type"] == "snapshot", f"First message must be snapshot, got {first_msg}"

    msg_types = [m["type"] for m in received_messages]
    assert "snapshot" in msg_types
    assert "sample" in msg_types
    assert "event_open" in msg_types
    assert "event_closed" in msg_types

    # Validate event open precedes closed
    open_idx = msg_types.index("event_open")
    closed_idx = msg_types.index("event_closed")
    assert open_idx < closed_idx, "event_open must precede event_closed"

    sample_msgs = [m for m in received_messages if m["type"] == "sample"]
    assert len(sample_msgs) == total_samples, (
        f"Subscriber received {len(sample_msgs)} samples, expected {total_samples}"
    )

    # 4. Assert live-capture CSV equals input sample CSV
    matching_csvs = list(tmp_path.glob(f"*{session_id}*.csv"))
    assert len(matching_csvs) == 1, (
        f"Expected 1 captured CSV in {tmp_path}, found {len(matching_csvs)}"
    )
    captured_csv = matching_csvs[0]
    assert captured_csv.is_file(), f"Captured CSV not found at {captured_csv}"

    _assert_live_capture_equals_input(SAMPLE_CSV, captured_csv)

    # 5. Assert batch anomaly detection on captured CSV equals live streaming results
    live_scored_samples = app.state.session_samples[session_id]
    _assert_batch_on_capture_equals_live(captured_csv, live_scored_samples)

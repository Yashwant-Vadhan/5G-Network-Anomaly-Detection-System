#!/usr/bin/env python3
"""Replay tool for streaming telemetry ingest (T11-015 / Contract C1, C7).

Reads a Contract C1 telemetry CSV and sends each row as a C7 sample message
through the WebSocket ingest endpoint (`/api/v1/ingest`). Respects server
acknowledgments (sliding-window backpressure), sets session source='replay',
and supports variable replay speeds.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import websockets

logger = logging.getLogger("replay_stream")


def row_to_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a CSV row dictionary to a Contract C1 / C7 IngestPayload dict."""

    def _float_or_none(v: Any) -> float | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.upper() in ("NA", "NAN", "NONE", "NULL"):
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def _int_or_none(v: Any) -> int | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.upper() in ("NA", "NAN", "NONE", "NULL"):
            return None
        try:
            return int(float(s))
        except ValueError:
            return None

    def _bool_or_none(v: Any) -> bool | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.upper() in ("NA", "NAN", "NONE", "NULL"):
            return None
        if s.lower() in ("true", "1", "t", "yes"):
            return True
        if s.lower() in ("false", "0", "f", "no"):
            return False
        return None

    def _str_or_default(v: Any, default: str) -> str:
        if v is None:
            return default
        s = str(v).strip()
        return s if s and s.upper() not in ("NA", "NAN", "NONE", "NULL") else default

    def _str_or_none(v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s and s.upper() not in ("NA", "NAN", "NONE", "NULL") else None

    return {
        "timestamp": str(row.get("timestamp", "")),
        "device": _str_or_default(row.get("device"), "device"),
        "manufacturer": _str_or_default(row.get("manufacturer"), "Generic"),
        "android": _str_or_default(row.get("android"), "14"),
        "operator": _str_or_default(row.get("operator"), "Operator"),
        "network_type": _str_or_default(row.get("network_type"), "5G NR"),
        "deployment_mode": _str_or_default(row.get("deployment_mode"), "UNKNOWN"),
        "display_override": _str_or_none(row.get("display_override")),
        "registered": _bool_or_none(row.get("registered")),
        "ss_rsrp": _float_or_none(row.get("ss_rsrp")),
        "ss_rsrq": _float_or_none(row.get("ss_rsrq")),
        "ss_sinr": _float_or_none(row.get("ss_sinr")),
        "csi_rsrp": _float_or_none(row.get("csi_rsrp")),
        "csi_rsrq": _float_or_none(row.get("csi_rsrq")),
        "csi_sinr": _float_or_none(row.get("csi_sinr")),
        "pci": _int_or_none(row.get("pci")),
        "nci": _int_or_none(row.get("nci")),
        "nrarfcn": _int_or_none(row.get("nrarfcn")),
    }


def parse_timestamp(ts_str: str) -> datetime | None:
    """Parse a Contract C1 timestamp (%d-%m-%y %H:%M:%S or ISO format)."""
    ts_str = ts_str.strip()
    if not ts_str:
        return None
    for fmt in ("%d-%m-%y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


class ReplayStreamer:
    """Manages WebSocket connection, flow control, and telemetry playback."""

    def __init__(
        self,
        csv_path: Path,
        host: str = "127.0.0.1",
        port: int = 8000,
        token: str | None = None,
        speed: float = 1.0,
        client_id: str | None = None,
        session_label: str = "replay-stream",
        max_in_flight: int = 20,
        limit: int | None = None,
        source: str = "replay",
    ) -> None:
        self.csv_path = csv_path
        self.host = host
        self.port = port
        self.token = token
        self.speed = speed
        self.client_id = client_id or f"replay-{uuid.uuid4().hex[:8]}"
        self.session_label = session_label
        self.max_in_flight = max_in_flight
        self.limit = limit
        self.source = source

        self.last_acked_seq: int = 0
        self.session_id: str | None = None
        self.ack_event: asyncio.Event = asyncio.Event()
        self.done_event: asyncio.Event = asyncio.Event()
        self.error: Exception | None = None
        self.samples_sent: int = 0
        self.samples_acked: int = 0

    async def _receiver_loop(self, ws: Any) -> None:
        """Background task receiving acks, pongs, and error messages from the server."""
        try:
            while not self.done_event.is_set():
                try:
                    msg_text = await ws.recv()
                except websockets.exceptions.ConnectionClosed:
                    break
                except Exception as e:
                    self.error = e
                    break

                try:
                    msg = json.loads(msg_text)
                except Exception:
                    continue

                msg_type = msg.get("type")
                if msg_type == "ack":
                    seq = msg.get("seq", 0)
                    if seq > self.last_acked_seq:
                        self.last_acked_seq = seq
                        self.samples_acked = seq
                        self.ack_event.set()
                elif msg_type == "error":
                    err_code = msg.get("code")
                    err_msg = msg.get("message")
                    logger.warning("Server error msg: %s: %s", err_code, err_msg)
                    if msg.get("fatal", False):
                        self.error = RuntimeError(f"Server fatal error: {err_code} - {err_msg}")
                        self.ack_event.set()
                        break
        finally:
            self.ack_event.set()

    async def run(self) -> dict[str, Any]:
        """Execute the replay session and return a summary dictionary."""
        # Read and prepare CSV rows
        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if self.limit is not None and self.limit > 0:
            rows = rows[: self.limit]

        if not rows:
            logger.warning("No rows found in CSV: %s", self.csv_path)
            return {
                "session_id": None,
                "samples_sent": 0,
                "samples_acked": 0,
                "duration_s": 0.0,
            }

        first_row = rows[0]
        device = str(first_row.get("device") or "replay-device")
        manufacturer = str(first_row.get("manufacturer") or "ReplayCorp")
        android = str(first_row.get("android") or "14")
        operator = str(first_row.get("operator") or "Replay-Operator")

        # Build WebSocket URL
        query = f"?token={self.token}" if self.token else ""
        uri = f"ws://{self.host}:{self.port}/api/v1/ingest{query}"

        additional_headers = {}
        if self.token:
            additional_headers["Authorization"] = f"Bearer {self.token}"

        start_time = time.monotonic()

        async with websockets.connect(
            uri,
            additional_headers=additional_headers or None,
            ping_interval=None,
        ) as ws:
            # 1. Hello handshake with source=replay
            hello_msg = {
                "type": "hello",
                "schema_version": 2,
                "client_id": self.client_id,
                "session_label": self.session_label,
                "device": device,
                "manufacturer": manufacturer,
                "android": android,
                "operator": operator,
                "app_version": "1.0.0",
                "source": self.source,
            }
            await ws.send(json.dumps(hello_msg))

            raw_hello_ack = await ws.recv()
            hello_ack = json.loads(raw_hello_ack)
            if hello_ack.get("type") != "hello_ack":
                raise RuntimeError(f"Unexpected response to hello: {raw_hello_ack}")

            self.session_id = hello_ack.get("session_id")
            self.last_acked_seq = hello_ack.get("last_seq_acked", 0)
            logger.info("Connected to ingest server, session_id=%s", self.session_id)

            # Start receiver loop
            receiver_task = asyncio.create_task(self._receiver_loop(ws))

            try:
                prev_dt: datetime | None = None
                for idx, row in enumerate(rows, start=1):
                    if self.error:
                        raise self.error

                    # Flow control: respect acks to prevent unbounded flooding
                    while (idx - 1 - self.last_acked_seq) >= self.max_in_flight:
                        self.ack_event.clear()
                        await asyncio.wait(
                            [
                                asyncio.create_task(self.ack_event.wait()),
                                asyncio.create_task(asyncio.sleep(0.5)),
                            ],
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if self.error:
                            raise self.error
                        # If still waiting, send ping to trigger an ack flush
                        if (idx - 1 - self.last_acked_seq) >= self.max_in_flight:
                            ping_msg = {"type": "ping", "schema_version": 2}
                            await ws.send(json.dumps(ping_msg))

                    # Timing: simulate real sample delays scaled by speed
                    curr_dt = parse_timestamp(row.get("timestamp", ""))
                    if idx > 1 and prev_dt is not None and curr_dt is not None:
                        delta_s = (curr_dt - prev_dt).total_seconds()
                        if delta_s > 0 and self.speed > 0:
                            sleep_dur = delta_s / self.speed
                            # Cap max single-sample sleep to 10s to avoid hanging on large gaps
                            sleep_dur = min(sleep_dur, 10.0)
                            if sleep_dur > 0.001:
                                await asyncio.sleep(sleep_dur)
                    prev_dt = curr_dt

                    # Send sample
                    payload = row_to_payload(row)
                    sample_msg = {
                        "type": "sample",
                        "schema_version": 2,
                        "seq": idx,
                        "sent_at": datetime.now(UTC).isoformat(),
                        "payload": payload,
                    }
                    await ws.send(json.dumps(sample_msg))
                    self.samples_sent = idx

                # All samples sent: flush remaining acks with ping if needed
                total_samples = len(rows)
                retries = 0
                while self.last_acked_seq < total_samples and retries < 20:
                    if self.error:
                        raise self.error
                    ping_msg = {"type": "ping", "schema_version": 2}
                    await ws.send(json.dumps(ping_msg))
                    self.ack_event.clear()
                    try:
                        await asyncio.wait_for(self.ack_event.wait(), timeout=1.0)
                    except TimeoutError:
                        pass
                    retries += 1

                # Send bye
                bye_msg = {"type": "bye", "schema_version": 2}
                await ws.send(json.dumps(bye_msg))

            finally:
                self.done_event.set()
                receiver_task.cancel()
                try:
                    await receiver_task
                except asyncio.CancelledError:
                    pass

        duration_s = time.monotonic() - start_time
        return {
            "session_id": self.session_id,
            "samples_sent": self.samples_sent,
            "samples_acked": self.last_acked_seq,
            "duration_s": duration_s,
        }


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI options with strict validation and exit code 2 on bad arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Replay a Contract C1 CSV stream through the 5G-NADS WebSocket ingest endpoint."
        ),
        prog="replay_stream.py",
    )
    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="Path to Contract C1 CSV file or directory containing sample measurements",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier (e.g. 1.0 for real-time, 20.0 for 20x). Must be > 0.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host of the 5G-NADS streaming server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port of the 5G-NADS streaming server (default: 8000)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Bearer auth token for the ingest WebSocket if required",
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=None,
        help="Optional custom client identifier",
    )
    parser.add_argument(
        "--session-label",
        type=str,
        default="replay-session",
        help="Session label for hello handshake",
    )
    parser.add_argument(
        "--max-in-flight",
        type=int,
        default=20,
        help="Maximum unacknowledged samples in flight (flow control)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of samples to send",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="replay",
        help="Telemetry source label ('phone' or 'replay')",
    )

    ns = parser.parse_args(args)

    if ns.speed <= 0:
        parser.error(f"--speed must be positive, got {ns.speed}")
    if ns.port < 1 or ns.port > 65535:
        parser.error(f"--port must be between 1 and 65535, got {ns.port}")
    if ns.max_in_flight < 1:
        parser.error(f"--max-in-flight must be >= 1, got {ns.max_in_flight}")

    csv_path = Path(ns.csv)
    if not csv_path.exists():
        parser.error(f"CSV path does not exist: {ns.csv}")
    if csv_path.is_dir():
        candidates = sorted(csv_path.glob("*.csv"))
        if not candidates:
            parser.error(f"No CSV files found in directory: {ns.csv}")
        # Prefer file with 'sample' in name
        preferred = next((c for c in candidates if "sample" in c.name.lower()), candidates[0])
        ns.resolved_csv = preferred
    else:
        if not csv_path.is_file():
            parser.error(f"CSV path is not a file: {ns.csv}")
        ns.resolved_csv = csv_path

    return ns


def main(args: list[str] | None = None) -> int:
    """CLI entry point for replay_stream."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ns = parse_args(args)

    streamer = ReplayStreamer(
        csv_path=ns.resolved_csv,
        host=ns.host,
        port=ns.port,
        token=ns.token,
        speed=ns.speed,
        client_id=ns.client_id,
        session_label=ns.session_label,
        max_in_flight=ns.max_in_flight,
        limit=ns.limit,
        source=ns.source,
    )

    try:
        summary = asyncio.run(streamer.run())
        print(
            f"Replay complete: {summary['samples_sent']} sent, "
            f"{summary['samples_acked']} acked, session={summary['session_id']} "
            f"in {summary['duration_s']:.2f}s"
        )
        return 0
    except Exception as e:
        logger.error("Replay failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())

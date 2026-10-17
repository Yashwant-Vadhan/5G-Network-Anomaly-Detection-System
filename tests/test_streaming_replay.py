"""Tests for scripts/replay_stream.py (T11-015).

Verifies:
- Bad arguments produce clear error messages and exit code 2.
- Telemetry replays through ingest WebSocket at 1x and 20x.
- Flow control respects acks without unbounded flooding.
- Session metadata and REST endpoints record source="replay".
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from scripts.replay_stream import ReplayStreamer, parse_args
from streaming.server import ServerConfig, create_app


def test_cli_bad_args_exit_code_2():
    """CLI exits with code 2 and helpful errors on invalid or missing arguments."""
    script_path = str(Path("scripts/replay_stream.py").resolve())

    # 1. Missing required --csv
    res1 = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    assert res1.returncode == 2
    assert "error" in res1.stderr.lower()

    # 2. Non-existent CSV file
    res2 = subprocess.run(
        [sys.executable, script_path, "--csv", "non_existent_file.csv"],
        capture_output=True,
        text=True,
    )
    assert res2.returncode == 2
    assert "does not exist" in res2.stderr

    # 3. Non-positive speed
    res3 = subprocess.run(
        [sys.executable, script_path, "--csv", "data/sample", "--speed", "0"],
        capture_output=True,
        text=True,
    )
    assert res3.returncode == 2
    assert "--speed must be positive" in res3.stderr

    res4 = subprocess.run(
        [sys.executable, script_path, "--csv", "data/sample", "--speed", "-5"],
        capture_output=True,
        text=True,
    )
    assert res4.returncode == 2
    assert "--speed must be positive" in res4.stderr

    # 4. Invalid port
    res5 = subprocess.run(
        [sys.executable, script_path, "--csv", "data/sample", "--port", "70000"],
        capture_output=True,
        text=True,
    )
    assert res5.returncode == 2
    assert "--port must be between" in res5.stderr

    # 5. Invalid max-in-flight
    res6 = subprocess.run(
        [sys.executable, script_path, "--csv", "data/sample", "--max-in-flight", "0"],
        capture_output=True,
        text=True,
    )
    assert res6.returncode == 2
    assert "--max-in-flight must be >= 1" in res6.stderr


def test_parse_args_resolves_directory_to_sample_csv():
    """Passing a directory to --csv finds the CSV within it."""
    ns = parse_args(["--csv", "data/sample", "--speed", "5"])
    assert ns.speed == 5.0
    assert ns.resolved_csv.is_file()
    assert "sample_measurements.csv" in ns.resolved_csv.name


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """Run an ephemeral live streaming server for replay integration testing."""
    live_dir = tmp_path_factory.mktemp("live_replay")
    config = ServerConfig(
        host="127.0.0.1",
        port=8092,
        retention_enabled=True,
    )
    app = create_app(config)

    # Patch DEFAULT_LIVE_DIR for test isolation
    import streaming.store

    orig_dir = streaming.store.DEFAULT_LIVE_DIR
    streaming.store.DEFAULT_LIVE_DIR = live_dir

    u_config = uvicorn.Config(app, host="127.0.0.1", port=8092, log_level="warning")
    server = uvicorn.Server(u_config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    for _ in range(50):
        if server.started:
            break
        time.sleep(0.05)

    yield "127.0.0.1", 8092, app, live_dir

    server.should_exit = True
    t.join(timeout=2.0)
    streaming.store.DEFAULT_LIVE_DIR = orig_dir


def test_replay_sample_at_1x_and_20x(live_server):
    """Replay tool successfully streams telemetry at 1x (short) and 20x (full)."""
    host, port, app, live_dir = live_server
    sample_csv = Path("data/sample/sample_measurements.csv")

    # 1. 1x replay for first 3 samples
    streamer_1x = ReplayStreamer(
        csv_path=sample_csv,
        host=host,
        port=port,
        speed=1.0,
        limit=3,
        client_id="test-replay-1x",
    )
    res_1x = asyncio.run(streamer_1x.run())
    assert res_1x["samples_sent"] == 3
    assert res_1x["samples_acked"] == 3

    # 2. 20x replay for full 70-sample dataset
    streamer_20x = ReplayStreamer(
        csv_path=sample_csv,
        host=host,
        port=port,
        speed=20.0,
        client_id="test-replay-20x",
    )
    res_20x = asyncio.run(streamer_20x.run())
    assert res_20x["samples_sent"] == 70
    assert res_20x["samples_acked"] == 70
    assert res_20x["duration_s"] < 25.0

    # 3. Check session metadata from REST API shows source=replay
    from fastapi.testclient import TestClient

    client = TestClient(app)
    r_sess = client.get("/api/v1/sessions")
    assert r_sess.status_code == 200
    sessions = r_sess.json()["sessions"]
    replay_sessions = [s for s in sessions if s["source"] == "replay"]
    assert len(replay_sessions) >= 2


def test_respects_acks_flow_control(live_server):
    """Replay streamer halts pipeline when in-flight messages exceed max_in_flight."""
    host, port, _app, _live_dir = live_server
    sample_csv = Path("data/sample/sample_measurements.csv")

    # Set tiny in-flight limit to force flow-control pauses
    streamer = ReplayStreamer(
        csv_path=sample_csv,
        host=host,
        port=port,
        speed=50.0,
        max_in_flight=4,
        limit=20,
        client_id="test-flow-control",
    )
    res = asyncio.run(streamer.run())
    assert res["samples_sent"] == 20
    assert res["samples_acked"] == 20


def test_replay_cli_subprocess(live_server):
    """Running scripts/replay_stream.py as a CLI process exits 0 and reports progress."""
    host, port, _app, _live_dir = live_server
    script_path = str(Path("scripts/replay_stream.py").resolve())

    res = subprocess.run(
        [
            sys.executable,
            script_path,
            "--csv",
            "data/sample",
            "--speed",
            "50",
            "--host",
            host,
            "--port",
            str(port),
            "--client-id",
            "cli-replay-proc",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Replay complete: 70 sent, 70 acked" in res.stdout

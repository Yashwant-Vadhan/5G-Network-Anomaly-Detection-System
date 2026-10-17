"""Tests for ephemeral session store and C1 CSV export endpoint (T18-005, Guardrail G29).

Acceptance Criteria:
- Disk scan after a session finds no live data in public mode
- Export equals samples received
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi.testclient import TestClient

from ml.config import RAW_COLUMNS
from streaming.server import ServerConfig, create_app


def _sample_payload(seq: int, rsrp: float = -85.0) -> dict:
    """Generate valid sample telemetry matching Contract C1."""
    return {
        "type": "sample",
        "seq": seq,
        "sent_at": "2026-10-17T12:00:00+00:00",
        "payload": {
            "timestamp": "17-10-26 12:00:00",
            "device": "pixel7",
            "manufacturer": "Google",
            "android": "14",
            "operator": "Jio",
            "network_type": "NR",
            "deployment_mode": "SA",
            "display_override": "NONE",
            "registered": True,
            "ss_rsrp": rsrp,
            "ss_rsrq": -11.0,
            "ss_sinr": 15.5,
            "csi_rsrp": -86.0,
            "csi_rsrq": -12.0,
            "csi_sinr": 14.0,
            "pci": 42,
            "nci": 1234567,
            "nrarfcn": 632000,
        },
    }


def test_export_equals_samples_received() -> None:
    """GET /api/v1/live-sessions/{id}/export.csv exports received samples in C1 format."""
    cfg = ServerConfig(ingest_token="secret-token", allow_remote_view=True)
    app = create_app(cfg)
    client = TestClient(app)

    # 1. Create session (cookie set automatically on TestClient)
    create_res = client.post("/api/v1/live-sessions")
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]
    code = create_res.json()["pairing_code"]

    # 2. Pair device
    pair_res = client.post("/api/v1/pair", json={"pairing_code": code, "client_id": "phone1"})
    assert pair_res.status_code == 200
    token = pair_res.json()["ingest_token"]

    # 3. Ingest 3 samples over WebSocket
    with client.websocket_connect(
        "/api/v1/ingest",
        headers={"Authorization": f"Bearer {token}"},
    ) as ws:
        hello_msg = {
            "type": "hello",
            "client_id": "phone1",
            "session_label": "test-label",
            "device": "pixel7",
            "manufacturer": "Google",
            "android": "14",
            "operator": "Jio",
            "app_version": "2.0.0",
        }
        ws.send_json(hello_msg)
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"

        # Send 3 distinct samples (no per-sample ack expected under cadence 5)
        ws.send_json(_sample_payload(1, rsrp=-85.0))
        ws.send_json(_sample_payload(2, rsrp=-90.0))
        ws.send_json(_sample_payload(3, rsrp=-95.0))

        # Send ping to flush cumulative ack
        ws.send_json({"type": "ping"})
        flush_ack = ws.receive_json()
        assert flush_ack["type"] == "ack"
        assert flush_ack["seq"] == 3
        pong = ws.receive_json()
        assert pong["type"] == "pong"

    # 4. Export CSV using viewer cookie
    export_res = client.get(f"/api/v1/live-sessions/{session_id}/export.csv")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"].startswith("text/csv")
    assert f'filename="live_{session_id}.csv"' in export_res.headers["content-disposition"]

    # 5. Parse CSV and verify exact match with C1 schema and sent samples
    reader = csv.reader(io.StringIO(export_res.text))
    rows = list(reader)
    assert len(rows) == 4  # 1 header + 3 data rows
    assert rows[0] == RAW_COLUMNS

    # Verify rsrp values in column index
    rsrp_idx = RAW_COLUMNS.index("ss_rsrp")
    assert float(rows[1][rsrp_idx]) == -85.0
    assert float(rows[2][rsrp_idx]) == -90.0
    assert float(rows[3][rsrp_idx]) == -95.0

    # Device & operator check
    dev_idx = RAW_COLUMNS.index("device")
    op_idx = RAW_COLUMNS.index("operator")
    assert rows[1][dev_idx] == "pixel7"
    assert rows[1][op_idx] == "Jio"


def test_disk_scan_finds_no_live_data_in_public_mode(tmp_path: Path) -> None:
    """In public mode (G29), no telemetry is persisted to disk during or after session."""
    cfg = ServerConfig(
        mode="public",
        allowed_origins=["https://dashboard.example.com"],
        retention_enabled=False,
    )
    app = create_app(cfg)
    client = TestClient(app)

    # Record disk state under data/ before session
    data_live = Path("data/live")
    pre_files = set(data_live.glob("**/*")) if data_live.exists() else set()

    # 1. Create session
    create_res = client.post("/api/v1/live-sessions")
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]
    code = create_res.json()["pairing_code"]

    # 2. Pair
    pair_res = client.post("/api/v1/pair", json={"pairing_code": code, "client_id": "phone-pub"})
    assert pair_res.status_code == 200
    token = pair_res.json()["ingest_token"]

    # 3. Stream data
    with client.websocket_connect(
        "/api/v1/ingest",
        headers={"Authorization": f"Bearer {token}"},
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "phone-pub",
                "session_label": "public-test",
                "device": "pixel7",
                "manufacturer": "Google",
                "android": "14",
                "operator": "Jio",
                "app_version": "2.0.0",
            }
        )
        ws.receive_json()

        for seq in range(1, 5):
            ws.send_json(_sample_payload(seq))

        # Ping to flush
        ws.send_json({"type": "ping"})
        ws.receive_json()
        ws.receive_json()

    # 4. Teardown session
    del_res = client.delete(
        f"/api/v1/live-sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200

    # 5. Assert NO files were created on disk (G29 requirement)
    post_files = set(data_live.glob("**/*")) if data_live.exists() else set()
    new_files = post_files - pre_files
    assert len(new_files) == 0, f"Leaked live telemetry to disk in public mode: {new_files}"


def test_export_unauthorized_without_viewer_auth() -> None:
    """GET /api/v1/live-sessions/{id}/export.csv rejects requests without auth."""
    cfg = ServerConfig(ingest_token="srv-token", allow_remote_view=True)
    app = create_app(cfg)
    anon_client = TestClient(app)

    create_res = anon_client.post("/api/v1/live-sessions")
    session_id = create_res.json()["session_id"]

    # Clear cookies on client
    anon_client.cookies.clear()

    # Request export without cookie or token -> 401
    res = anon_client.get(f"/api/v1/live-sessions/{session_id}/export.csv")
    assert res.status_code == 401
    assert "Unauthorized" in res.json()["error"]["message"]


def test_memory_purged_after_delete_session() -> None:
    """After DELETE /api/v1/live-sessions/{id}, telemetry buffers are empty (G29)."""
    cfg = ServerConfig()
    app = create_app(cfg)
    client = TestClient(app)

    create_res = client.post("/api/v1/live-sessions")
    session_id = create_res.json()["session_id"]
    code = create_res.json()["pairing_code"]

    pair_res = client.post("/api/v1/pair", json={"pairing_code": code, "client_id": "phone1"})
    token = pair_res.json()["ingest_token"]

    with client.websocket_connect(
        "/api/v1/ingest",
        headers={"Authorization": f"Bearer {token}"},
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "phone1",
                "session_label": "purge-test",
                "device": "pixel7",
                "manufacturer": "Google",
                "android": "14",
                "operator": "Jio",
                "app_version": "2.0.0",
            }
        )
        ws.receive_json()
        ws.send_json(_sample_payload(1))
        ws.send_json({"type": "ping"})
        ws.receive_json()
        ws.receive_json()

    # Buffers exist before delete
    assert session_id in app.state.session_raw_samples
    assert len(app.state.session_raw_samples[session_id]) == 1

    # Teardown session
    del_res = client.delete(f"/api/v1/live-sessions/{session_id}")
    assert del_res.status_code == 200

    # In-memory telemetry must be completely deleted
    assert session_id not in app.state.session_raw_samples
    assert session_id not in app.state.session_samples
    assert session_id not in app.state.active_live_sessions

    # Subsequent export returns 401/404
    export_res = client.get(
        f"/api/v1/live-sessions/{session_id}/export.csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert export_res.status_code in (401, 404)

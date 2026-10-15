#!/usr/bin/env python3
"""Export JSON Schema and golden examples for Contract C7, C8, and C9 models (T10-008).

Emits schemas and golden test fixtures to tests/fixtures/stream/ for:
1. Python unit tests and contract drift verification (--check).
2. Android Kotlin client deserialization tests (Contract C7 ingest).
3. React TypeScript frontend type generation (Contract C8 live-stream / REST).

Usage:
    python scripts/export_contract_examples.py           # Generate / update fixtures
    python scripts/export_contract_examples.py --check   # Verify committed fixtures match schemas
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path for direct CLI execution
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic import BaseModel  # noqa: E402

from streaming.schema import (  # noqa: E402
    Ack,
    AlertDecision,
    AlertDelivery,
    AlertPush,
    AlertRecord,
    BrowserAuthFrame,
    ConnectionEvent,
    DroppedEvent,
    ErrorDetail,
    ErrorMsg,
    ErrorResponse,
    EventRecord,
    HealthResponse,
    HeartbeatEvent,
    HelloAck,
    IngestBye,
    IngestHello,
    IngestPing,
    IngestSample,
    LiveEventClosed,
    LiveEventOpen,
    LiveEventUpdate,
    LiveSampleEvent,
    MetricsResponse,
    ModelInfoResponse,
    Pong,
    SamplesResponse,
    ScoredSample,
    SessionListResponse,
    SessionSummary,
    SnapshotEvent,
)

FIXTURES_DIR = Path("tests/fixtures/stream")


def get_golden_definitions() -> list[dict[str, Any]]:
    """Define models, target names, and representative valid instances."""
    sample_raw = {
        "timestamp": "01-10-26 18:26:32",
        "device": "SM-A156E",
        "manufacturer": "samsung",
        "android": "16",
        "operator": "airtel",
        "network_type": "LTE",
        "deployment_mode": "NSA",
        "display_override": "NR_NSA",
        "registered": False,
        "ss_rsrp": -97.0,
        "ss_rsrq": -12.0,
        "ss_sinr": 3.0,
        "csi_rsrp": None,
        "csi_rsrq": None,
        "csi_sinr": None,
        "pci": 861,
        "nci": 0,
        "nrarfcn": 629952,
    }

    scored_sample = ScoredSample(
        **sample_raw,
        session_id="sm-a156e-1",
        sample_idx=42,
        is_valid=True,
        model_eligible=True,
        csi_available=False,
        is_synthetic=False,
        source_file="5G_measurements_Samsung_Indoor-Movement.csv",
        dup_ts=False,
        delta_rsrp=-2.0,
        delta_rsrq=0.0,
        delta_sinr=1.0,
        pci_changed=False,
        nci_changed=False,
        network_changed=False,
        rolling_mean_rsrp=-96.5,
        rolling_std_rsrp=0.5,
        rolling_mean_rsrq=-12.0,
        rolling_std_rsrq=0.0,
        rolling_mean_sinr=2.8,
        rolling_std_sinr=0.4,
        weak_rsrp_run=0,
        poor_rsrq_run=0,
        poor_sinr_run=0,
        baseline_z_rsrp=0.2,
        baseline_z_rsrq=0.1,
        baseline_z_sinr=-0.4,
        baseline_z_max=0.4,
        baseline_flag=False,
        if_score=0.35,
        if_flag=False,
        anomaly_type="NORMAL",
        severity="NONE",
        event_id=None,
        is_anom=False,
        seq=42,
        received_at="2026-10-01T18:26:32.500+05:30",
        scored_at="2026-10-01T18:26:32.505+05:30",
        published_at="2026-10-01T18:26:32.508+05:30",
        edge_if_score=0.34,
        edge_divergence=0.01,
    )

    event_record = EventRecord(
        event_id="redmi-1-e003",
        session_id="redmi-1",
        start="2026-10-09T10:15:00+05:30",
        end="2026-10-09T10:15:30+05:30",
        anomaly_type="PERSISTENT_POOR_QUALITY",
        severity="MEDIUM",
        ml={"anomaly_type": "PERSISTENT_POOR_QUALITY", "max_severity": "MEDIUM", "sample_count": 8},
        signal={"signal_condition": "degraded", "evidence": ["SINR below poor threshold"]},
        cell={"cell_event": "NONE", "evidence": ["PCI stayed constant"]},
        network={"network_state": "stable", "deployment_mode": "NSA"},
        diagnosis={
            "summary": "Persistent poor radio quality (possible)",
            "evidence": ["SINR degraded for 24s without cell change"],
            "confidence_note": (
                "Diagnostic correlation derived deterministically from empirical measurements."
            ),
            "anomaly_type": "PERSISTENT_POOR_QUALITY",
        },
        recommendation={"text": "Monitor area coverage", "kind": "MONITORING"},
        status="PROVISIONAL",
        alert_decision=AlertDecision(alerted=True, reason="Alert triggered"),
    )

    alert_record = AlertRecord(
        alert_id="al-000017",
        created_at="2026-10-09T10:15:41+05:30",
        event_id="redmi-1-e003",
        session_id="redmi-1",
        source="phone",
        kind="NEW",
        severity="MEDIUM",
        anomaly_type="PERSISTENT_POOR_QUALITY",
        event_status="PROVISIONAL",
        title="MEDIUM · Persistent poor radio quality (possible)",
        body=(
            "SINR below the configured poor-quality level for 24 s; "
            "RSRQ also degraded; no cell change in the window."
        ),
        evidence=["SS-RSRP degraded to -105 dBm"],
        recommendation={"text": "Maintain standard telemetry", "kind": "MONITORING"},
        policy={
            "rule_evidence": True,
            "persistence_samples": 8,
            "min_persistence": 6,
            "min_severity": "MEDIUM",
        },
        delivery=[
            AlertDelivery(channel="in_app", status="OK"),
            AlertDelivery(channel="webhook", status="FAILED", detail="timeout"),
        ],
        acknowledged_at=None,
    )

    return [
        # Contract C7 Client
        {
            "name": "c7_ingest_hello",
            "model": IngestHello,
            "example": IngestHello(
                client_id="b1e2c3d4-test-uuid",
                session_label="walk-01",
                device="Redmi 13 5G",
                manufacturer="Xiaomi",
                android="14",
                operator="Airtel",
                app_version="1.3.0",
            ),
        },
        {
            "name": "c7_ingest_sample",
            "model": IngestSample,
            "example": IngestSample(
                seq=119, sent_at="2026-10-01T18:26:32.412+05:30", payload=sample_raw
            ),
        },
        {
            "name": "c7_ingest_ping",
            "model": IngestPing,
            "example": IngestPing(queue_depth=5, dropped_from_queue=0),
        },
        {"name": "c7_ingest_bye", "model": IngestBye, "example": IngestBye(reason="user_stopped")},
        # Contract C7 Server
        {
            "name": "c7_hello_ack",
            "model": HelloAck,
            "example": HelloAck(
                session_id="session-001",
                server_time="2026-10-09T10:15:04+05:30",
                last_seq_acked=100,
            ),
        },
        {"name": "c7_ack", "model": Ack, "example": Ack(seq=105)},
        {
            "name": "c7_error",
            "model": ErrorMsg,
            "example": ErrorMsg(
                code="BAD_MESSAGE", message="Payload invalid", fatal=False, seq=105
            ),
        },
        {
            "name": "c7_alert_push",
            "model": AlertPush,
            "example": AlertPush(alert={"title": "MEDIUM · Radio anomaly", "severity": "MEDIUM"}),
        },
        {
            "name": "c7_pong",
            "model": Pong,
            "example": Pong(server_time="2026-10-09T10:15:05+05:30"),
        },
        # Contract C8 Live Events
        {"name": "c8_scored_sample", "model": ScoredSample, "example": scored_sample},
        {
            "name": "c8_live_sample",
            "model": LiveSampleEvent,
            "example": LiveSampleEvent(
                server_time="2026-10-01T18:26:32.510+05:30",
                session_id="sm-a156e-1",
                sample=scored_sample,
            ),
        },
        {"name": "c8_event_record", "model": EventRecord, "example": event_record},
        {
            "name": "c8_event_open",
            "model": LiveEventOpen,
            "example": LiveEventOpen(
                server_time="2026-10-09T10:15:00+05:30", session_id="redmi-1", event=event_record
            ),
        },
        {
            "name": "c8_event_update",
            "model": LiveEventUpdate,
            "example": LiveEventUpdate(
                server_time="2026-10-09T10:15:10+05:30", session_id="redmi-1", event=event_record
            ),
        },
        {
            "name": "c8_event_closed",
            "model": LiveEventClosed,
            "example": LiveEventClosed(
                server_time="2026-10-09T10:15:30+05:30",
                session_id="redmi-1",
                event=event_record.model_copy(update={"status": "FINAL"}),
            ),
        },
        {
            "name": "c8_connection",
            "model": ConnectionEvent,
            "example": ConnectionEvent(
                server_time="2026-10-09T10:15:00+05:30",
                session_id="redmi-1",
                state="LIVE",
                last_sample_age_s=1.5,
                source="phone",
            ),
        },
        {
            "name": "c8_snapshot",
            "model": SnapshotEvent,
            "example": SnapshotEvent(
                server_time="2026-10-09T10:15:00+05:30",
                session_id="redmi-1",
                state="LIVE",
                latest_sample=scored_sample,
                open_events=[event_record],
                last_alerts=[],
            ),
        },
        {
            "name": "c8_dropped",
            "model": DroppedEvent,
            "example": DroppedEvent(
                server_time="2026-10-09T10:15:05+05:30", session_id="redmi-1", count=10
            ),
        },
        {
            "name": "c8_heartbeat",
            "model": HeartbeatEvent,
            "example": HeartbeatEvent(server_time="2026-10-09T10:15:10+05:30"),
        },
        {
            "name": "c8_auth",
            "model": BrowserAuthFrame,
            "example": BrowserAuthFrame(ticket="ticket-uuid-abc-123"),
        },
        # Contract C8 REST
        {
            "name": "c8_health_response",
            "model": HealthResponse,
            "example": HealthResponse(status="ok", version="2.0.0", uptime_s=142.5),
        },
        {
            "name": "c8_session_list_response",
            "model": SessionListResponse,
            "example": SessionListResponse(
                sessions=[
                    SessionSummary(
                        session_id="redmi-1", source="phone", status="OPEN", sample_count=100
                    )
                ],
                total=1,
            ),
        },
        {
            "name": "c8_samples_response",
            "model": SamplesResponse,
            "example": SamplesResponse(samples=[scored_sample], total=1, has_more=False),
        },
        {
            "name": "c8_model_info_response",
            "model": ModelInfoResponse,
            "example": ModelInfoResponse(
                model_version="if_v1",
                feature_columns=["ss_rsrp", "ss_rsrq", "ss_sinr"],
                feature_hash="hash-12345",
                thresholds={"if_threshold": 0.6},
            ),
        },
        {
            "name": "c8_metrics_response",
            "model": MetricsResponse,
            "example": MetricsResponse(
                p50_latency_ms=2.1,
                p95_latency_ms=4.8,
                max_latency_ms=12.0,
                duplicates_count=0,
                drops_count=0,
            ),
        },
        {
            "name": "c8_error_response",
            "model": ErrorResponse,
            "example": ErrorResponse(
                error=ErrorDetail(
                    code="UNAUTHORIZED", message="Unauthorized access", correlation_id="corr-12345"
                )
            ),
        },
        # Contract C9 Alerts
        {"name": "c9_alert_record", "model": AlertRecord, "example": alert_record},
    ]


def export_examples(check_mode: bool = False, output_dir: Path = FIXTURES_DIR) -> int:
    """Generate or verify JSON Schema and example files."""
    definitions = get_golden_definitions()
    output_dir.mkdir(parents=True, exist_ok=True)

    discrepancies: list[str] = []

    for item in definitions:
        name = item["name"]
        model: type[BaseModel] = item["model"]
        example_inst: BaseModel = item["example"]

        schema_file = output_dir / f"{name}.schema.json"
        example_file = output_dir / f"{name}.example.json"

        # Generate schema & example JSON
        schema_json = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        example_json = (
            json.dumps(example_inst.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        )

        if check_mode:
            # Check schema
            if not schema_file.exists():
                discrepancies.append(f"Missing schema file: {schema_file}")
            else:
                existing_schema = schema_file.read_text(encoding="utf-8")
                if existing_schema != schema_json:
                    discrepancies.append(f"Schema drift detected in {schema_file}")

            # Check example
            if not example_file.exists():
                discrepancies.append(f"Missing example file: {example_file}")
            else:
                existing_example = example_file.read_text(encoding="utf-8")
                if existing_example != example_json:
                    discrepancies.append(f"Example drift detected in {example_file}")
        else:
            schema_file.write_text(schema_json, encoding="utf-8")
            example_file.write_text(example_json, encoding="utf-8")
            print(f"Exported: {schema_file.name} & {example_file.name}")

    if check_mode:
        if discrepancies:
            print("ERROR: Contract example drift check failed!", file=sys.stderr)
            for d in discrepancies:
                print(f"  - {d}", file=sys.stderr)
            print(
                "\nRun 'python scripts/export_contract_examples.py' to regenerate fixtures.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: All {len(definitions)} contract schemas and examples match committed fixtures.")
        return 0

    print(f"\nSuccessfully exported {len(definitions)} schemas and examples to {output_dir}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export contract JSON schemas and golden fixtures."
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail with non-zero exit code if files have drifted."
    )
    parser.add_argument(
        "--out-dir", type=Path, default=FIXTURES_DIR, help="Target directory for fixtures."
    )
    args = parser.parse_args()

    exit_code = export_examples(check_mode=args.check, output_dir=args.out_dir)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

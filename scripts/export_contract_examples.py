#!/usr/bin/env python3
"""Export JSON Schema and golden examples for Contract C7, C8, C9, C11 models (T10-008, T16-005).

Emits schemas and golden test fixtures to tests/fixtures/stream/ for:
1. Python unit tests and contract drift verification (--check).
2. Android Kotlin client deserialization tests (Contract C7 ingest).
3. React TypeScript frontend type generation in frontend/src/types/ (C8, C9, C11).

Usage:
    python scripts/export_contract_examples.py           # Generate / update fixtures & TS types
    python scripts/export_contract_examples.py --check   # Verify committed files match schemas
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
    BundlePrivacy,
    BundleSamples,
    BundleSession,
    ConnectionEvent,
    DemoBundle,
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
TYPES_DIR = Path("frontend/src/types")


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
        ml={
            "anomaly_type": "PERSISTENT_POOR_QUALITY",
            "max_severity": "MEDIUM",
            "sample_count": 8,
        },
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

    demo_bundle = DemoBundle(
        bundle_version=1,
        generated_at="2026-10-12T10:00:00Z",
        model_version="1.0.0",
        source="sample",
        privacy=BundlePrivacy(
            time="device-local, no timezone",
            cell_ids="hashed",
            salt_hash="a1b2c3d4e5f60718",
            cell_lookup={"pci": {"42": "Cell-A"}, "nci": {"13322280247": "Cell-A"}},
        ),
        sessions=[
            BundleSession(
                session_id="samsung-1",
                device="Samsung Galaxy S21",
                operator="Jio",
                start="2026-10-09 10:15:00",
                end="2026-10-09 10:15:06",
                n=3,
            )
        ],
        samples=BundleSamples(
            columns=[
                "timestamp",
                "device",
                "operator",
                "network_type",
                "deployment_mode",
                "registered",
                "ss_rsrp",
                "ss_rsrq",
                "ss_sinr",
                "pci",
                "nci",
                "nrarfcn",
                "session_id",
                "sample_idx",
                "is_anom",
                "anomaly_type",
                "severity",
                "baseline_flag",
                "if_flag",
                "if_score",
            ],
            rows=[
                [
                    "2026-10-09 10:15:00",
                    "Samsung Galaxy S21",
                    "Jio",
                    "5G",
                    "NSA",
                    True,
                    -95.0,
                    -11.0,
                    18.5,
                    42,
                    13322280247,
                    632000,
                    "samsung-1",
                    0,
                    False,
                    "NORMAL",
                    "NONE",
                    False,
                    False,
                    0.12,
                ]
            ],
        ),
        transitions=[
            {
                "device": "Samsung Galaxy S21",
                "session_id": "samsung-1",
                "timestamp": "2026-10-09 10:15:03",
                "sample_idx": 1,
                "type": "PCI",
                "from_cell": "Cell-A",
                "to_cell": "Cell-B",
            }
        ],
        events=[
            {
                "event_id": "e-001",
                "session_id": "samsung-1",
                "start": "2026-10-09 10:15:00",
                "end": "2026-10-09 10:15:06",
                "anomaly_type": "SIGNAL_DEGRADATION",
                "max_severity": "LOW",
                "status": "FINAL",
            }
        ],
        quality={"total_raw": 3, "clean_rows": 3, "dropped": 0},
        model_meta={"model_name": "if_v1", "model_version": "1.0.0", "contamination": 0.05},
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
        # Contract C11 Demo Bundle
        {"name": "c11_demo_bundle", "model": DemoBundle, "example": demo_bundle},
    ]


def generate_typescript_contracts() -> str:
    """Generate strongly-typed TypeScript interfaces from Contract C8, C9, and C11 schemas."""
    return """/**
 * Auto-generated Contract TypeScript Definitions (T16-005).
 * Generated by scripts/export_contract_examples.py.
 * DO NOT EDIT DIRECTLY. Run `python scripts/export_contract_examples.py` to regenerate.
 */

// ==============================================================================
// Domain Literals & Enums
// ==============================================================================

export type AnomalyType =
  | 'NORMAL'
  | 'SIGNAL_DEGRADATION'
  | 'SUDDEN_SIGNAL_DEGRADATION'
  | 'PERSISTENT_POOR_QUALITY'
  | 'NETWORK_STATE_TRANSITION'
  | 'CELL_TRANSITION'
  | 'COMBINED_ANOMALY'
  | 'STATISTICAL_ONLY';

export type Severity = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH';

export type EventStatus = 'PROVISIONAL' | 'FINAL';

export type ConnectionState =
  | 'LIVE'
  | 'STALE'
  | 'RECONNECTING'
  | 'WAITING'
  | 'DISCONNECTED'
  | 'REPLAY-SOURCE';

export type AlertKind = 'NEW' | 'ESCALATION' | 'RESOLVED';

export type DeploymentMode = 'NSA' | 'SA' | 'UNKNOWN';

// ==============================================================================
// Contract C8: Live Streaming & Telemetry Models
// ==============================================================================

export interface ScoredSample {
  timestamp: string;
  device: string;
  manufacturer?: string | null;
  android?: string | null;
  operator?: string | null;
  network_type?: string | null;
  deployment_mode?: string | null;
  display_override?: string | null;
  registered?: boolean | null;
  ss_rsrp?: number | null;
  ss_rsrq?: number | null;
  ss_sinr?: number | null;
  csi_rsrp?: number | null;
  csi_rsrq?: number | null;
  csi_sinr?: number | null;
  pci?: number | null;
  nci?: number | null;
  nrarfcn?: number | null;
  session_id: string;
  sample_idx: number;
  is_valid: boolean;
  model_eligible: boolean;
  csi_available: boolean;
  is_synthetic: boolean;
  source_file?: string | null;
  dup_ts: boolean;
  delta_rsrp?: number | null;
  delta_rsrq?: number | null;
  delta_sinr?: number | null;
  pci_changed?: number | boolean | null;
  nci_changed?: number | boolean | null;
  network_changed?: number | boolean | null;
  rolling_mean_rsrp?: number | null;
  rolling_std_rsrp?: number | null;
  rolling_mean_rsrq?: number | null;
  rolling_std_rsrq?: number | null;
  rolling_mean_sinr?: number | null;
  rolling_std_sinr?: number | null;
  weak_rsrp_run?: number | null;
  poor_rsrq_run?: number | null;
  poor_sinr_run?: number | null;
  baseline_z_rsrp?: number | null;
  baseline_z_rsrq?: number | null;
  baseline_z_sinr?: number | null;
  baseline_z_max?: number | null;
  baseline_flag: boolean;
  if_score?: number | null;
  if_flag: boolean;
  anomaly_type: AnomalyType | string;
  severity: Severity | string;
  event_id?: string | null;
  is_anom: boolean;
  seq: number;
  received_at: string;
  scored_at: string;
  published_at: string;
  edge_if_score?: number | null;
  edge_divergence?: number | null;
}

export interface LiveSampleEvent {
  type: 'sample';
  schema_version: number;
  server_time: string;
  session_id: string;
  sample: ScoredSample;
}

export interface EventRecord {
  event_id: string;
  session_id: string;
  start: string;
  end: string;
  sample_count: number;
  anomaly_type: AnomalyType | string;
  max_severity: Severity | string;
  ml: Record<string, unknown>;
  signal: Record<string, unknown>;
  cell: Record<string, unknown>;
  network: Record<string, unknown>;
  diagnosis: Record<string, unknown>;
  recommendation: Record<string, unknown>;
  status: EventStatus | string;
  alert_decision?: Record<string, unknown> | null;
}

export interface LiveEventOpen {
  type: 'event_open';
  schema_version: number;
  server_time: string;
  session_id: string;
  event: EventRecord;
}

export interface LiveEventUpdate {
  type: 'event_update';
  schema_version: number;
  server_time: string;
  session_id: string;
  event: EventRecord;
}

export interface LiveEventClosed {
  type: 'event_closed';
  schema_version: number;
  server_time: string;
  session_id: string;
  event: EventRecord;
}

export interface ConnectionEvent {
  type: 'connection';
  schema_version: number;
  server_time: string;
  state: ConnectionState;
  device?: string | null;
  session_id?: string | null;
  sample_age_s?: number | null;
  message?: string | null;
}

export interface SnapshotEvent {
  type: 'snapshot';
  schema_version: number;
  server_time: string;
  session_id: string;
  device: string;
  latest_sample?: ScoredSample | null;
  state: ConnectionState;
  open_events: EventRecord[];
  last_alerts: Record<string, unknown>[];
}

export interface DroppedEvent {
  type: 'dropped';
  schema_version: number;
  server_time: string;
  session_id?: string | null;
  count: number;
}

export interface HeartbeatEvent {
  type: 'heartbeat';
  schema_version: number;
  server_time: string;
}

export interface BrowserAuthFrame {
  type: 'auth';
  ticket: string;
}

// ==============================================================================
// Contract C8: REST API Response Models
// ==============================================================================

export interface HealthResponse {
  status: string;
  version: string;
  model_version: string;
  uptime_s: number;
  active_sessions: number;
}

export interface SessionSummary {
  session_id: string;
  device: string;
  operator: string;
  start_time: string;
  last_time: string;
  sample_count: number;
  anomaly_count: number;
  is_active: boolean;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
}

export interface SamplesResponse {
  session_id: string;
  samples: ScoredSample[];
  total_count: number;
  has_more: boolean;
}

export interface EventsResponse {
  session_id: string;
  events: EventRecord[];
  total_count: number;
}

export interface ModelInfoResponse {
  model_name: string;
  model_version: string;
  feature_columns: string[];
  feature_hash: string;
  training_rows?: number | null;
  contamination?: number | null;
  created_at?: string | null;
}

export interface MetricsResponse {
  p50_latency_ms: number;
  p95_latency_ms: number;
  max_latency_ms: number;
  duplicates_count: number;
  drops_count: number;
}

export interface ErrorDetail {
  code: string;
  message: string;
  correlation_id?: string | null;
}

export interface ErrorResponse {
  error: ErrorDetail;
}

// ==============================================================================
// Contract C9: Alert Models
// ==============================================================================

export interface AlertDelivery {
  channel: string;
  status: string;
  detail?: string | null;
}

export interface AlertRecord {
  alert_id: string;
  created_at: string;
  event_id: string;
  session_id: string;
  source: 'phone' | 'server' | 'replay';
  kind: AlertKind;
  severity: string;
  anomaly_type: string;
  event_status: EventStatus;
  title: string;
  body: string;
  evidence: string[];
  recommendation: Record<string, unknown>;
  policy: Record<string, unknown>;
  delivery: AlertDelivery[];
  acknowledged_at?: string | null;
}

// ==============================================================================
// Contract C11: Demo Data Bundle Models
// ==============================================================================

export interface BundlePrivacy {
  time: string;
  cell_ids: 'raw' | 'hashed';
  salt_hash?: string | null;
  cell_lookup?: Record<string, unknown> | null;
}

export interface BundleSession {
  session_id: string;
  device: string;
  operator?: string | null;
  start: string;
  end: string;
  n: number;
}

export interface BundleSamples {
  columns: string[];
  rows: (number | string | boolean | null)[][];
}

export interface BundleTransition {
  device: string;
  session_id: string;
  timestamp: string;
  sample_idx: number;
  pci_from?: number | string | null;
  pci_to?: number | string | null;
  nci_from?: number | string | null;
  nci_to?: number | string | null;
  nrarfcn_from?: number | null;
  nrarfcn_to?: number | null;
  kind?: string | null;
  type?: string | null;
  from_cell?: string | null;
  to_cell?: string | null;
}

export interface DemoBundle {
  bundle_version: number;
  generated_at: string;
  model_version: string;
  source: 'processed' | 'sample';
  privacy: BundlePrivacy;
  sessions: BundleSession[];
  samples: BundleSamples;
  transitions: BundleTransition[];
  events: EventRecord[] | Record<string, unknown>[];
  quality: Record<string, unknown>;
  model_meta: Record<string, unknown>;
}
"""


def export_examples(
    check_mode: bool = False,
    output_dir: Path = FIXTURES_DIR,
    types_dir: Path = TYPES_DIR,
) -> int:
    """Generate or verify JSON Schema, example files, and TypeScript definitions."""
    definitions = get_golden_definitions()
    output_dir.mkdir(parents=True, exist_ok=True)
    types_dir.mkdir(parents=True, exist_ok=True)

    discrepancies: list[str] = []

    # 1. Export JSON Schemas and golden examples
    for item in definitions:
        name = item["name"]
        model: type[BaseModel] = item["model"]
        example_inst: BaseModel = item["example"]

        schema_file = output_dir / f"{name}.schema.json"
        example_file = output_dir / f"{name}.example.json"

        schema_json = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        example_json = (
            json.dumps(example_inst.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        )

        if check_mode:
            if not schema_file.exists():
                discrepancies.append(f"Missing schema file: {schema_file}")
            else:
                existing_schema = schema_file.read_text(encoding="utf-8")
                if existing_schema != schema_json:
                    discrepancies.append(f"Schema drift detected in {schema_file}")

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

    # 2. Export / verify TypeScript type definitions
    ts_content = generate_typescript_contracts()
    ts_file = types_dir / "contracts.ts"
    index_file = types_dir / "index.ts"
    index_content = "export * from './contracts';\n"

    if check_mode:
        if not ts_file.exists():
            discrepancies.append(f"Missing TypeScript types file: {ts_file}")
        else:
            existing_ts = ts_file.read_text(encoding="utf-8")
            if existing_ts != ts_content:
                discrepancies.append(f"TypeScript type drift detected in {ts_file}")

        if not index_file.exists():
            discrepancies.append(f"Missing TypeScript index file: {index_file}")
        else:
            existing_index = index_file.read_text(encoding="utf-8")
            if existing_index != index_content:
                discrepancies.append(f"TypeScript index drift detected in {index_file}")
    else:
        ts_file.write_text(ts_content, encoding="utf-8")
        index_file.write_text(index_content, encoding="utf-8")
        print(f"Generated: {ts_file} & {index_file}")

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
        print(f"OK: All {len(definitions)} contract schemas and TS types match committed files.")
        return 0

    print(f"\nSuccessfully exported {len(definitions)} schemas, examples, and TypeScript types.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export contract JSON schemas, golden fixtures, and TypeScript types."
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail with non-zero exit code if files have drifted."
    )
    parser.add_argument(
        "--out-dir", type=Path, default=FIXTURES_DIR, help="Target directory for fixtures."
    )
    parser.add_argument(
        "--types-dir", type=Path, default=TYPES_DIR, help="Target directory for TS types."
    )
    args = parser.parse_args()

    exit_code = export_examples(
        check_mode=args.check, output_dir=args.out_dir, types_dir=args.types_dir
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

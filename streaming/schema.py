"""Wire schema models for streaming contracts C7, C8, and C9.

Defines Pydantic data models for phone-to-server ingest protocol (C7),
server-to-dashboard live telemetry and REST responses (C8), and alert records
dispatched across notification channels (C9).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ml.config import MAX_MESSAGE_BYTES, MAX_MSGS_PER_MIN

SCHEMA_VERSION: int = 2

# Error codes for Contract C7 / C8
ERROR_CODES = {
    "UNAUTHORIZED": "UNAUTHORIZED",
    "VERSION_MISMATCH": "VERSION_MISMATCH",
    "BAD_MESSAGE": "BAD_MESSAGE",
    "SCHEMA_ERROR": "SCHEMA_ERROR",
    "RATE_LIMITED": "RATE_LIMITED",
    "TOO_LARGE": "TOO_LARGE",
    "SESSION_CONFLICT": "SESSION_CONFLICT",
    "INTERNAL": "INTERNAL",
}


def validate_iso_with_tz(v: str, field_name: str = "timestamp") -> str:
    """Validate string is a valid ISO-8601 datetime with explicit timezone offset."""
    try:
        dt = datetime.fromisoformat(v)
    except Exception as e:
        raise ValueError(f"{field_name} must be a valid ISO-8601 datetime: {e}") from e

    if dt.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone offset (e.g. +05:30 or Z)")
    return v


# ==============================================================================
# Contract C7: Client -> Server Models
# ==============================================================================


class EdgeHelloInfo(BaseModel):
    """Optional edge inference status reported during hello handshake."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    model_version: str | None = None
    feature_hash: str | None = None


class IngestHello(BaseModel):
    """Initial client hello message upon WebSocket connection (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["hello"] = "hello"
    schema_version: int = SCHEMA_VERSION
    client_id: str = Field(..., min_length=1, max_length=128)
    session_label: str = Field(..., max_length=128)
    device: str = Field(..., max_length=100)
    manufacturer: str = Field(..., max_length=100)
    android: str = Field(..., max_length=50)
    operator: str = Field(..., max_length=100)
    app_version: str = Field(..., max_length=50)
    resume_from_seq: int = Field(default=0, ge=0)
    queue_depth: int = Field(default=0, ge=0)
    dropped_from_queue: int = Field(default=0, ge=0)
    edge: EdgeHelloInfo | None = None


class EdgeSampleInfo(BaseModel):
    """Optional advisory edge inference score sent alongside a sample."""

    model_config = ConfigDict(extra="ignore")

    if_score: float | None = None
    model_version: str | None = None
    feature_hash: str | None = None


class IngestPayload(BaseModel):
    """Raw telemetry measurement payload carrying exactly the 18 C1 columns.

    Unknown fields are strictly forbidden per Contract C7. NA strings and sentinels
    are accepted and coerced to None / missing values where appropriate.
    """

    model_config = ConfigDict(extra="forbid")

    timestamp: str = Field(..., max_length=64)  # Raw collector dd-MM-yy HH:mm:ss string
    device: str = Field(..., max_length=100)
    manufacturer: str = Field(..., max_length=100)
    android: str = Field(..., max_length=50)
    operator: str = Field(..., max_length=100)
    network_type: str = Field(..., max_length=50)
    deployment_mode: str = Field(default="UNKNOWN", max_length=50)
    display_override: str | None = None
    registered: bool | None = None
    ss_rsrp: float | None = None
    ss_rsrq: float | None = None
    ss_sinr: float | None = None
    csi_rsrp: float | None = None
    csi_rsrq: float | None = None
    csi_sinr: float | None = None
    pci: int | float | None = None
    nci: int | float | None = None
    nrarfcn: int | float | None = None

    @model_validator(mode="before")
    @classmethod
    def convert_na_tokens(cls, data: Any) -> Any:
        """Convert 'NA' strings to None for nullable/numeric fields."""
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if v == "NA" or v == "":
                    clean[k] = None
                else:
                    clean[k] = v
            return clean
        return data


class IngestSample(BaseModel):
    """Single telemetry measurement message from phone collector (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["sample"] = "sample"
    schema_version: int = SCHEMA_VERSION
    seq: int = Field(..., ge=0)
    sent_at: str = Field(...)  # ISO-8601 with timezone offset
    payload: IngestPayload
    edge: EdgeSampleInfo | None = None

    @field_validator("sent_at")
    @classmethod
    def validate_sent_at_has_tz(cls, v: str) -> str:
        """Validate sent_at is valid ISO-8601 and has an explicit timezone offset."""
        try:
            dt = datetime.fromisoformat(v)
        except Exception as e:
            raise ValueError(f"sent_at must be a valid ISO-8601 datetime: {e}") from e

        if dt.tzinfo is None:
            raise ValueError("sent_at must include a timezone offset (e.g. +05:30 or Z)")
        return v


class IngestPing(BaseModel):
    """Heartbeat ping from client (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["ping"] = "ping"
    schema_version: int = SCHEMA_VERSION
    queue_depth: int = Field(default=0, ge=0)
    dropped_from_queue: int = Field(default=0, ge=0)


class IngestBye(BaseModel):
    """Clean session disconnect message from client (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["bye"] = "bye"
    schema_version: int = SCHEMA_VERSION
    reason: str = Field(default="user_stopped", max_length=64)


ClientMessage = Annotated[
    IngestHello | IngestSample | IngestPing | IngestBye,
    Field(discriminator="type"),
]


# ==============================================================================
# Contract C7: Server -> Client Messages
# ==============================================================================


class IngestLimits(BaseModel):
    """Operational server limits negotiated during hello handshake."""

    model_config = ConfigDict(extra="ignore")

    max_message_bytes: int = MAX_MESSAGE_BYTES
    max_msgs_per_min: int = MAX_MSGS_PER_MIN


class HelloAck(BaseModel):
    """Server handshake acknowledgment accepting an ingest session (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["hello_ack"] = "hello_ack"
    schema_version: int = SCHEMA_VERSION
    session_id: str
    server_time: str
    last_seq_acked: int = Field(default=0, ge=0)
    model_version: str = "if_v1"
    limits: IngestLimits = Field(default_factory=IngestLimits)


class Ack(BaseModel):
    """Cumulative delivery acknowledgment sent from server to client (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["ack"] = "ack"
    schema_version: int = SCHEMA_VERSION
    seq: int = Field(..., ge=0)


class ErrorMsg(BaseModel):
    """Error message returned to client on contract or operational violations (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["error"] = "error"
    schema_version: int = SCHEMA_VERSION
    code: str
    message: str
    fatal: bool = False
    seq: int | None = None


class AlertPush(BaseModel):
    """Compact alert push notification sent from server to client (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["alert"] = "alert"
    schema_version: int = SCHEMA_VERSION
    alert: dict[str, Any]


class Pong(BaseModel):
    """Heartbeat response to client ping (C7)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["pong"] = "pong"
    schema_version: int = SCHEMA_VERSION
    server_time: str


# ==============================================================================
# Contract C8: Live Event Models (Server -> Dashboard / Live Subscribers)
# ==============================================================================

# Closed enum of the five fixed alert decision reasons from DESIGN_v2 / TECH_RULES_v2
ALERT_DECISION_REASONS = (
    "Alert triggered",
    "ML-only (no rule evidence)",
    "Transition only",
    "Below persistence/severity threshold",
    "Cooldown active",
)

AlertDecisionReason = Literal[
    "Alert triggered",
    "ML-only (no rule evidence)",
    "Transition only",
    "Below persistence/severity threshold",
    "Cooldown active",
]

EventStatus = Literal["PROVISIONAL", "FINAL"]
ConnectionState = Literal[
    "LIVE", "STALE", "RECONNECTING", "WAITING", "DISCONNECTED", "REPLAY-SOURCE"
]
SessionStatus = Literal["OPEN", "CLOSED", "INCOMPLETE"]
StreamSource = Literal["phone", "replay"]


class AlertDecision(BaseModel):
    """Decision record indicating whether an event fired an alert and why."""

    model_config = ConfigDict(extra="ignore")

    alerted: bool
    reason: AlertDecisionReason


class ScoredSample(BaseModel):
    """One scored sample bearing all C4 columns plus C8 streaming metadata."""

    model_config = ConfigDict(extra="ignore")

    # Raw measurement & collector columns (C1)
    timestamp: str
    device: str
    manufacturer: str | None = None
    android: str | None = None
    operator: str | None = None
    network_type: str | None = None
    deployment_mode: str | None = None
    display_override: str | None = None
    registered: bool | None = None
    ss_rsrp: float | None = None
    ss_rsrq: float | None = None
    ss_sinr: float | None = None
    csi_rsrp: float | None = None
    csi_rsrq: float | None = None
    csi_sinr: float | None = None
    pci: int | None = None
    nci: int | None = None
    nrarfcn: int | None = None

    # Pipeline metadata & validity flags
    session_id: str
    sample_idx: int = 0
    is_valid: bool = True
    model_eligible: bool = True
    csi_available: bool = False
    is_synthetic: bool = False
    source_file: str | None = None
    dup_ts: bool = False

    # Feature columns (C3 subset)
    delta_rsrp: float | None = None
    delta_rsrq: float | None = None
    delta_sinr: float | None = None
    pci_changed: int | bool | None = None
    nci_changed: int | bool | None = None
    network_changed: int | bool | None = None
    rolling_mean_rsrp: float | None = None
    rolling_std_rsrp: float | None = None
    rolling_mean_rsrq: float | None = None
    rolling_std_rsrq: float | None = None
    rolling_mean_sinr: float | None = None
    rolling_std_sinr: float | None = None
    weak_rsrp_run: int | None = None
    poor_rsrq_run: int | None = None
    poor_sinr_run: int | None = None

    # Score & anomaly classification columns (C4)
    baseline_z_rsrp: float | None = None
    baseline_z_rsrq: float | None = None
    baseline_z_sinr: float | None = None
    baseline_z_max: float | None = None
    baseline_flag: bool = False
    if_score: float | None = None
    if_flag: bool = False
    anomaly_type: str = "NORMAL"
    severity: str = "NONE"
    event_id: str | None = None
    is_anom: bool = False

    # Streaming-specific extensions (C8)
    seq: int = Field(..., ge=0)
    received_at: str
    scored_at: str
    published_at: str
    edge_if_score: float | None = None
    edge_divergence: float | None = None

    @field_validator("received_at", "scored_at", "published_at")
    @classmethod
    def _validate_iso8601_timestamps(cls, v: str) -> str:
        validate_iso_with_tz(v)
        return v


class EventRecord(BaseModel):
    """C5-compatible diagnosed event record with C8 status and alert decision."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    session_id: str
    start: str
    end: str
    anomaly_type: str
    severity: str
    ml: dict[str, Any]
    signal: dict[str, Any] | None = None
    cell: dict[str, Any] | None = None
    network: dict[str, Any] | None = None
    signal_report: dict[str, Any] | None = None
    cell_report: dict[str, Any] | None = None
    network_report: dict[str, Any] | None = None
    diagnosis: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    explanation_text: str | None = None

    # Contract C8 additions:
    status: EventStatus
    alert_decision: AlertDecision


# ------------------------------------------------------------------------------
# WebSocket /api/v1/live Event Messages
# ------------------------------------------------------------------------------


class LiveSampleEvent(BaseModel):
    """Live scored sample broadcast on /api/v1/live (C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["sample"] = "sample"
    schema_version: int = SCHEMA_VERSION
    server_time: str
    session_id: str
    sample: ScoredSample


class LiveEventOpen(BaseModel):
    """Event open notification (C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["event_open"] = "event_open"
    schema_version: int = SCHEMA_VERSION
    server_time: str
    session_id: str
    event: EventRecord


class LiveEventUpdate(BaseModel):
    """Event update notification while provisional (C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["event_update"] = "event_update"
    schema_version: int = SCHEMA_VERSION
    server_time: str
    session_id: str
    event: EventRecord


class LiveEventClosed(BaseModel):
    """Event closed notification (transitions to FINAL, C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["event_closed"] = "event_closed"
    schema_version: int = SCHEMA_VERSION
    server_time: str
    session_id: str
    event: EventRecord


class ConnectionEvent(BaseModel):
    """Server-authoritative connection & freshness state event (C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["connection"] = "connection"
    schema_version: int = SCHEMA_VERSION
    server_time: str
    session_id: str | None = None
    state: ConnectionState
    last_sample_age_s: float | None = None
    source: StreamSource | None = None


class SnapshotEvent(BaseModel):
    """Initial connection snapshot emitted to newly connected live subscribers (C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["snapshot"] = "snapshot"
    schema_version: int = SCHEMA_VERSION
    server_time: str
    session_id: str
    latest_sample: ScoredSample | None = None
    state: ConnectionState
    open_events: list[EventRecord] = Field(default_factory=list)
    last_alerts: list[dict[str, Any]] = Field(default_factory=list)


class DroppedEvent(BaseModel):
    """Queue overflow warning informing subscriber to resync state via REST (C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["dropped"] = "dropped"
    schema_version: int = SCHEMA_VERSION
    server_time: str
    session_id: str | None = None
    count: int = Field(..., ge=1)


class HeartbeatEvent(BaseModel):
    """Periodic 5-second server heartbeat frame (C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["heartbeat"] = "heartbeat"
    schema_version: int = SCHEMA_VERSION
    server_time: str
    session_id: str | None = None


class BrowserAuthFrame(BaseModel):
    """First-frame browser ticket auth on WS /api/v1/live within 5s of connect (C8)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["auth"] = "auth"
    ticket: str = Field(..., min_length=1, max_length=256)


LiveSubscriberMessage = Annotated[
    LiveSampleEvent
    | LiveEventOpen
    | LiveEventUpdate
    | LiveEventClosed
    | ConnectionEvent
    | SnapshotEvent
    | DroppedEvent
    | HeartbeatEvent,
    Field(discriminator="type"),
]


# ==============================================================================
# Contract C8: REST API Response Models
# ==============================================================================


class HealthResponse(BaseModel):
    """Public healthcheck response for GET /healthz (C8)."""

    model_config = ConfigDict(extra="ignore")

    status: str = "ok"
    version: str = "2.0.0"
    uptime_s: float = Field(..., ge=0.0)


class SessionSummary(BaseModel):
    """Session metadata summary item (C8)."""

    model_config = ConfigDict(extra="ignore")

    session_id: str
    source: StreamSource
    status: SessionStatus
    sample_count: int = Field(default=0, ge=0)
    event_count: int = Field(default=0, ge=0)
    start_time: str | None = None
    end_time: str | None = None


class SessionListResponse(BaseModel):
    """Response payload for GET /api/v1/sessions."""

    model_config = ConfigDict(extra="ignore")

    sessions: list[SessionSummary] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class SamplesResponse(BaseModel):
    """Response payload for GET /api/v1/sessions/{id}/samples."""

    model_config = ConfigDict(extra="ignore")

    samples: list[ScoredSample] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    has_more: bool = False


class EventsResponse(BaseModel):
    """Response payload for GET /api/v1/sessions/{id}/events."""

    model_config = ConfigDict(extra="ignore")

    events: list[EventRecord] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class ModelInfoResponse(BaseModel):
    """Response payload for GET /api/v1/model."""

    model_config = ConfigDict(extra="ignore")

    model_version: str
    feature_columns: list[str] = Field(default_factory=list)
    feature_hash: str
    thresholds: dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    """Response payload for GET /api/v1/metrics."""

    model_config = ConfigDict(extra="ignore")

    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    max_latency_ms: float | None = None
    sequence_gaps: list[dict[str, int]] = Field(default_factory=list)
    duplicates_count: int = 0
    drops_count: int = 0
    skew_estimate_s: float | None = None
    queue_depth: int = 0


class ErrorDetail(BaseModel):
    """Error detail block adhering strictly to C8 error specification."""

    model_config = ConfigDict(extra="ignore")

    code: str
    message: str
    correlation_id: str


class ErrorResponse(BaseModel):
    """Generic REST error envelope returning C8 error body without stack traces."""

    model_config = ConfigDict(extra="ignore")

    error: ErrorDetail


# ==============================================================================
# Contract C9: Alert Models & Log Format (alerts.jsonl, webhooks, alert events)
# ==============================================================================

AlertKind = Literal["NEW", "ESCALATION", "RESOLVED"]
DeliveryStatus = Literal["OK", "FAILED", "SKIPPED"]


class AlertDelivery(BaseModel):
    """Per-channel delivery attempt result."""

    model_config = ConfigDict(extra="ignore")

    channel: str
    status: DeliveryStatus
    detail: str | None = None


class AlertRecord(BaseModel):
    """Alert record specification for alerts.jsonl, alert events, and external dispatches."""

    model_config = ConfigDict(extra="ignore")

    alert_id: str
    created_at: str
    event_id: str
    session_id: str
    source: StreamSource
    kind: AlertKind
    severity: str
    anomaly_type: str
    event_status: EventStatus
    title: str
    body: str
    evidence: list[str] = Field(default_factory=list)
    recommendation: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    delivery: list[AlertDelivery] = Field(default_factory=list)
    acknowledged_at: str | None = None

    @field_validator("created_at")
    @classmethod
    def _validate_created_at_has_tz(cls, v: str) -> str:
        validate_iso_with_tz(v, field_name="created_at")
        return v

    def to_webhook_body(self, include_evidence: bool = False) -> dict[str, Any]:
        """Return webhook/email payload subset conforming to G26 data minimization.

        By default excludes raw measurements, cell IDs, device IDs, and evidence.
        """
        payload = {
            "title": self.title,
            "body": self.body,
            "severity": self.severity,
            "anomaly_type": self.anomaly_type,
            "event_status": self.event_status,
            "created_at": self.created_at,
        }
        if include_evidence:
            payload["evidence"] = self.evidence
        return payload


def serialize_alert_jsonl(alert: AlertRecord) -> str:
    """Serialize an AlertRecord as a single-line JSON string for alerts.jsonl."""
    return alert.model_dump_json() + "\n"


def deserialize_alert_jsonl(line: str) -> AlertRecord:
    """Deserialize a single JSON line from alerts.jsonl into an AlertRecord."""
    return AlertRecord.model_validate_json(line.strip())


# ==============================================================================
# Contract C11: Demo Data Bundle Models (T16-002, T16-005)
# ==============================================================================


class BundlePrivacy(BaseModel):
    """Privacy configuration and cell anonymisation lookup (C11, G27)."""

    model_config = ConfigDict(extra="ignore")

    time: str = "device-local, no timezone"
    cell_ids: Literal["raw", "hashed"] = "hashed"
    salt_hash: str | None = None
    cell_lookup: dict[str, Any] | None = None


class BundleSession(BaseModel):
    """Session summary within demo bundle (C11)."""

    model_config = ConfigDict(extra="ignore")

    session_id: str
    device: str
    operator: str | None = None
    start: str
    end: str
    n: int = Field(..., ge=0)


class BundleSamples(BaseModel):
    """Columnar sample representation within demo bundle (C11)."""

    model_config = ConfigDict(extra="ignore")

    columns: list[str]
    rows: list[list[Any]]


class BundleTransition(BaseModel):
    """Precomputed handover / transition record (C11, T16-002)."""

    model_config = ConfigDict(extra="ignore")

    device: str
    session_id: str
    timestamp: str
    sample_idx: int
    pci_from: int | str | None = None
    pci_to: int | str | None = None
    nci_from: int | str | None = None
    nci_to: int | str | None = None
    nrarfcn_from: int | None = None
    nrarfcn_to: int | None = None
    kind: str | None = None


class DemoBundle(BaseModel):
    """Contract C11: Offline demo data bundle for the static React dashboard."""

    model_config = ConfigDict(extra="ignore")

    bundle_version: int = 1
    generated_at: str
    model_version: str = "1.0.0"
    source: Literal["processed", "sample"] = "processed"
    privacy: BundlePrivacy
    sessions: list[BundleSession]
    samples: BundleSamples
    transitions: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    quality: dict[str, Any] = Field(default_factory=dict)
    model_meta: dict[str, Any] = Field(default_factory=dict)

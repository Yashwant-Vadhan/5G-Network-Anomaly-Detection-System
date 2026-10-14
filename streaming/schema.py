"""Wire schema models for streaming contracts C7, C8, and C9.

Defines Pydantic data models for phone-to-server ingest protocol (C7),
server-to-dashboard live telemetry and REST responses (C8), and alert records
dispatched across notification channels (C9).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    max_message_bytes: int = 8192
    max_msgs_per_min: int = 120


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

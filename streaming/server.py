"""FastAPI application factory, auth dependencies, and route definitions.

Provides the HTTP and WebSocket endpoints for phone telemetry ingest,
viewer live-stream push, health inspection, and REST administration
following the Contracts C7 and C8 specifications.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hmac
import io
import json
import logging
import os
import secrets
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from ml.config import (
    DATA_DIR,
    IDLE_SESSION_TIMEOUT_SECONDS,
    MAX_LIVE_SESSIONS,
    MAX_MESSAGE_BYTES,
    MAX_PAIRING_ATTEMPTS_PER_IP,
    MAX_SEQ_JUMP,
    MAX_SESSION_CREATIONS_PER_IP,
    PAIRING_ATTEMPT_WINDOW_SECONDS,
    PAIRING_CODE_ALPHABET,
    PAIRING_CODE_LENGTH,
    PAIRING_CODE_TTL_SECONDS,
    PAIRING_LOCKOUT_ATTEMPTS,
    PAIRING_LOCKOUT_SECONDS,
    RAW_COLUMNS,
    SESSION_CREATION_WINDOW_SECONDS,
    SESSION_MAX_ROWS,
    TICKET_TTL_SECONDS,
)
from ml.schema import ConfigError, SchemaError
from streaming.connection import ConnectionTracker
from streaming.engine import StreamingEngine
from streaming.event_tracker import EventTracker
from streaming.hub import LiveHub
from streaming.metrics import get_stream_metrics, reset_stream_metrics
from streaming.schema import (
    Ack,
    AlertRecord,
    BatchIngestResponse,
    CreateLiveSessionResponse,
    DeleteLiveSessionResponse,
    ErrorDetail,
    ErrorMsg,
    ErrorResponse,
    EventRecord,
    EventsResponse,
    HealthResponse,
    HeartbeatEvent,
    HelloAck,
    IngestHello,
    IngestLimits,
    IngestSample,
    LiveEventClosed,
    LiveEventOpen,
    LiveEventUpdate,
    LiveSampleEvent,
    LiveSessionTicketResponse,
    MetricsResponse,
    ModelInfoResponse,
    PairRequest,
    PairResponse,
    Pong,
    SamplesResponse,
    ScoredSample,
    SessionListResponse,
    SessionSummary,
    SnapshotEvent,
    deserialize_alert_jsonl,
    serialize_alert_jsonl,
)
from streaming.session_manager import SessionManager
from streaming.store import LiveCaptureStore

logger = logging.getLogger("streaming.server")


class TokenBucket:
    """Thread-safe token-bucket rate limiter for streaming messages."""

    def __init__(self, rate: float, capacity: float) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_check = time.monotonic()

    def allow(self, cost: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_check
        self.last_check = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


@dataclass(frozen=True)
class ServerConfig:
    """Runtime server configuration loaded from environment or CLI."""

    host: str = "127.0.0.1"
    port: int = 8000
    ingest_token: str | None = None
    allow_lan: bool = False
    allow_remote_view: bool = False
    mode: str = "local"  # "local" | "public"
    allowed_origins: list[str] = field(default_factory=list)
    retention_enabled: bool = True
    max_sessions: int = 10
    max_msgs_per_min: int = 120
    require_live_auth: bool = False
    max_live_sessions: int = MAX_LIVE_SESSIONS
    max_session_creations_per_ip: int = MAX_SESSION_CREATIONS_PER_IP
    session_creation_window_seconds: int = SESSION_CREATION_WINDOW_SECONDS
    pairing_lockout_attempts: int = PAIRING_LOCKOUT_ATTEMPTS
    pairing_lockout_seconds: int = PAIRING_LOCKOUT_SECONDS
    max_pairing_attempts_per_ip: int = MAX_PAIRING_ATTEMPTS_PER_IP
    pairing_attempt_window_seconds: int = PAIRING_ATTEMPT_WINDOW_SECONDS
    idle_session_timeout_seconds: int = IDLE_SESSION_TIMEOUT_SECONDS

    def validate(self) -> None:
        """Validate server configuration and startup security guards (T18-001)."""
        mode_lower = self.mode.lower().strip()
        if mode_lower not in ("local", "public"):
            raise ConfigError(
                f"Invalid NADS_MODE: '{self.mode}'. Must be 'local' or 'public'. "
                "Fix: set NADS_MODE=local or NADS_MODE=public."
            )

        if mode_lower == "public":
            if not self.allowed_origins:
                raise ConfigError(
                    "Public mode requires explicit NADS_ALLOWED_ORIGINS. "
                    "Fix: set NADS_ALLOWED_ORIGINS=https://your-domain.com."
                )
            if any(o.strip() == "*" for o in self.allowed_origins):
                raise ConfigError(
                    "Wildcard '*' origin is forbidden in public mode. "
                    "Fix: set NADS_ALLOWED_ORIGINS to an explicit domain list."
                )
            if self.retention_enabled:
                raise ConfigError(
                    "Live session retention must be disabled in public mode (Guardrail G29). "
                    "Fix: set NADS_ENABLE_RETENTION=false."
                )

        # Bind policy (T11-019 / Guardrail G20):
        # Default 127.0.0.1; non-loopback requires allow_lan and a non-empty ingest_token
        is_loopback = self.host in ("127.0.0.1", "localhost", "::1")
        if not is_loopback:
            if not self.allow_lan:
                raise ConfigError(
                    f"Binding to non-loopback host '{self.host}' requires --allow-lan "
                    "(or NADS_ALLOW_LAN=true). Fix: pass --allow-lan or bind to 127.0.0.1."
                )
            if not self.ingest_token:
                raise ConfigError(
                    f"Binding to non-loopback host '{self.host}' requires a non-empty "
                    "NADS_INGEST_TOKEN. Fix: set NADS_INGEST_TOKEN=<token> or pass --token=<token>."
                )

    @classmethod
    def from_env(cls) -> ServerConfig:
        """Load configuration from environment variables."""
        token = os.environ.get("NADS_INGEST_TOKEN", "").strip() or None
        allow_lan = os.environ.get("NADS_ALLOW_LAN", "false").lower() in ("1", "true", "yes")
        allow_remote = os.environ.get("NADS_ALLOW_REMOTE_VIEW", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        port_raw = os.environ.get("NADS_PORT", "8000").strip()
        try:
            port = int(port_raw)
        except ValueError:
            port = 8000

        mode = os.environ.get("NADS_MODE", "local").strip().lower()

        raw_origins = os.environ.get("NADS_ALLOWED_ORIGINS", "").strip()
        origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

        retention_raw = os.environ.get("NADS_ENABLE_RETENTION")
        if mode == "public":
            retention_enabled = (
                retention_raw.lower() in ("1", "true", "yes") if retention_raw else False
            )
        else:
            retention_enabled = (
                retention_raw.lower() not in ("0", "false", "no") if retention_raw else True
            )

        max_live_raw = os.environ.get("NADS_MAX_LIVE_SESSIONS", "").strip()
        try:
            max_live_sessions = int(max_live_raw) if max_live_raw else MAX_LIVE_SESSIONS
        except ValueError:
            max_live_sessions = MAX_LIVE_SESSIONS

        idle_reaper_raw = os.environ.get("NADS_IDLE_SESSION_TIMEOUT_SECONDS", "").strip()
        try:
            idle_timeout = int(idle_reaper_raw) if idle_reaper_raw else IDLE_SESSION_TIMEOUT_SECONDS
        except ValueError:
            idle_timeout = IDLE_SESSION_TIMEOUT_SECONDS

        config = cls(
            host=os.environ.get("NADS_HOST", "127.0.0.1").strip(),
            port=port,
            ingest_token=token,
            allow_lan=allow_lan,
            allow_remote_view=allow_remote,
            mode=mode,
            allowed_origins=origins,
            retention_enabled=retention_enabled,
            max_live_sessions=max_live_sessions,
            idle_session_timeout_seconds=idle_timeout,
        )
        config.validate()
        return config


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Ensure every HTTP request has an X-Correlation-ID for auditability."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        corr_id = request.headers.get("X-Correlation-ID")
        if not corr_id:
            corr_id = f"corr-{uuid.uuid4().hex[:12]}"

        request.state.correlation_id = corr_id
        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response


def is_origin_allowed(
    origin: str | None,
    allowed_origins: list[str] | set[str],
    host: str | None = None,
    x_forwarded_host: str | None = None,
) -> bool:
    """Check if an Origin header (or reverse-proxied Host) matches allowed origins."""
    if not allowed_origins:
        return True

    effective_hosts: list[str] = []
    if host:
        effective_hosts.append(host.split(":")[0].strip().lower())
    if x_forwarded_host:
        effective_hosts.append(x_forwarded_host.split(":")[0].strip().lower())

    normalized_allowed: set[str] = set()
    allowed_hostnames: set[str] = set()
    for ao in allowed_origins:
        ao_clean = ao.strip().rstrip("/")
        normalized_allowed.add(ao_clean.lower())
        if "://" in ao_clean:
            allowed_hostnames.add(ao_clean.split("://", 1)[1].split(":")[0].strip().lower())
        else:
            allowed_hostnames.add(ao_clean.split(":")[0].strip().lower())

    if not origin:
        # If Origin header is omitted (e.g. stripped by reverse proxy / Envoy),
        # accept if Host or X-Forwarded-Host matches an allowed origin domain.
        for eh in effective_hosts:
            if eh in allowed_hostnames:
                return True
        return False

    if "," in origin:
        return any(
            is_origin_allowed(part.strip(), allowed_origins, host, x_forwarded_host)
            for part in origin.split(",")
            if part.strip()
        )

    orig_clean = origin.strip().rstrip("/").lower()
    if orig_clean in normalized_allowed:
        return True

    # Strip default port 443 / 80
    if orig_clean.endswith(":443") and orig_clean[:-4] in normalized_allowed:
        return True
    if orig_clean.endswith(":80") and orig_clean[:-3] in normalized_allowed:
        return True

    if "://" in orig_clean:
        orig_hostname = orig_clean.split("://", 1)[1].split(":")[0].strip().lower()
        if orig_hostname in allowed_hostnames:
            return True

    return False


class OriginEnforcementMiddleware(BaseHTTPMiddleware):
    """Enforces Contract C8 Origin header validation on cross-origin requests."""

    def __init__(self, app: Any, allowed_origins: list[str], is_public: bool = False) -> None:
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)
        self.is_public = is_public

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        origin = request.headers.get("origin")
        host = request.headers.get("host")
        xf_host = request.headers.get("x-forwarded-host")
        if origin:
            if self.allowed_origins and not is_origin_allowed(
                origin, self.allowed_origins, host, xf_host
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "FORBIDDEN",
                            "message": f"Origin '{origin}' is not allowed",
                            "correlation_id": get_correlation_id(request),
                        }
                    },
                )
        elif self.is_public and request.method == "OPTIONS":
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Origin header required for preflight in public mode",
                        "correlation_id": get_correlation_id(request),
                    }
                },
            )
        return await call_next(request)


def get_correlation_id(request: Request) -> str:
    """Extract correlation ID from request state or generate a fallback."""
    return getattr(request.state, "correlation_id", f"corr-{uuid.uuid4().hex[:12]}")


def verify_ingest_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> str | None:
    """Validate Bearer token using constant-time comparison against configured token.

    Extension point for Contract C10: per-session ephemeral tokens can be validated here.
    """
    config: ServerConfig = getattr(request.app.state, "config", ServerConfig())
    expected_token = config.ingest_token

    # If no token is configured on the server, local-dev / loopback mode is open
    if not expected_token:
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized: Missing or invalid token scheme")

    provided_token = authorization.removeprefix("Bearer ").strip()

    # Per-session ephemeral token check (Contract C10)
    session_tokens = getattr(request.app.state, "session_ingest_tokens", {})
    if provided_token in session_tokens:
        return provided_token

    # hmac.compare_digest prevents timing side-channel attacks
    if not hmac.compare_digest(provided_token.encode("utf-8"), expected_token.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid token")

    return provided_token


def reap_idle_sessions(app: FastAPI, now: datetime | None = None) -> list[str]:
    """Reap live sessions idle past IDLE_SESSION_TIMEOUT_SECONDS (G29/T18-004)."""
    if now is None:
        now = datetime.now(UTC)
    config: ServerConfig = getattr(app.state, "config", ServerConfig())
    timeout = getattr(config, "idle_session_timeout_seconds", IDLE_SESSION_TIMEOUT_SECONDS)
    cutoff = now - timedelta(seconds=timeout)
    reaped: list[str] = []

    active_sessions = getattr(app.state, "active_live_sessions", {})
    for session_id, meta in list(active_sessions.items()):
        last_active = meta.get("last_active_at") or meta.get("created_at")
        if last_active is None:
            continue
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=UTC)
        expires_at = meta.get("expires_at")
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        is_expired_unpaired = (not meta.get("used", False)) and expires_at and now >= expires_at
        if last_active < cutoff or is_expired_unpaired:
            active_sessions.pop(session_id, None)
            code = meta.get("pairing_code")
            if code and code in app.state.pairing_sessions:
                del app.state.pairing_sessions[code]
            token = meta.get("ingest_token")
            if token and token in app.state.session_ingest_tokens:
                del app.state.session_ingest_tokens[token]
            tickets_to_del = [
                t for t, (sid, _) in app.state.live_session_tickets.items() if sid == session_id
            ]
            for t in tickets_to_del:
                del app.state.live_session_tickets[t]
            app.state.session_samples.pop(session_id, None)
            app.state.session_raw_samples.pop(session_id, None)
            app.state.session_events.pop(session_id, None)
            reaped.append(session_id)
            logger.info("Reaped idle live session %s (last active: %s)", session_id, last_active)

    return reaped


def create_app(
    config: ServerConfig | None = None,
    session_manager: SessionManager | None = None,
    engine: StreamingEngine | None = None,
    hub: LiveHub | None = None,
) -> FastAPI:
    """Factory creating and configuring the FastAPI streaming application."""
    if config is None:
        config = ServerConfig.from_env()
    else:
        config.validate()

    logger.info(
        "Starting 5G-NADS server in %s mode (lan=%s, retention=%s)",
        config.mode.upper(),
        config.allow_lan,
        config.retention_enabled,
    )
    enabled_channels = ["in_app"]
    if os.environ.get("NADS_ALERT_WEBHOOK_URL"):
        enabled_channels.append("webhook")
    if os.environ.get("NADS_ALERT_EMAIL_HOST"):
        enabled_channels.append("email")
    if os.environ.get("NADS_ALERT_PHONE_SMS"):
        enabled_channels.append("phone")
    logger.info("Enabled alert channels: %s", ", ".join(enabled_channels))

    app = FastAPI(
        title="5G-NADS Streaming API",
        version="2.0.0",
        docs_url="/docs" if config.host == "127.0.0.1" else None,
        redoc_url=None,
    )

    app.state.config = config
    app.state.start_time = time.time()
    app.state.session_manager = session_manager or SessionManager()
    if engine is not None:
        app.state.engine = engine
    else:
        try:
            app.state.engine = StreamingEngine(session_manager=app.state.session_manager)
        except Exception:
            app.state.engine = None
    app.state.hub = hub or LiveHub()
    app.state.connection_tracker = ConnectionTracker(hub=app.state.hub)
    app.state.active_ingest_clients: dict[str, WebSocket] = {}
    app.state.latest_samples: dict[str, ScoredSample] = {}
    app.state.session_samples: dict[str, list[ScoredSample]] = {}
    app.state.session_raw_samples: dict[str, list[dict[str, Any]]] = {}
    app.state.session_events: dict[str, list[EventRecord]] = {}
    app.state.session_sources: dict[str, str] = {}
    app.state.alerts: dict[str, AlertRecord] = {}
    app.state.alert_ack_attempts: dict[str, list[float]] = {}
    app.state.pairing_sessions: dict[str, dict[str, Any]] = {}
    app.state.active_live_sessions: dict[str, dict[str, Any]] = {}
    app.state.session_ingest_tokens: dict[str, str] = {}
    app.state.live_session_tickets: dict[str, tuple[str, datetime]] = {}
    app.state.ip_session_creations: dict[str, list[float]] = {}
    app.state.pairing_failed_attempts: dict[str, list[float]] = {}
    app.state.pairing_lockouts: dict[str, float] = {}
    app.state.session_ingested_seqs: dict[str, set[int]] = {}
    app.state.session_last_seq_acked: dict[str, int] = {}
    app.state.session_trackers: dict[str, EventTracker] = {}

    # Middleware
    app.add_middleware(CorrelationIdMiddleware)

    if config.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.add_middleware(
            OriginEnforcementMiddleware,
            allowed_origins=config.allowed_origins,
            is_public=(config.mode == "public"),
        )

    # Error Handlers adhering strictly to Contract C8
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
        if exc.status_code == 404:
            path = request.url.path
            if not (path.startswith("/api/") or path.startswith("/ws/")):
                sdir = os.environ.get("NADS_STATIC_DIR")
                if not sdir:
                    cdist = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "frontend",
                        "dist",
                    )
                    if os.path.isdir(cdist):
                        sdir = cdist
                if sdir and os.path.isdir(sdir):
                    rel = path.lstrip("/")
                    target = os.path.join(sdir, rel)
                    if rel and os.path.isfile(target):
                        from fastapi.responses import FileResponse

                        return FileResponse(target)
                    idx_p = os.path.join(sdir, "index.html")
                    if os.path.isfile(idx_p):
                        from fastapi.responses import FileResponse

                        return FileResponse(idx_p)

        corr_id = get_correlation_id(request)
        code = "UNAUTHORIZED" if exc.status_code == 401 else f"HTTP_{exc.status_code}"
        payload = ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=str(exc.detail),
                correlation_id=corr_id,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json"),
            headers={"X-Correlation-ID": corr_id},
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> Response:
        detail = exc.detail if isinstance(exc, HTTPException) else "Not Found"
        return await http_exception_handler(request, HTTPException(status_code=404, detail=detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        corr_id = get_correlation_id(request)
        payload = ErrorResponse(
            error=ErrorDetail(
                code="BAD_MESSAGE",
                message="Request validation failed",
                correlation_id=corr_id,
            )
        )
        return JSONResponse(
            status_code=400,
            content=payload.model_dump(mode="json"),
            headers={"X-Correlation-ID": corr_id},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        corr_id = get_correlation_id(request)
        # Log error with correlation ID for server-side diagnosis; never leak trace to client
        logger.error("Unhandled server error [corr_id=%s]: %s", corr_id, exc, exc_info=True)
        payload = ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL",
                message="Internal server error",
                correlation_id=corr_id,
            )
        )
        return JSONResponse(
            status_code=500,
            content=payload.model_dump(mode="json"),
            headers={"X-Correlation-ID": corr_id},
        )

    # Routes
    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        """Public healthcheck reporting service uptime and version without secrets."""
        uptime = max(0.0, time.time() - app.state.start_time)
        return HealthResponse(
            status="ok",
            version="2.0.0",
            uptime_s=round(uptime, 2),
        )

    # Protected route example/smoke-test endpoint
    @app.get("/api/v1/auth-check")
    async def auth_check(_token: str | None = Depends(verify_ingest_token)) -> dict[str, str]:
        return {"status": "authenticated"}

    @app.get("/api/v1/metrics", response_model=MetricsResponse)
    async def get_metrics(session_id: str | None = None) -> MetricsResponse:
        """Report stream latency percentiles, drop counts, sequence gaps, and skew."""
        metrics = get_stream_metrics(session_id)
        return metrics.to_response()

    # WebSocket Ingest Endpoint (T11-011 / Contract C7)
    @app.websocket("/api/v1/ingest")
    async def websocket_ingest(websocket: WebSocket) -> None:
        """Contract C7 phone telemetry ingest WebSocket protocol handler."""
        # 0. Check Origin allow-list if present (T18-006)
        origin = websocket.headers.get("origin")
        host = websocket.headers.get("host")
        xf_host = websocket.headers.get("x-forwarded-host")
        if config.allowed_origins and origin:
            if not is_origin_allowed(origin, config.allowed_origins, host, xf_host):
                await websocket.close(code=4403, reason="Forbidden: Origin not allowed")
                return

        # 1. Authenticate connection if ingest_token is configured or session token provided
        connected_session_id: str | None = None
        auth_header = websocket.headers.get("authorization")
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        if not token:
            token = websocket.query_params.get("token")

        session_tokens = getattr(websocket.app.state, "session_ingest_tokens", {})
        is_valid_session_token = bool(token and token in session_tokens)
        is_valid_global_token = bool(
            config.ingest_token
            and token
            and hmac.compare_digest(token.encode("utf-8"), config.ingest_token.encode("utf-8"))
        )

        if config.ingest_token:
            if not (is_valid_session_token or is_valid_global_token):
                await websocket.close(code=4401, reason="Unauthorized")
                return

        if is_valid_session_token and token:
            connected_session_id = session_tokens.get(token)

        await websocket.accept()

        client_id: str | None = None
        session_id: str | None = None
        device: str | None = None
        store: LiveCaptureStore | None = None
        tracker: EventTracker | None = None
        last_seq_acked = 0
        samples_since_last_ack = 0
        last_ack_time = time.monotonic()

        # Token-bucket rate limiter: max_msgs_per_min (default 120, rate=2/s, burst=120)
        max_rate = float(config.max_msgs_per_min)
        rate_limiter = TokenBucket(rate=max_rate / 60.0, capacity=max_rate)

        try:
            while True:
                try:
                    message_text = await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                except Exception:
                    break

                # Frame size limit: MAX_MESSAGE_BYTES (close with 1009)
                if len(message_text.encode("utf-8")) > MAX_MESSAGE_BYTES:
                    reason_msg = f"Message exceeds {MAX_MESSAGE_BYTES} bytes"
                    await websocket.close(code=1009, reason=reason_msg)
                    break

                # Rate limiting check: return RATE_LIMITED error without closing
                if not rate_limiter.allow():
                    err = ErrorMsg(code="RATE_LIMITED", message="Rate limit exceeded", fatal=False)
                    await websocket.send_text(err.model_dump_json())
                    continue

                try:
                    raw_msg = json.loads(message_text)
                except Exception:
                    err = ErrorMsg(code="BAD_MESSAGE", message="Invalid JSON", fatal=False)
                    await websocket.send_text(err.model_dump_json())
                    continue

                if not isinstance(raw_msg, dict):
                    err = ErrorMsg(
                        code="BAD_MESSAGE",
                        message="Message must be a JSON object",
                        fatal=False,
                    )
                    await websocket.send_text(err.model_dump_json())
                    continue

                msg_type = raw_msg.get("type")
                schema_ver = raw_msg.get("schema_version", 2)
                if schema_ver != 2:
                    err = ErrorMsg(
                        code="VERSION_MISMATCH",
                        message=f"Unsupported schema_version {schema_ver}; expected 2",
                        fatal=True,
                    )
                    await websocket.send_text(err.model_dump_json())
                    await websocket.close(code=4426, reason="Unsupported schema version")
                    break

                if msg_type == "hello":
                    try:
                        hello = IngestHello.model_validate(raw_msg)
                    except Exception as e:
                        err = ErrorMsg(
                            code="BAD_MESSAGE",
                            message=f"Invalid hello message: {e}",
                            fatal=False,
                        )
                        await websocket.send_text(err.model_dump_json())
                        continue

                    # Check for SESSION_CONFLICT (close code 4409)
                    if hello.client_id in app.state.active_ingest_clients:
                        existing_ws = app.state.active_ingest_clients[hello.client_id]
                        if connected_session_id and existing_ws is not websocket:
                            try:
                                await existing_ws.close(code=4409, reason="Superseded by reconnect")
                            except Exception:
                                pass
                            app.state.active_ingest_clients.pop(hello.client_id, None)
                        else:
                            err = ErrorMsg(
                                code="SESSION_CONFLICT",
                                message=(
                                    f"Session conflict: active connection for {hello.client_id}"
                                ),
                                fatal=True,
                            )
                            await websocket.send_text(err.model_dump_json())
                            await websocket.close(code=4409, reason="Session conflict")
                            break

                    client_id = hello.client_id
                    device = hello.device
                    app.state.active_ingest_clients[client_id] = websocket

                    sess_mgr: SessionManager = app.state.session_manager
                    if connected_session_id:
                        req_sid = raw_msg.get("session_id")
                        if req_sid and req_sid != connected_session_id:
                            err = ErrorMsg(
                                code="UNAUTHORIZED",
                                message="Session mismatch: token cannot write to another session",
                                fatal=True,
                            )
                            await websocket.send_text(err.model_dump_json())
                            await websocket.close(code=4401, reason="Session mismatch")
                            break
                        session_id = connected_session_id
                        sess_buf = sess_mgr.get_or_create_session(
                            client_id=client_id,
                            device=device,
                            session_id=connected_session_id,
                        )
                        last_seq_acked = 0
                        reset_stream_metrics(session_id)
                    elif hello.resume_from_seq and hello.resume_from_seq > 0:
                        sess_buf = sess_mgr.get_or_resume_session(
                            client_id=client_id,
                            device=device,
                            resume_from_seq=hello.resume_from_seq,
                        )
                        last_seq_acked = hello.resume_from_seq - 1
                        session_id = sess_buf.session_id
                    else:
                        sess_buf = sess_mgr.start_new_session(client_id, device)
                        last_seq_acked = 0
                        reset_stream_metrics(sess_buf.session_id)
                        session_id = sess_buf.session_id

                    hello_src = getattr(hello, "source", None) or "phone"
                    app.state.session_sources[session_id] = hello_src

                    # Live capture store for telemetry retention
                    if config.retention_enabled:
                        store = LiveCaptureStore(
                            client_id=client_id,
                            session_id=session_id,
                            source=hello_src,
                        )

                    tracker = EventTracker(session_id=session_id, device=device)

                    hello_ack = HelloAck(
                        session_id=session_id,
                        server_time=datetime.now(UTC).isoformat(),
                        last_seq_acked=last_seq_acked,
                        model_version="if_v1",
                        limits=IngestLimits(
                            max_message_bytes=MAX_MESSAGE_BYTES,
                            max_msgs_per_min=config.max_msgs_per_min,
                        ),
                    )
                    await websocket.send_text(hello_ack.model_dump_json())
                    hello_src = getattr(hello, "source", None) or "phone"
                    conn_ev = app.state.connection_tracker.on_connect(
                        client_id=client_id, session_id=session_id, source=hello_src
                    )
                    if app.state.hub is not None:
                        await app.state.hub.broadcast(conn_ev, session_id=session_id)

                elif msg_type == "sample":
                    if connected_session_id:
                        msg_sid = raw_msg.get("session_id")
                        p_data = raw_msg.get("payload")
                        p_sid = p_data.get("session_id") if isinstance(p_data, dict) else None
                        if (msg_sid and msg_sid != connected_session_id) or (
                            p_sid and p_sid != connected_session_id
                        ):
                            err = ErrorMsg(
                                code="UNAUTHORIZED",
                                message="Session mismatch: token cannot write to another session",
                                fatal=True,
                            )
                            await websocket.send_text(err.model_dump_json())
                            await websocket.close(code=4401, reason="Session mismatch")
                            break

                    try:
                        sample = IngestSample.model_validate(raw_msg)
                    except Exception as e:
                        raw_seq = raw_msg.get("seq")
                        safe_seq = (
                            raw_seq
                            if isinstance(raw_seq, int) and not isinstance(raw_seq, bool)
                            else None
                        )
                        err = ErrorMsg(
                            code="BAD_MESSAGE",
                            message=f"Invalid sample message: {e}",
                            fatal=False,
                            seq=safe_seq,
                        )
                        await websocket.send_text(err.model_dump_json())
                        continue

                    cid = client_id or sample.payload.device
                    sess_mgr: SessionManager = app.state.session_manager
                    curr_buf = sess_mgr.get_session(cid)
                    is_already_seen = bool(curr_buf is not None and curr_buf.has_seq(sample.seq))

                    if is_already_seen:
                        if session_id:
                            get_stream_metrics(session_id).record_sample({"seq": sample.seq})
                        re_ack = Ack(seq=sample.seq)
                        await websocket.send_text(re_ack.model_dump_json())
                        continue

                    # Sequence reset check: if client started a new collection run from seq 1
                    # or sequence jumped backwards by at least 5
                    if sample.seq < last_seq_acked:
                        if (last_seq_acked - sample.seq >= 5) or (sample.seq == 1):
                            logger.info(
                                "Sequence reset for session %s: seq %d < last_seq_acked %d",
                                session_id,
                                sample.seq,
                                last_seq_acked,
                            )
                            last_seq_acked = 0

                    # Idempotent re-ack if seq <= last_seq_acked
                    if sample.seq <= last_seq_acked:
                        if session_id:
                            get_stream_metrics(session_id).record_sample({"seq": sample.seq})
                        re_ack = Ack(seq=sample.seq)
                        await websocket.send_text(re_ack.model_dump_json())
                        continue

                    # Enforce seq jump cap to avoid memory/metrics manipulation (T14-002)
                    if sample.seq - last_seq_acked > MAX_SEQ_JUMP:
                        err = ErrorMsg(
                            code="BAD_MESSAGE",
                            message=(
                                f"Sequence jump too large "
                                f"({sample.seq - last_seq_acked} > {MAX_SEQ_JUMP})"
                            ),
                            fatal=False,
                            seq=sample.seq,
                        )
                        await websocket.send_text(err.model_dump_json())
                        continue

                    engine: StreamingEngine | None = app.state.engine
                    if engine is not None:
                        try:
                            scored = engine.process(sample, client_id=cid, session_id=session_id)
                        except SchemaError as e:
                            err = ErrorMsg(
                                code="SCHEMA_ERROR",
                                message=str(e),
                                fatal=False,
                                seq=sample.seq,
                            )
                            await websocket.send_text(err.model_dump_json())
                            continue
                        except Exception as e:
                            logger.error(
                                "Error processing sample seq %d: %s", sample.seq, e, exc_info=True
                            )
                            err = ErrorMsg(
                                code="INTERNAL",
                                message="Internal error processing sample",
                                fatal=False,
                                seq=sample.seq,
                            )
                            await websocket.send_text(err.model_dump_json())
                            continue
                    else:
                        scored = None

                    if session_id:
                        if session_id in app.state.active_live_sessions:
                            app.state.active_live_sessions[session_id]["last_active_at"] = (
                                datetime.now(UTC)
                            )
                        # Store raw sample for C1 CSV export (bounded buffer, T18-005)
                        raw_buf = app.state.session_raw_samples.setdefault(session_id, [])
                        if len(raw_buf) >= SESSION_MAX_ROWS:
                            raw_buf.pop(0)
                        raw_buf.append(sample.payload.model_dump(mode="python"))

                        if scored is not None:
                            app.state.latest_samples[session_id] = scored
                            scored_buf = app.state.session_samples.setdefault(session_id, [])
                            if len(scored_buf) >= SESSION_MAX_ROWS:
                                scored_buf.pop(0)
                            scored_buf.append(scored)
                            get_stream_metrics(session_id).record_sample(scored)

                            # Fan-out live sample to dashboard subscribers
                            if app.state.hub is not None:
                                live_sample_ev = LiveSampleEvent(
                                    server_time=datetime.now(UTC).isoformat(),
                                    session_id=session_id,
                                    sample=scored,
                                )
                                await app.state.hub.broadcast(live_sample_ev, session_id=session_id)
                        else:
                            get_stream_metrics(session_id).record_sample({"seq": sample.seq})

                        conn_ev, _skew_flag = app.state.connection_tracker.on_sample(
                            session_id=session_id,
                            sent_at=sample.sent_at,
                            received_at=datetime.now(UTC),
                        )
                        if conn_ev is not None and app.state.hub is not None:
                            await app.state.hub.broadcast(conn_ev, session_id=session_id)

                    if store is not None:
                        store.append_sample(sample.payload)

                    if tracker is not None and scored is not None:
                        action, evt = tracker.process_sample(scored)
                        if evt is not None and session_id:
                            if session_id not in app.state.session_events:
                                app.state.session_events[session_id] = []
                            app.state.session_events[session_id].append(evt)

                            now_iso = datetime.now(UTC).isoformat()
                            if action == "OPEN" and app.state.hub is not None:
                                ev_msg = LiveEventOpen(
                                    server_time=now_iso, session_id=session_id, event=evt
                                )
                                await app.state.hub.broadcast(ev_msg, session_id=session_id)
                            elif action == "UPDATE" and app.state.hub is not None:
                                ev_msg = LiveEventUpdate(
                                    server_time=now_iso, session_id=session_id, event=evt
                                )
                                await app.state.hub.broadcast(ev_msg, session_id=session_id)
                            elif action == "CLOSED" and app.state.hub is not None:
                                ev_msg = LiveEventClosed(
                                    server_time=now_iso, session_id=session_id, event=evt
                                )
                                await app.state.hub.broadcast(ev_msg, session_id=session_id)

                    last_seq_acked = sample.seq
                    samples_since_last_ack += 1
                    now_m = time.monotonic()

                    # Ack cadence: cumulative ack every 5 samples or 5s
                    if samples_since_last_ack >= 5 or (now_m - last_ack_time) >= 5.0:
                        ack = Ack(seq=last_seq_acked)
                        await websocket.send_text(ack.model_dump_json())
                        samples_since_last_ack = 0
                        last_ack_time = now_m

                elif msg_type == "ping":
                    # Flush pending acks with pong
                    if samples_since_last_ack > 0:
                        ack = Ack(seq=last_seq_acked)
                        await websocket.send_text(ack.model_dump_json())
                        samples_since_last_ack = 0
                        last_ack_time = time.monotonic()
                    pong = Pong(server_time=datetime.now(UTC).isoformat())
                    await websocket.send_text(pong.model_dump_json())

                elif msg_type == "bye":
                    if samples_since_last_ack > 0:
                        ack = Ack(seq=last_seq_acked)
                        await websocket.send_text(ack.model_dump_json())
                    if tracker is not None:
                        tracker.close_session()
                    if store is not None:
                        store.close(status="CLOSED")
                    if session_id:
                        close_ev = app.state.connection_tracker.on_session_close(session_id)
                        if app.state.hub is not None:
                            await app.state.hub.broadcast(close_ev, session_id=session_id)
                    await websocket.close(code=1000, reason="Client bye")
                    break

                else:
                    err = ErrorMsg(
                        code="BAD_MESSAGE",
                        message=f"Unknown message type '{msg_type}'",
                        fatal=False,
                    )
                    await websocket.send_text(err.model_dump_json())

        finally:
            if client_id and client_id in app.state.active_ingest_clients:
                del app.state.active_ingest_clients[client_id]
            if session_id:
                disc_ev = app.state.connection_tracker.on_disconnect(client_id, session_id)
                if app.state.hub is not None:
                    await app.state.hub.broadcast(disc_ev, session_id=session_id)
            if store is not None and not store.is_closed:
                store.close(status="INCOMPLETE")

    # --------------------------------------------------------------------------
    # HTTP Batch Ingest Endpoint (T15-001)
    # --------------------------------------------------------------------------
    @app.post("/api/v1/ingest/batch", response_model=BatchIngestResponse)
    async def http_batch_ingest(
        request: Request,
        authorization: str | None = Header(default=None),
        token: str | None = Query(default=None),
    ) -> BatchIngestResponse:
        """HTTP batch telemetry ingest fallback accepting an array of C7 sample objects.

        Implements:
        1. Authentication matching WebSocket ingest (ingest token or per-session token).
        2. Strict Contract C7 schema validation on each sample.
        3. Guardrail G19 deduplication: duplicate sequence numbers are ignored.
        4. Rate limiting enforcement against operational limits.
        """
        # 0. Check Origin allow-list if present (T18-006)
        origin = request.headers.get("origin")
        if config.allowed_origins and origin:
            if origin not in config.allowed_origins:
                raise HTTPException(status_code=403, detail="Forbidden: Origin not allowed")

        # 1. Authentication: global ingest_token or per-session token
        auth_token = None
        if authorization and authorization.startswith("Bearer "):
            auth_token = authorization.split(" ", 1)[1].strip()
        if not auth_token:
            auth_token = token or request.query_params.get("token")

        session_tokens = getattr(request.app.state, "session_ingest_tokens", {})
        is_valid_session_token = bool(auth_token and auth_token in session_tokens)
        is_valid_global_token = bool(
            config.ingest_token
            and auth_token
            and hmac.compare_digest(auth_token.encode("utf-8"), config.ingest_token.encode("utf-8"))
        )

        if config.ingest_token:
            if not (is_valid_session_token or is_valid_global_token):
                raise HTTPException(status_code=401, detail="Unauthorized")

        connected_session_id = (
            session_tokens.get(auth_token) if is_valid_session_token and auth_token else None
        )

        # 2. Extract sample array (accepts either list of samples or {"samples": [...]})
        try:
            body = await request.json()
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail="Batch payload must be valid JSON",
            ) from e

        if isinstance(body, list):
            sample_list = body
        elif isinstance(body, dict):
            sample_list = body.get("samples")
            if not isinstance(sample_list, list):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Batch payload must be a JSON array of sample objects "
                        "or contain a 'samples' array"
                    ),
                )
        else:
            raise HTTPException(
                status_code=422,
                detail="Batch payload must be a JSON array of sample objects",
            )

        # 3. Rate limiting check (T15-001)
        max_rate = float(config.max_msgs_per_min)
        if len(sample_list) > max_rate:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: batch size {len(sample_list)} exceeds maximum "
                    f"{int(max_rate)} messages per batch"
                ),
            )

        # 4. Strict Validation of each sample adhering to Contract C7
        validated_samples: list[IngestSample] = []
        for idx, item in enumerate(sample_list):
            if not isinstance(item, dict):
                raise HTTPException(
                    status_code=422,
                    detail=f"Sample at index {idx} must be a JSON object",
                )
            schema_ver = item.get("schema_version", 2)
            if schema_ver != 2:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported schema_version {schema_ver} at index {idx}; expected 2",
                )
            msg_type = item.get("type")
            if msg_type != "sample":
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid message type '{msg_type}' at index {idx}; expected 'sample'",
                )
            try:
                sample_obj = IngestSample.model_validate(item)
            except Exception as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Validation error for sample at index {idx}: {e}",
                ) from e
            validated_samples.append(sample_obj)

        if not validated_samples:
            return BatchIngestResponse(
                accepted=0,
                duplicates=0,
                last_seq_acked=0,
                session_id=connected_session_id,
            )

        # 5. Resolve session
        session_id = connected_session_id
        if not session_id:
            req_sid = request.headers.get("x-session-id") or request.query_params.get("session_id")
            if req_sid:
                session_id = req_sid
            else:
                first_dev = validated_samples[0].payload.device
                sess_mgr: SessionManager = app.state.session_manager
                sess_buf = sess_mgr.get_or_create_session(client_id=first_dev, device=first_dev)
                session_id = sess_buf.session_id

        # 6. Process samples with deduplication (Guardrail G19)
        accepted = 0
        duplicates = 0
        seen_seqs = app.state.session_ingested_seqs.setdefault(session_id, set())
        last_seq_acked = app.state.session_last_seq_acked.get(session_id, 0)

        engine: StreamingEngine | None = app.state.engine

        for sample in validated_samples:
            if sample.seq in seen_seqs:
                duplicates += 1
                # Duplicates ignored without crashing or corrupting metrics (G19)
                continue

            seen_seqs.add(sample.seq)
            accepted += 1
            if sample.seq > last_seq_acked:
                last_seq_acked = sample.seq

            # Process through inference engine if available
            scored = None
            if engine is not None:
                try:
                    cid = sample.payload.device
                    scored = engine.process(sample, client_id=cid)
                except Exception as e:
                    logger.error("Error processing batch sample seq %d: %s", sample.seq, e)

            # Raw and scored session buffering (bounded to SESSION_MAX_ROWS)
            raw_buf = app.state.session_raw_samples.setdefault(session_id, [])
            if len(raw_buf) >= SESSION_MAX_ROWS:
                raw_buf.pop(0)
            raw_buf.append(sample.payload.model_dump(mode="python"))

            if scored is not None:
                app.state.latest_samples[session_id] = scored
                scored_buf = app.state.session_samples.setdefault(session_id, [])
                if len(scored_buf) >= SESSION_MAX_ROWS:
                    scored_buf.pop(0)
                scored_buf.append(scored)
                get_stream_metrics(session_id).record_sample(scored)

                # Fan-out to live dashboard subscribers
                now_iso = datetime.now(UTC).isoformat()
                if app.state.hub is not None:
                    await app.state.hub.broadcast(
                        LiveSampleEvent(
                            server_time=now_iso,
                            session_id=session_id,
                            sample=scored,
                        ),
                        session_id=session_id,
                    )

                # Event tracker evaluation
                tracker = app.state.session_trackers.setdefault(
                    session_id, EventTracker(session_id=session_id, device=sample.payload.device)
                )
                action, evt = tracker.process_sample(scored)
                if evt is not None:
                    ev_records = app.state.session_events.setdefault(session_id, [])
                    ev_records.append(evt)
                    if app.state.hub is not None:
                        if action == "OPEN":
                            await app.state.hub.broadcast(
                                LiveEventOpen(
                                    server_time=now_iso, session_id=session_id, event=evt
                                ),
                                session_id=session_id,
                            )
                        elif action == "CLOSED":
                            await app.state.hub.broadcast(
                                LiveEventClosed(
                                    server_time=now_iso, session_id=session_id, event=evt
                                ),
                                session_id=session_id,
                            )
                        elif action == "UPDATE":
                            await app.state.hub.broadcast(
                                LiveEventUpdate(
                                    server_time=now_iso, session_id=session_id, event=evt
                                ),
                                session_id=session_id,
                            )

        app.state.session_last_seq_acked[session_id] = last_seq_acked

        return BatchIngestResponse(
            accepted=accepted,
            duplicates=duplicates,
            last_seq_acked=last_seq_acked,
            session_id=session_id,
        )

    # --------------------------------------------------------------------------
    # REST Endpoints (T11-014 / Contract C8)
    # --------------------------------------------------------------------------

    def verify_loopback_access(request: Request) -> None:
        """Enforce loopback-only access unless NADS_ALLOW_REMOTE_VIEW is enabled."""
        if not config.allow_remote_view:
            client_host = request.client.host if request.client else "127.0.0.1"
            if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: Remote access disabled; loopback only",
                )

    @app.get("/api/v1/sessions", response_model=SessionListResponse)
    async def get_sessions(
        request: Request,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ) -> SessionListResponse:
        """List active and historical streaming sessions."""
        verify_loopback_access(request)
        sess_mgr: SessionManager = app.state.session_manager
        summaries: list[SessionSummary] = []
        for _cid, buf in sess_mgr._active_sessions.items():
            evts = app.state.session_events.get(buf.session_id, [])
            status = "CLOSED" if buf.is_closed else "OPEN"
            src = app.state.session_sources.get(buf.session_id, "phone")
            summaries.append(
                SessionSummary(
                    session_id=buf.session_id,
                    source=src,
                    status=status,
                    sample_count=len(buf),
                    event_count=len(evts),
                    start_time=None,
                    end_time=None,
                )
            )
        total = len(summaries)
        paginated = summaries[offset : offset + limit]
        return SessionListResponse(sessions=paginated, total=total)

    @app.get("/api/v1/sessions/{session_id}/samples", response_model=SamplesResponse)
    async def get_session_samples(
        session_id: str,
        request: Request,
        since_seq: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> SamplesResponse:
        """Retrieve paginated scored samples for a given session."""
        verify_loopback_access(request)
        all_samples = app.state.session_samples.get(session_id, [])
        filtered = [s for s in all_samples if s.seq > since_seq]
        paginated = filtered[:limit]
        has_more = len(filtered) > limit
        return SamplesResponse(samples=paginated, total=len(all_samples), has_more=has_more)

    @app.get("/api/v1/sessions/{session_id}/events", response_model=EventsResponse)
    async def get_session_events(
        session_id: str,
        request: Request,
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> EventsResponse:
        """Retrieve diagnosed anomaly events for a given session."""
        verify_loopback_access(request)
        evts = app.state.session_events.get(session_id, [])
        return EventsResponse(events=evts[:limit], total=len(evts))

    @app.get("/api/v1/alerts", response_model=list[AlertRecord])
    async def get_alerts(
        request: Request,
        since: str | None = None,
        ack: bool | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ) -> list[AlertRecord]:
        """List alerts with optional acknowledgment and timestamp filter (C8/C9)."""
        verify_loopback_access(request)
        alerts_file = DATA_DIR / "live" / "alerts.jsonl"
        if alerts_file.exists():
            for line in alerts_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        rec = deserialize_alert_jsonl(line)
                        app.state.alerts[rec.alert_id] = rec
                    except Exception:
                        pass

        result = list(app.state.alerts.values())
        if ack is not None:
            result = [a for a in result if (a.acknowledged_at is not None) == ack]
        if since is not None:
            result = [a for a in result if a.created_at >= since]
        return result[offset : offset + limit]

    @app.post("/api/v1/alerts/{alert_id}/ack", response_model=AlertRecord)
    async def ack_alert(alert_id: str, request: Request) -> AlertRecord:
        """Mark an alert as acknowledged (idempotent, Contract C8/C9, T13-007)."""
        verify_loopback_access(request)

        # Rate limiting: 60 ack requests per minute per IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        now_ts = time.time()
        recent = [t for t in app.state.alert_ack_attempts.get(client_ip, []) if t > now_ts - 60.0]
        if len(recent) >= 60:
            raise HTTPException(
                status_code=429,
                detail="Alert acknowledgement rate limit exceeded",
            )
        recent.append(now_ts)
        app.state.alert_ack_attempts[client_ip] = recent

        # Find alert in memory or in alerts.jsonl
        if alert_id not in app.state.alerts:
            alerts_file = DATA_DIR / "live" / "alerts.jsonl"
            if alerts_file.exists():
                for line in alerts_file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        try:
                            rec = deserialize_alert_jsonl(line)
                            app.state.alerts[rec.alert_id] = rec
                        except Exception:
                            pass

        if alert_id not in app.state.alerts:
            raise HTTPException(
                status_code=404,
                detail=f"Alert '{alert_id}' not found",
            )

        alert = app.state.alerts[alert_id]

        # Idempotent: second ack returns 200 without appending a second record
        if alert.acknowledged_at is not None:
            return alert

        now_iso = datetime.now(UTC).isoformat()
        alert.acknowledged_at = now_iso

        # Append ack record to alerts.jsonl
        alerts_file = DATA_DIR / "live" / "alerts.jsonl"
        alerts_file.parent.mkdir(parents=True, exist_ok=True)
        with alerts_file.open("a", encoding="utf-8") as f:
            f.write(serialize_alert_jsonl(alert))

        # Publish alert update over LiveHub
        if app.state.hub is not None:
            alert_ev = {
                "type": "alert",
                "schema_version": 2,
                "server_time": now_iso,
                "session_id": alert.session_id,
                "alert": alert.model_dump(mode="json"),
            }
            await app.state.hub.broadcast(alert_ev, session_id=alert.session_id)

        return alert

    @app.get("/api/v1/model", response_model=ModelInfoResponse)
    async def get_model_info(request: Request) -> ModelInfoResponse:
        """Retrieve active ML model version, features, and detection thresholds."""
        verify_loopback_access(request)
        return ModelInfoResponse(
            model_version="if_v1",
            feature_columns=["ss_rsrp", "ss_rsrq", "ss_sinr"],
            feature_hash="hash-12345",
            thresholds={"if_threshold": 0.6},
        )

    # --------------------------------------------------------------------------
    # Contract C10: Hosted Pairing & Ephemeral Session Lifecycle API (T18-002)
    # --------------------------------------------------------------------------

    def verify_viewer_auth(request: Request, session_id: str) -> None:
        """Check HttpOnly viewer cookie or bearer auth for session access (Contract C10)."""
        cookie_session = request.cookies.get("nads_viewer_session")
        if cookie_session == session_id:
            return
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if config.ingest_token and hmac.compare_digest(
                token.encode("utf-8"), config.ingest_token.encode("utf-8")
            ):
                return
            session_tokens = getattr(request.app.state, "session_ingest_tokens", {})
            if session_tokens.get(token) == session_id or token == session_id:
                return
        raise HTTPException(status_code=401, detail="Unauthorized viewer")

    @app.post("/api/v1/live-sessions", response_model=CreateLiveSessionResponse)
    async def create_live_session(
        request: Request, response: Response
    ) -> CreateLiveSessionResponse:
        """Initialize an ephemeral live session and return an 8-char pairing code (C10)."""
        reap_idle_sessions(app)
        if len(app.state.active_live_sessions) >= config.max_live_sessions:
            raise HTTPException(
                status_code=429,
                detail=f"Maximum live sessions ({config.max_live_sessions}) reached",
            )

        client_ip = request.client.host if request.client else "127.0.0.1"
        now_ts = time.time()
        window = config.session_creation_window_seconds
        creations = [
            t for t in app.state.ip_session_creations.get(client_ip, []) if t > now_ts - window
        ]
        if len(creations) >= config.max_session_creations_per_ip:
            raise HTTPException(
                status_code=429,
                detail="Session creation rate limit exceeded",
            )
        creations.append(now_ts)
        app.state.ip_session_creations[client_ip] = creations

        session_id = f"live-{uuid.uuid4().hex[:12]}"
        pairing_code = "".join(
            secrets.choice(PAIRING_CODE_ALPHABET) for _ in range(PAIRING_CODE_LENGTH)
        )
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=PAIRING_CODE_TTL_SECONDS)
        expires_at_iso = expires_at.isoformat()

        session_meta = {
            "session_id": session_id,
            "pairing_code": pairing_code,
            "created_at": now,
            "last_active_at": now,
            "expires_at": expires_at,
            "used": False,
            "client_id": None,
            "ingest_token": None,
        }
        app.state.pairing_sessions[pairing_code] = session_meta
        app.state.active_live_sessions[session_id] = session_meta

        # Set HttpOnly viewer cookie scoped to session_id
        response.set_cookie(
            key="nads_viewer_session",
            value=session_id,
            httponly=True,
            samesite="lax",
            max_age=PAIRING_CODE_TTL_SECONDS * 6,
            secure=False,
            path="/",
        )
        return CreateLiveSessionResponse(
            session_id=session_id,
            pairing_code=pairing_code,
            expires_at=expires_at_iso,
        )

    @app.post("/api/v1/pair", response_model=PairResponse)
    async def pair_device(payload: PairRequest, request: Request) -> PairResponse:
        """Pair phone device using 8-character single-use pairing code (C10)."""
        client_ip = request.client.host if request.client else "127.0.0.1"
        now_ts = time.time()

        # Check brute-force lockout
        lockout_until = app.state.pairing_lockouts.get(client_ip, 0.0)
        if now_ts < lockout_until:
            rem = int(lockout_until - now_ts)
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed pairing attempts. Locked out for {rem} seconds",
            )

        code = payload.pairing_code.strip().upper()
        meta = app.state.pairing_sessions.get(code)
        now_dt = datetime.now(UTC)

        if meta is None or meta.get("used", False) or now_dt > meta["expires_at"]:
            recent = [
                t
                for t in app.state.pairing_failed_attempts.get(client_ip, [])
                if t > now_ts - config.pairing_lockout_seconds
            ]
            recent.append(now_ts)
            app.state.pairing_failed_attempts[client_ip] = recent

            if len(recent) >= config.pairing_lockout_attempts:
                app.state.pairing_lockouts[client_ip] = now_ts + config.pairing_lockout_seconds
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Too many failed pairing attempts. "
                        f"Locked out for {config.pairing_lockout_seconds} seconds"
                    ),
                )

            if meta is None:
                raise HTTPException(status_code=404, detail="Pairing code not found")
            if meta.get("used", False):
                raise HTTPException(status_code=409, detail="Pairing code already used")
            raise HTTPException(status_code=400, detail="Pairing code expired")

        app.state.pairing_failed_attempts.pop(client_ip, None)
        meta["used"] = True
        meta["client_id"] = payload.client_id
        meta["last_active_at"] = now_dt
        session_id = meta["session_id"]

        # Close any previous connection for this client so it does not SESSION_CONFLICT
        if payload.client_id and payload.client_id in app.state.active_ingest_clients:
            old_ws = app.state.active_ingest_clients.pop(payload.client_id, None)
            if old_ws is not None:
                try:
                    await old_ws.close(code=4409, reason="Superseded by new pairing")
                except Exception:
                    pass

        ingest_token = secrets.token_urlsafe(32)
        meta["ingest_token"] = ingest_token
        app.state.session_ingest_tokens[ingest_token] = session_id

        return PairResponse(
            session_id=session_id,
            ingest_token=ingest_token,
            ws_url="/api/v1/ingest",
            limits=IngestLimits(),
        )

    @app.post(
        "/api/v1/live-sessions/{session_id}/ticket",
        response_model=LiveSessionTicketResponse,
    )
    async def get_live_session_ticket(
        session_id: str, request: Request
    ) -> LiveSessionTicketResponse:
        """Generate single-use WebSocket ticket (30s TTL) for viewer browser (C10)."""
        verify_viewer_auth(request, session_id)
        if session_id not in app.state.active_live_sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        meta = app.state.active_live_sessions[session_id]
        meta["last_active_at"] = datetime.now(UTC)

        ticket = secrets.token_urlsafe(24)
        expires_at = datetime.now(UTC) + timedelta(seconds=TICKET_TTL_SECONDS)
        app.state.live_session_tickets[ticket] = (session_id, expires_at)

        return LiveSessionTicketResponse(
            ticket=ticket,
            expires_at=expires_at.isoformat(),
        )

    @app.delete(
        "/api/v1/live-sessions/{session_id}",
        response_model=DeleteLiveSessionResponse,
    )
    async def delete_live_session(
        session_id: str, request: Request, response: Response
    ) -> DeleteLiveSessionResponse:
        """Teardown session and purge all in-memory telemetry immediately (G29/C10)."""
        verify_viewer_auth(request, session_id)
        meta = app.state.active_live_sessions.pop(session_id, None)
        if meta is not None:
            code = meta.get("pairing_code")
            if code and code in app.state.pairing_sessions:
                del app.state.pairing_sessions[code]
            token = meta.get("ingest_token")
            if token and token in app.state.session_ingest_tokens:
                del app.state.session_ingest_tokens[token]
            cid = meta.get("client_id")
            if cid:
                app.state.session_manager.close_session(cid)
                if cid in app.state.active_ingest_clients:
                    old_ws = app.state.active_ingest_clients.pop(cid, None)
                    if old_ws is not None:
                        try:
                            await old_ws.close(code=1000, reason="Live session ended")
                        except Exception:
                            pass

        # Purge any tickets
        tickets_to_del = [
            t for t, (sid, _) in app.state.live_session_tickets.items() if sid == session_id
        ]
        for t in tickets_to_del:
            del app.state.live_session_tickets[t]

        # Purge in-memory telemetry (G29)
        app.state.session_samples.pop(session_id, None)
        app.state.session_raw_samples.pop(session_id, None)
        app.state.session_events.pop(session_id, None)
        app.state.latest_samples.pop(session_id, None)

        response.delete_cookie(key="nads_viewer_session", path="/")
        return DeleteLiveSessionResponse(status="deleted", session_id=session_id)

    @app.get("/api/v1/live-sessions/{session_id}/export.csv")
    async def export_live_session_csv(session_id: str, request: Request) -> Response:
        """Export in-memory session telemetry as C1 CSV with viewer auth (T18-005/G29)."""
        verify_viewer_auth(request, session_id)
        if session_id not in app.state.active_live_sessions:
            raise HTTPException(status_code=404, detail="Live session not found")

        raw_samples = app.state.session_raw_samples.get(session_id)
        if raw_samples is None:
            raw_samples = app.state.session_samples.get(session_id, [])

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(RAW_COLUMNS)

        for s in raw_samples:
            data = s if isinstance(s, dict) else s.model_dump(mode="python")
            row = []
            for col in RAW_COLUMNS:
                val = data.get(col)
                if val is None:
                    row.append("")
                elif isinstance(val, bool):
                    row.append("True" if val else "False")
                else:
                    row.append(str(val))
            writer.writerow(row)

        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="live_{session_id}.csv"',
            },
        )

    # --------------------------------------------------------------------------
    # WebSocket /api/v1/live Endpoint (T11-014 / Contract C8)
    # --------------------------------------------------------------------------

    @app.websocket("/api/v1/live")
    async def websocket_live(websocket: WebSocket) -> None:
        """Live dashboard fan-out WebSocket streaming snapshot, samples, and events (C8)."""
        # Origin allow-list check (T18-006)
        origin = websocket.headers.get("origin")
        host = websocket.headers.get("host")
        xf_host = websocket.headers.get("x-forwarded-host")
        if config.allowed_origins:
            if not is_origin_allowed(origin, config.allowed_origins, host, xf_host):
                logger.warning(
                    "websocket_live rejected origin %r (host=%r, xf_host=%r, allowed=%r)",
                    origin,
                    host,
                    xf_host,
                    config.allowed_origins,
                )
                await websocket.close(code=4403, reason="Forbidden: Origin not allowed")
                return

        if not config.allow_remote_view:
            client_host = websocket.client.host if websocket.client else "127.0.0.1"
            if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
                logger.warning("websocket_live rejected non-loopback host %r", client_host)
                await websocket.close(code=4403, reason="Forbidden: Loopback only")
                return

        await websocket.accept()

        auth_session_id: str | None = None
        if config.require_live_auth or config.mode == "public":
            try:
                auth_frame_text = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            except TimeoutError:
                await websocket.close(
                    code=4401, reason="Auth timeout: first-frame ticket required within 5s"
                )
                return
            except WebSocketDisconnect:
                return

            try:
                frame_dict = json.loads(auth_frame_text)
            except Exception:
                await websocket.close(code=4401, reason="Unauthorized: Malformed auth frame")
                return

            if not isinstance(frame_dict, dict) or frame_dict.get("type") != "auth":
                await websocket.close(
                    code=4401, reason="Unauthorized: First frame must have type 'auth'"
                )
                return

            ticket_str = frame_dict.get("ticket")
            if not ticket_str or not isinstance(ticket_str, str):
                await websocket.close(code=4401, reason="Unauthorized: Missing ticket")
                return

            # Single-use pop
            ticket_record = app.state.live_session_tickets.pop(ticket_str, None)
            if ticket_record is None:
                await websocket.close(code=4401, reason="Unauthorized: Invalid or reused ticket")
                return

            sess_id, exp_dt = ticket_record
            if datetime.now(UTC) > exp_dt:
                await websocket.close(code=4401, reason="Unauthorized: Expired ticket")
                return

            auth_session_id = sess_id

        sub_id, queue = await app.state.hub.subscribe()

        try:
            active_cids = list(app.state.active_ingest_clients.keys())
            latest_sess_id = None
            if active_cids:
                cid = active_cids[-1]
                latest_sess_id = getattr(
                    app.state.connection_tracker, "_client_to_session", {}
                ).get(cid)
                if not latest_sess_id:
                    sess_buf = app.state.session_manager.get_session(cid)
                    if sess_buf:
                        latest_sess_id = sess_buf.session_id
            if not latest_sess_id and app.state.active_live_sessions:
                latest_sess_id = list(app.state.active_live_sessions.keys())[-1]

            target_sess_id = auth_session_id or latest_sess_id
            latest_sample = app.state.latest_samples.get(target_sess_id) if target_sess_id else None
            open_events = [
                e
                for e in app.state.session_events.get(target_sess_id, [])
                if getattr(e, "status", "") == "PROVISIONAL"
            ]

            cur_state, _ = app.state.connection_tracker.get_state(target_sess_id)
            now_iso = datetime.now(UTC).isoformat()
            snapshot = SnapshotEvent(
                server_time=now_iso,
                session_id=target_sess_id or "default",
                latest_sample=latest_sample,
                state=cur_state,
                open_events=open_events,
                last_alerts=app.state.alerts[-5:] if app.state.alerts else [],
            )
            await websocket.send_text(snapshot.model_dump_json())

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                    if auth_session_id:
                        msg_sid = (
                            getattr(msg, "session_id", None)
                            if isinstance(msg, BaseModel)
                            else msg.get("session_id")
                            if isinstance(msg, dict)
                            else None
                        )
                        if msg_sid is not None and msg_sid != auth_session_id:
                            continue
                    if isinstance(msg, BaseModel):
                        await websocket.send_text(msg.model_dump_json())
                    elif isinstance(msg, dict):
                        await websocket.send_text(json.dumps(msg))
                    else:
                        await websocket.send_text(str(msg))
                except TimeoutError:
                    stale_events = app.state.connection_tracker.check_stale()
                    for st_ev in stale_events:
                        if app.state.hub is not None:
                            await app.state.hub.broadcast(st_ev, session_id=st_ev.session_id)
                    hb = HeartbeatEvent(
                        server_time=datetime.now(UTC).isoformat(),
                        session_id=latest_sess_id,
                    )
                    try:
                        await websocket.send_text(hb.model_dump_json())
                    except Exception:
                        break
                except WebSocketDisconnect:
                    break
                except Exception:
                    break
        finally:
            await app.state.hub.unsubscribe(sub_id)

    # Mount SPA static files if static assets directory exists (T18-007)
    static_dir = os.environ.get("NADS_STATIC_DIR")
    if not static_dir:
        default_dist = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "frontend",
            "dist",
        )
        if os.path.isdir(default_dist):
            static_dir = default_dist

    if static_dir and os.path.isdir(static_dir):
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        index_file = os.path.join(static_dir, "index.html")

        assets_dir = os.path.join(static_dir, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        data_dir_static = os.path.join(static_dir, "data")
        if os.path.isdir(data_dir_static):
            app.mount("/data", StaticFiles(directory=data_dir_static), name="data")

        if os.path.isfile(index_file):

            @app.get("/", include_in_schema=False)
            async def serve_index() -> Response:
                return FileResponse(index_file)

    return app


def parse_server_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI options for the streaming server with documentation for every flag."""
    parser = argparse.ArgumentParser(
        description="5G-NADS Streaming Ingest and Telemetry Server.",
        prog="python -m streaming.server",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("NADS_HOST", "127.0.0.1").strip(),
        help="Host address to bind the streaming server (default: 127.0.0.1 or NADS_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("NADS_PORT", "8000")),
        help="Port to bind the streaming server (default: 8000 or NADS_PORT)",
    )
    parser.add_argument(
        "--allow-lan",
        action="store_true",
        default=os.environ.get("NADS_ALLOW_LAN", "false").lower() in ("1", "true", "yes"),
        help="Allow binding to LAN/external interfaces; requires a non-empty ingest token",
    )
    parser.add_argument(
        "--allow-remote-view",
        action="store_true",
        default=os.environ.get("NADS_ALLOW_REMOTE_VIEW", "false").lower() in ("1", "true", "yes"),
        help="Allow remote viewers to access read/live endpoints without loopback restriction",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("NADS_INGEST_TOKEN", "").strip() or None,
        help="Bearer authentication token for phone telemetry ingest",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=os.environ.get("NADS_MODE", "local").strip().lower(),
        choices=["local", "public"],
        help="Server deployment mode: 'local' (development) or 'public' (cloud deployment)",
    )
    parser.add_argument(
        "--allowed-origins",
        type=str,
        default=os.environ.get("NADS_ALLOWED_ORIGINS", "").strip(),
        help="Comma-separated list of allowed CORS origins (required in public mode)",
    )
    parser.add_argument(
        "--retention",
        type=str,
        default=None,
        help=(
            "Enable live telemetry capture to disk ('true' or 'false', "
            "default: true in local, false in public)"
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """CLI entry point for running the streaming server with bind policy enforcement."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        ns = parse_server_args(args)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2

    # Enforce bind policy: non-loopback requires --allow-lan and non-empty token
    is_loopback = ns.host in ("127.0.0.1", "localhost", "::1")
    if not is_loopback:
        if not ns.allow_lan:
            sys.stderr.write(
                f"Error: Non-loopback host '{ns.host}' requires --allow-lan flag.\n"
                "Fix: pass --allow-lan to enable non-loopback binding, or bind to 127.0.0.1.\n"
            )
            return 2
        if not ns.token:
            sys.stderr.write(
                f"Error: Non-loopback host '{ns.host}' requires a non-empty NADS_INGEST_TOKEN.\n"
                "Fix: set NADS_INGEST_TOKEN=<token> or pass --token=<token>.\n"
            )
            return 2

    raw_origins = [o.strip() for o in ns.allowed_origins.split(",") if o.strip()]
    if ns.retention is not None:
        retention_enabled = ns.retention.lower() in ("1", "true", "yes")
    elif ns.mode == "public":
        retention_enabled = False
    else:
        retention_enabled = True

    config = ServerConfig(
        host=ns.host,
        port=ns.port,
        ingest_token=ns.token,
        allow_lan=ns.allow_lan,
        allow_remote_view=ns.allow_remote_view,
        mode=ns.mode,
        allowed_origins=raw_origins,
        retention_enabled=retention_enabled,
    )

    try:
        config.validate()
    except ConfigError as e:
        sys.stderr.write(f"Configuration error: {e}\n")
        return 2

    app = create_app(config)
    import uvicorn

    uvicorn.run(app, host=config.host, port=config.port, log_level=ns.log_level.lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())

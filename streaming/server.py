"""FastAPI application factory, auth dependencies, and route definitions.

Provides the HTTP and WebSocket endpoints for phone telemetry ingest,
viewer live-stream push, health inspection, and REST administration
following the Contracts C7 and C8 specifications.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import secrets
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
    MAX_MESSAGE_BYTES,
    MAX_SEQ_JUMP,
    PAIRING_CODE_ALPHABET,
    PAIRING_CODE_LENGTH,
    PAIRING_CODE_TTL_SECONDS,
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

        config = cls(
            host=os.environ.get("NADS_HOST", "127.0.0.1").strip(),
            port=port,
            ingest_token=token,
            allow_lan=allow_lan,
            allow_remote_view=allow_remote,
            mode=mode,
            allowed_origins=origins,
            retention_enabled=retention_enabled,
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
    app.state.session_events: dict[str, list[EventRecord]] = {}
    app.state.alerts: list[dict[str, Any]] = []
    app.state.pairing_sessions: dict[str, dict[str, Any]] = {}
    app.state.active_live_sessions: dict[str, dict[str, Any]] = {}
    app.state.session_ingest_tokens: dict[str, str] = {}
    app.state.live_session_tickets: dict[str, tuple[str, datetime]] = {}

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

    # Error Handlers adhering strictly to Contract C8
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
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
        # 1. Authenticate connection if ingest_token is configured
        if config.ingest_token:
            auth_header = websocket.headers.get("authorization")
            token = None
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1].strip()
            if not token:
                token = websocket.query_params.get("token")

            session_tokens = getattr(websocket.app.state, "session_ingest_tokens", {})
            is_valid_session_token = bool(token and token in session_tokens)
            is_valid_global_token = bool(
                token
                and hmac.compare_digest(token.encode("utf-8"), config.ingest_token.encode("utf-8"))
            )

            if not (is_valid_session_token or is_valid_global_token):
                await websocket.close(code=4401, reason="Unauthorized")
                return

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
                        err = ErrorMsg(
                            code="SESSION_CONFLICT",
                            message=f"Session conflict: active connection for {hello.client_id}",
                            fatal=True,
                        )
                        await websocket.send_text(err.model_dump_json())
                        await websocket.close(code=4409, reason="Session conflict")
                        break

                    client_id = hello.client_id
                    device = hello.device
                    app.state.active_ingest_clients[client_id] = websocket

                    sess_mgr: SessionManager = app.state.session_manager
                    if hello.resume_from_seq and hello.resume_from_seq > 0:
                        sess_buf = sess_mgr.get_or_resume_session(
                            client_id=client_id,
                            device=device,
                            resume_from_seq=hello.resume_from_seq,
                        )
                        last_seq_acked = hello.resume_from_seq - 1
                    else:
                        sess_buf = sess_mgr.start_new_session(client_id, device)
                        last_seq_acked = 0
                        reset_stream_metrics(sess_buf.session_id)

                    session_id = sess_buf.session_id

                    # Live capture store for telemetry retention
                    if config.retention_enabled:
                        store = LiveCaptureStore(
                            client_id=client_id,
                            session_id=session_id,
                            source="phone",
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

                    cid = client_id or sample.payload.device

                    engine: StreamingEngine | None = app.state.engine
                    if engine is not None:
                        try:
                            scored = engine.process(sample, client_id=cid)
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
                        if scored is not None:
                            app.state.latest_samples[session_id] = scored
                            if session_id not in app.state.session_samples:
                                app.state.session_samples[session_id] = []
                            app.state.session_samples[session_id].append(scored)
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
            summaries.append(
                SessionSummary(
                    session_id=buf.session_id,
                    source="phone",
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

    @app.get("/api/v1/alerts")
    async def get_alerts(
        request: Request,
        ack: bool | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        """List alerts with optional acknowledgment filter."""
        verify_loopback_access(request)
        alerts = list(app.state.alerts)
        if ack is not None:
            alerts = [a for a in alerts if a.get("acknowledged", False) == ack]
        return alerts[:limit]

    @app.post("/api/v1/alerts/{alert_id}/ack")
    async def ack_alert(alert_id: str, request: Request) -> dict[str, Any]:
        """Mark an alert as acknowledged (idempotent)."""
        verify_loopback_access(request)
        for a in app.state.alerts:
            if a.get("alert_id") == alert_id:
                a["acknowledged"] = True
                return {"status": "acknowledged", "alert_id": alert_id}
        return {"status": "acknowledged", "alert_id": alert_id}

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
    async def create_live_session(response: Response) -> CreateLiveSessionResponse:
        """Initialize an ephemeral live session and return an 8-char pairing code (C10)."""
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
    async def pair_device(payload: PairRequest) -> PairResponse:
        """Pair phone device using 8-character single-use pairing code (C10)."""
        code = payload.pairing_code.strip().upper()
        meta = app.state.pairing_sessions.get(code)
        if meta is None:
            raise HTTPException(status_code=404, detail="Pairing code not found")

        if meta.get("used", False):
            raise HTTPException(status_code=409, detail="Pairing code already used")

        if datetime.now(UTC) > meta["expires_at"]:
            raise HTTPException(status_code=400, detail="Pairing code expired")

        meta["used"] = True
        meta["client_id"] = payload.client_id
        session_id = meta["session_id"]

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

        # Purge any tickets
        tickets_to_del = [
            t for t, (sid, _) in app.state.live_session_tickets.items() if sid == session_id
        ]
        for t in tickets_to_del:
            del app.state.live_session_tickets[t]

        # Purge in-memory telemetry (G29)
        app.state.session_samples.pop(session_id, None)
        app.state.session_events.pop(session_id, None)

        response.delete_cookie(key="nads_viewer_session", path="/")
        return DeleteLiveSessionResponse(status="deleted", session_id=session_id)

    # --------------------------------------------------------------------------
    # WebSocket /api/v1/live Endpoint (T11-014 / Contract C8)
    # --------------------------------------------------------------------------

    @app.websocket("/api/v1/live")
    async def websocket_live(websocket: WebSocket) -> None:
        """Live dashboard fan-out WebSocket streaming snapshot, samples, and events (C8)."""
        if not config.allow_remote_view:
            client_host = websocket.client.host if websocket.client else "127.0.0.1"
            if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
                await websocket.close(code=4403, reason="Forbidden: Loopback only")
                return

        await websocket.accept()
        sub_id, queue = await app.state.hub.subscribe()

        try:
            active_cids = list(app.state.active_ingest_clients.keys())
            latest_sess_id = None
            if active_cids:
                sess_buf = app.state.session_manager.get_session(active_cids[-1])
                if sess_buf:
                    latest_sess_id = sess_buf.session_id

            latest_sample = app.state.latest_samples.get(latest_sess_id) if latest_sess_id else None
            open_events = [
                e
                for e in app.state.session_events.get(latest_sess_id, [])
                if getattr(e, "status", "") == "PROVISIONAL"
            ]

            cur_state, _ = app.state.connection_tracker.get_state(latest_sess_id)
            now_iso = datetime.now(UTC).isoformat()
            snapshot = SnapshotEvent(
                server_time=now_iso,
                session_id=latest_sess_id or "default",
                latest_sample=latest_sample,
                state=cur_state,
                open_events=open_events,
                last_alerts=app.state.alerts[-5:] if app.state.alerts else [],
            )
            await websocket.send_text(snapshot.model_dump_json())

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=5.0)
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
                    await websocket.send_text(hb.model_dump_json())
                except WebSocketDisconnect:
                    break
                except Exception:
                    break
        finally:
            await app.state.hub.unsubscribe(sub_id)

    return app

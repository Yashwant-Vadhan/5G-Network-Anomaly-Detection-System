"""FastAPI application factory, auth dependencies, and route definitions.

Provides the HTTP and WebSocket endpoints for phone telemetry ingest,
viewer live-stream push, health inspection, and REST administration
following the Contracts C7 and C8 specifications.
"""

from __future__ import annotations

import hmac
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ml.schema import ConfigError
from streaming.metrics import get_stream_metrics
from streaming.schema import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
)

logger = logging.getLogger("streaming.server")


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

    # hmac.compare_digest prevents timing side-channel attacks
    if not hmac.compare_digest(provided_token.encode("utf-8"), expected_token.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid token")

    return provided_token


def create_app(config: ServerConfig | None = None) -> FastAPI:
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

    return app

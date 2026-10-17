"""Tests for outbound webhook channel (T13-004, Guardrail G26).

Acceptance Criteria:
- Payload equals the minimal subset (G26): title, body, severity, anomaly_type,
  event_status, created_at; no cell IDs, device IDs, raw metrics.
- Timeout recorded as FAILED, pipeline / dispatcher unaffected.
- URL absent from all emitted logs.
- Off unless NADS_ALERT_WEBHOOK_URL is set or explicitly configured.
- Dry-run outputs payload to stdout without sending HTTP requests.
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

import httpx

from streaming.alerts.channels.webhook import WebhookChannel
from streaming.alerts.dispatcher import AlertDispatcher
from streaming.schema import AlertRecord


def _make_dummy_alert(alert_id: str = "alt-webhook-01") -> AlertRecord:
    """Helper creating a valid AlertRecord for testing webhook payloads."""
    return AlertRecord(
        alert_id=alert_id,
        created_at="2026-10-17T15:30:00+00:00",
        event_id="evt-100",
        session_id="sess-wh-1",
        source="phone",
        kind="NEW",
        severity="HIGH",
        anomaly_type="SIGNAL_DEGRADATION",
        event_status="PROVISIONAL",
        title="Signal Degradation Alert",
        body="RSRP dropped sharply below -115 dBm on cell 4501",
        evidence=["ss_rsrp < -115 dBm", "cell_id: 4501"],
        recommendation={"action": "reorient"},
        policy={"tier": "HIGH"},
    )


def test_webhook_payload_equals_minimal_subset_g26() -> None:
    """Payload sent to webhook equals minimal subset (G26), omitting cell IDs and raw data."""
    alert = _make_dummy_alert()
    payload = alert.to_webhook_body(include_evidence=False)

    # Must contain exactly the 6 minimal fields
    expected_keys = {
        "title",
        "body",
        "severity",
        "anomaly_type",
        "event_status",
        "created_at",
    }
    assert set(payload.keys()) == expected_keys

    # Must NOT contain evidence, cell identifiers, or session IDs
    assert "evidence" not in payload
    assert "cell_id" not in payload
    assert "session_id" not in payload
    assert "recommendation" not in payload
    assert "policy" not in payload


def test_webhook_skipped_when_url_not_configured(monkeypatch: Any) -> None:
    """When NADS_ALERT_WEBHOOK_URL is unset, channel skips delivery gracefully."""
    monkeypatch.delenv("NADS_ALERT_WEBHOOK_URL", raising=False)
    channel = WebhookChannel(webhook_url=None)
    alert = _make_dummy_alert()

    async def _run() -> None:
        delivery = await channel.send(alert)
        assert delivery.channel == "webhook"
        assert delivery.status == "SKIPPED"
        assert "not configured" in (delivery.detail or "")

    asyncio.run(_run())


def test_webhook_dry_run_prints_payload_to_stdout(capsys: Any) -> None:
    """Dry-run mode prints minimal payload to stdout without sending HTTP request."""
    channel = WebhookChannel(
        webhook_url="https://hooks.example.com/sensitive-path-xyz",
        dry_run=True,
    )
    alert = _make_dummy_alert()

    async def _run() -> None:
        delivery = await channel.send(alert)
        assert delivery.channel == "webhook"
        assert delivery.status == "OK"
        assert delivery.detail == "dry-run"

    asyncio.run(_run())

    captured = capsys.readouterr()
    assert "[DRY-RUN WEBHOOK PAYLOAD]" in captured.out
    assert "Signal Degradation Alert" in captured.out
    # Raw evidence should not be in stdout payload
    assert "cell_id: 4501" not in captured.out


def test_webhook_timeout_recorded_as_failed_and_pipeline_unaffected(
    monkeypatch: Any,
) -> None:
    """Timeout during webhook POST is recorded as FAILED without crashing dispatcher."""
    secret_url = "https://hooks.internal.corp/secret-hook-key-8899"

    async def _mock_post(*args: Any, **kwargs: Any) -> Any:
        raise httpx.TimeoutException("Connection timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    channel = WebhookChannel(
        webhook_url=secret_url,
        timeout_seconds=0.1,
        max_retries=1,
    )
    dispatcher = AlertDispatcher(channels=[channel])
    alert = _make_dummy_alert()

    async def _run() -> None:
        # Dispatch must complete cleanly without raising
        result = await dispatcher.dispatch(alert)
        assert len(result.delivery) == 1
        d = result.delivery[0]
        assert d.channel == "webhook"
        assert d.status == "FAILED"
        assert "Timed out" in (d.detail or "")

    asyncio.run(_run())


def test_webhook_url_absent_from_all_logs(monkeypatch: Any) -> None:
    """The webhook URL is confidential and must never leak into log messages."""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)

    webhook_logger = logging.getLogger("streaming.alerts.channels.webhook")
    webhook_logger.addHandler(handler)
    webhook_logger.setLevel(logging.DEBUG)

    secret_url = "https://hooks.slack.com/services/T00/B00/ULTRA_SECRET_TOKEN_999"

    # Simulate server 500 error from webhook endpoint
    async def _mock_error_post(*args: Any, **kwargs: Any) -> httpx.Response:
        req = httpx.Request("POST", secret_url)
        return httpx.Response(status_code=500, request=req)

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_error_post)

    channel = WebhookChannel(
        webhook_url=secret_url,
        timeout_seconds=0.1,
        max_retries=1,
    )
    alert = _make_dummy_alert()

    try:
        async def _run() -> None:
            delivery = await channel.send(alert)
            assert delivery.status == "FAILED"
            assert "HTTP 500" in (delivery.detail or "")

        asyncio.run(_run())

        emitted_logs = log_capture.getvalue()
        # Verify secret URL and its components are completely absent from logs
        assert secret_url not in emitted_logs
        assert "ULTRA_SECRET_TOKEN_999" not in emitted_logs
        assert "services/T00/B00" not in emitted_logs
    finally:
        webhook_logger.removeHandler(handler)

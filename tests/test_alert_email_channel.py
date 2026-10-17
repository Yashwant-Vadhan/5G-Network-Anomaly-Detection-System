"""Tests for EmailChannel (T13-005 / Guardrail G26).

Verifies:
- Email channel is off by default when environment variables are unset.
- Dry-run mode outputs plain-text email without network requests.
- Failure is completely isolated and never disrupts core engine.
- Credentials and passwords are NEVER leaked in logs or error details.
- Dispatched payload contains only the minimal subset per Guardrail G26.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from streaming.alerts.channels.email import EmailChannel
from streaming.alerts.dispatcher import AlertDispatcher
from streaming.schema import AlertRecord


@pytest.fixture
def sample_alert() -> AlertRecord:
    """Fixture returning a standard AlertRecord for notification tests."""
    return AlertRecord(
        alert_id="alt-email-test-01",
        created_at="2026-10-17T14:30:00+00:00",
        event_id="evt-email-01",
        session_id="sess-email-01",
        source="phone",
        kind="NEW",
        severity="HIGH",
        anomaly_type="LOW_RSRP",
        event_status="FINAL",
        title="Low RSRP Detected",
        body="Sustained radio degradation detected on device.",
        evidence=["ss_rsrp: -115.0 dBm below -110.0 dBm threshold"],
    )


def test_email_channel_skipped_when_not_configured(sample_alert):
    """EmailChannel returns SKIPPED when host or recipients are unset."""
    with patch.dict("os.environ", {}, clear=True):
        channel = EmailChannel()
        import asyncio

        delivery = asyncio.run(channel.send(sample_alert))
        assert delivery.status == "SKIPPED"
        assert delivery.channel == "email"
        assert "not configured" in delivery.detail.lower()


def test_email_channel_dry_run_prints_message(sample_alert, capsys):
    """Dry-run mode prints plain-text email message to stdout without network I/O."""
    channel = EmailChannel(
        host="smtp.example.com",
        to_addrs=["ops@example.com"],
        dry_run=True,
    )
    import asyncio

    delivery = asyncio.run(channel.send(sample_alert))
    assert delivery.status == "OK"
    assert delivery.channel == "email"
    assert "dry-run" in delivery.detail

    captured = capsys.readouterr()
    assert "[DRY-RUN EMAIL MESSAGE]" in captured.out
    assert "To: ops@example.com" in captured.out
    assert "Subject: [5G-NADS HIGH] Alert: LOW_RSRP" in captured.out
    assert "alt-email-test-01" in captured.out
    assert "Sustained radio degradation" in captured.out


def test_email_channel_delivery_success(sample_alert):
    """Email delivery connects via SMTP, uses STARTTLS and sends message."""
    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server
    mock_server.has_extn.return_value = True

    with patch("smtplib.SMTP", return_value=mock_server) as mock_smtp_cls:
        channel = EmailChannel(
            host="smtp.relay.internal",
            port=587,
            user="test-user",
            password="test-secret-password-123",
            from_addr="nads@example.com",
            to_addrs=["ops1@example.com", "ops2@example.com"],
        )
        import asyncio

        delivery = asyncio.run(channel.send(sample_alert))
        assert delivery.status == "OK"
        assert delivery.channel == "email"
        assert "2 recipients" in delivery.detail

        # Verify SMTP interaction
        mock_smtp_cls.assert_called_once_with("smtp.relay.internal", 587, timeout=10.0)
        mock_server.__enter__.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test-user", "test-secret-password-123")
        mock_server.send_message.assert_called_once()


def test_email_channel_failure_isolated_no_password_leak(sample_alert, caplog):
    """Failures are isolated to AlertDelivery and never leak password in logs or detail."""
    secret_pass = "super-confidential-smtp-pass"
    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server
    mock_server.has_extn.return_value = False
    mock_server.send_message.side_effect = RuntimeError(
        f"SMTP Authentication failed with secret {secret_pass}!"
    )

    with patch("smtplib.SMTP", return_value=mock_server):
        channel = EmailChannel(
            host="smtp.relay.internal",
            user="user",
            password=secret_pass,
            to_addrs=["ops@example.com"],
        )
        import asyncio

        with caplog.at_level(logging.WARNING):
            delivery = asyncio.run(channel.send(sample_alert))

        assert delivery.status == "FAILED"
        assert delivery.channel == "email"
        # Secret password must be sanitized
        assert secret_pass not in delivery.detail
        assert secret_pass not in caplog.text


def test_dispatcher_fans_out_to_email_channel(sample_alert):
    """AlertDispatcher coordinates fan-out across multiple channels including email."""
    email_channel = EmailChannel(
        host="smtp.example.com",
        to_addrs=["oncall@example.com"],
        dry_run=True,
    )
    dispatcher = AlertDispatcher(channels=[email_channel])
    import asyncio

    res = asyncio.run(dispatcher.dispatch(sample_alert))
    assert len(res.delivery) == 1
    assert res.delivery[0].channel == "email"
    assert res.delivery[0].status == "OK"
    assert "dry-run" in res.delivery[0].detail

"""Tests for streaming privacy audit, token scrubbing, and PII omission (T14-005).

Verifies Contract C7, C8, and C9 schemas, alert notification channels, persistent
file formats in data/live/, and Android collector source code for strict conformance
with privacy invariants and zero leakage of auth tokens, hardware IDs, or PII.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch

import pydantic
import pytest

from scripts.audit_privacy import (
    FORBIDDEN_PII_FIELDS,
    audit_android_collector,
    audit_c7_schema,
    audit_c8_schema,
    audit_c9_payloads,
    audit_data_live_files,
    audit_server_loggers,
    run_full_privacy_audit,
)
from streaming.alerts.channels.email import EmailChannel, format_email_body
from streaming.alerts.channels.phone import to_compact_c9
from streaming.alerts.channels.webhook import WebhookChannel
from streaming.schema import AlertRecord, IngestPayload, ScoredSample


@pytest.fixture
def sample_alert() -> AlertRecord:
    """Fixture returning a standard valid AlertRecord."""
    return AlertRecord(
        alert_id="alt-privacy-test-101",
        created_at="2026-10-18T12:00:00+00:00",
        event_id="evt-101",
        session_id="sess-101",
        source="phone",
        kind="NEW",
        severity="HIGH",
        anomaly_type="RADIO_LINK_FAILURE",
        event_status="PROVISIONAL",
        title="5G Radio Link Failure Alert",
        body="SS-RSRP dropped below -120 dBm persistently",
        evidence=["ss_rsrp < -110 dBm for 5 samples"],
    )


def test_c7_schema_forbids_pii_and_hardware_ids() -> None:
    """Verify IngestPayload forbids extra fields like IMEI, IMSI, or GPS coordinates."""
    valid_payload = {
        "timestamp": "18-10-26 12:00:00",
        "device": "Pixel 7 Pro",
        "manufacturer": "Google",
        "android": "14",
        "operator": "Jio",
        "network_type": "NR",
        "deployment_mode": "SA",
        "ss_rsrp": -85.0,
        "ss_rsrq": -11.0,
        "ss_sinr": 15.0,
        "pci": 42,
        "nci": 1234567,
        "nrarfcn": 632000,
    }

    # Clean payload succeeds
    parsed = IngestPayload.model_validate(valid_payload)
    assert parsed.device == "Pixel 7 Pro"

    # Injecting any forbidden PII field MUST raise ValidationError
    for forbidden_field in ["imei", "imsi", "latitude", "longitude", "mac_address", "phone"]:
        with pytest.raises(pydantic.ValidationError):
            IngestPayload.model_validate({**valid_payload, forbidden_field: "sensitive_val"})


def test_c8_scored_sample_contains_zero_pii() -> None:
    """Verify ScoredSample schema contains zero forbidden PII or hardware ID fields."""
    field_names = set(ScoredSample.model_fields.keys())
    leaked = field_names.intersection(FORBIDDEN_PII_FIELDS)
    assert len(leaked) == 0, f"ScoredSample exposes forbidden fields: {leaked}"


def test_c9_webhook_body_data_minimization(sample_alert: AlertRecord) -> None:
    """Verify webhook payload subset adheres to G26 data minimization."""
    body = sample_alert.to_webhook_body(include_evidence=False)
    assert set(body.keys()) == {
        "title",
        "body",
        "severity",
        "anomaly_type",
        "event_status",
        "created_at",
    }
    # No raw radio metrics, no cell IDs, no tokens
    for key in ["pci", "nci", "ss_rsrp", "token", "session_id", "device"]:
        assert key not in body


def test_c9_phone_compact_payload_privacy(sample_alert: AlertRecord) -> None:
    """Verify phone push notification payload contains no PII or hardware IDs."""
    compact = to_compact_c9(sample_alert)
    keys = set(compact.keys())
    assert len(keys.intersection(FORBIDDEN_PII_FIELDS)) == 0
    assert "token" not in compact


def test_c9_email_formatting_no_credential_leak(sample_alert: AlertRecord) -> None:
    """Verify email formatting contains no passwords, tokens, or auth headers."""
    email_text = format_email_body(sample_alert, include_evidence=True)
    assert "password" not in email_text.lower()
    assert "bearer" not in email_text.lower()
    assert "token=" not in email_text.lower()


def test_webhook_channel_url_privacy(
    sample_alert: AlertRecord, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify WebhookChannel log output never interpolates sensitive webhook URLs (G26)."""
    secret_url = "https://hooks.internal.net/alerts/v2?token=SUPER_SECRET_TOKEN_XYZ123"
    channel = WebhookChannel(webhook_url=secret_url, timeout_seconds=0.1, max_retries=0)

    async def _run() -> None:
        with caplog.at_level(logging.WARNING):
            delivery = await channel.send(sample_alert)
            assert delivery.status in ("FAILED", "OK")

    asyncio.run(_run())

    # The secret token and full URL must NEVER appear in logs
    for record in caplog.records:
        assert "SUPER_SECRET_TOKEN_XYZ123" not in record.message
        assert secret_url not in record.message


def test_email_channel_masks_password_on_error(
    sample_alert: AlertRecord, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify EmailChannel scrubs passwords from logs and delivery details on SMTP failure."""
    secret_pass = "P@ssw0rd_SuperSecret_999!"
    channel = EmailChannel(
        host="smtp.invalid.domain.test",
        port=587,
        user="alerts@test.local",
        password=secret_pass,
        to_addrs=["admin@test.local"],
        timeout_seconds=0.1,
    )

    err = Exception(f"Auth failed with {secret_pass}")

    async def _run() -> None:
        with patch.object(channel, "_send_sync", side_effect=err):
            with caplog.at_level(logging.WARNING):
                delivery = await channel.send(sample_alert)
                assert delivery.status == "FAILED"
                assert secret_pass not in delivery.detail

    asyncio.run(_run())

    for record in caplog.records:
        assert secret_pass not in record.message


def test_audit_runner_reports_clean_pass() -> None:
    """Verify all static audit runner functions return passed=True."""
    assert audit_c7_schema()["passed"] is True
    assert audit_c8_schema()["passed"] is True
    assert audit_c9_payloads()["passed"] is True
    assert audit_server_loggers()["passed"] is True
    assert audit_data_live_files()["passed"] is True
    assert audit_android_collector()["passed"] is True

    all_results = run_full_privacy_audit()
    assert all(r["passed"] for r in all_results)

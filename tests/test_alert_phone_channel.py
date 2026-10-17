"""Tests for Phone notification channel (T13-006 / Contract C7 / Contract C9).

Verifies:
- Delivery status is recorded in AlertDelivery.
- Pushes compact C7 AlertPush JSON payload over the active WebSocket connection.
- No message is sent to other connected sessions/clients.
- LOW severity alerts are not pushed by default (status=SKIPPED).
- Disconnected phone clients return status=SKIPPED without queueing.
- Socket transmission exceptions are isolated and return status=FAILED.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from streaming.alerts.channels.phone import PhoneChannel, to_compact_c9
from streaming.alerts.dispatcher import AlertDispatcher
from streaming.schema import AlertPush, AlertRecord


@pytest.fixture
def sample_alert() -> AlertRecord:
    """Standard AlertRecord fixture for phone channel tests."""
    return AlertRecord(
        alert_id="alt-phone-001",
        created_at="2026-10-17T15:00:00+00:00",
        event_id="evt-phone-001",
        session_id="sess-alpha",
        source="phone",
        kind="NEW",
        severity="HIGH",
        anomaly_type="LOW_RSRP",
        event_status="FINAL",
        title="High Degradation Alert",
        body="RSRP dropped below -115 dBm for 6 consecutive seconds.",
        evidence=["ss_rsrp: -116.0 dBm"],
    )


@pytest.fixture
def low_alert() -> AlertRecord:
    """Low severity AlertRecord fixture."""
    return AlertRecord(
        alert_id="alt-phone-low",
        created_at="2026-10-17T15:00:00+00:00",
        event_id="evt-phone-low",
        session_id="sess-alpha",
        source="phone",
        kind="NEW",
        severity="LOW",
        anomaly_type="MODERATE_JITTER",
        event_status="PROVISIONAL",
        title="Moderate Jitter",
        body="Minor packet jitter observed.",
    )


def test_compact_c9_payload_structure(sample_alert):
    """to_compact_c9 converts AlertRecord into minimal phone notification dictionary."""
    compact = to_compact_c9(sample_alert)
    assert compact["alert_id"] == "alt-phone-001"
    assert compact["session_id"] == "sess-alpha"
    assert compact["severity"] == "HIGH"
    assert compact["anomaly_type"] == "LOW_RSRP"
    assert compact["title"] == "High Degradation Alert"
    assert "evidence" not in compact  # evidence excluded from phone compact push


def test_phone_channel_delivery_success(sample_alert):
    """PhoneChannel delivers C7 AlertPush JSON to the active session connection."""
    mock_ws = AsyncMock()
    connections = {"sess-alpha": mock_ws}
    channel = PhoneChannel(active_connections=connections)

    delivery = asyncio.run(channel.send(sample_alert))

    assert delivery.status == "OK"
    assert delivery.channel == "phone"
    assert "sess-alpha" in delivery.detail

    mock_ws.send_text.assert_called_once()
    sent_text = mock_ws.send_text.call_args[0][0]
    data = json.loads(sent_text)

    # Validate against C7 AlertPush schema
    parsed_push = AlertPush.model_validate(data)
    assert parsed_push.type == "alert"
    assert parsed_push.schema_version == 2
    assert parsed_push.alert["alert_id"] == "alt-phone-001"
    assert parsed_push.alert["severity"] == "HIGH"


def test_phone_channel_no_message_sent_to_other_clients(sample_alert):
    """Only the target session connection receives the alert; other clients are untouched."""
    mock_ws_target = AsyncMock()
    mock_ws_other1 = AsyncMock()
    mock_ws_other2 = AsyncMock()

    connections = {
        "sess-alpha": mock_ws_target,
        "sess-beta": mock_ws_other1,
        "sess-gamma": mock_ws_other2,
    }
    channel = PhoneChannel(active_connections=connections)

    delivery = asyncio.run(channel.send(sample_alert))

    assert delivery.status == "OK"
    mock_ws_target.send_text.assert_called_once()
    mock_ws_other1.send_text.assert_not_called()
    mock_ws_other2.send_text.assert_not_called()


def test_phone_channel_low_severity_suppressed_by_default(low_alert):
    """LOW severity alerts are suppressed by default and record status=SKIPPED."""
    mock_ws = AsyncMock()
    connections = {"sess-alpha": mock_ws}
    channel = PhoneChannel(active_connections=connections, allow_low_severity=False)

    delivery = asyncio.run(channel.send(low_alert))

    assert delivery.status == "SKIPPED"
    assert delivery.channel == "phone"
    assert "Low severity" in delivery.detail
    mock_ws.send_text.assert_not_called()


def test_phone_channel_low_severity_pushed_when_allowed(low_alert):
    """LOW severity alerts are delivered when allow_low_severity=True."""
    mock_ws = AsyncMock()
    connections = {"sess-alpha": mock_ws}
    channel = PhoneChannel(active_connections=connections, allow_low_severity=True)

    delivery = asyncio.run(channel.send(low_alert))

    assert delivery.status == "OK"
    mock_ws.send_text.assert_called_once()


def test_phone_channel_disconnected_client_returns_skipped(sample_alert):
    """Disconnected phone clients return SKIPPED without queuing or error."""
    # Active connections is empty; target session is disconnected
    channel = PhoneChannel(active_connections={})

    delivery = asyncio.run(channel.send(sample_alert))

    assert delivery.status == "SKIPPED"
    assert delivery.channel == "phone"
    assert "disconnected" in delivery.detail


def test_phone_channel_connection_resolver_callable(sample_alert):
    """Connection can be dynamically resolved via custom resolver callable."""
    mock_ws = AsyncMock()
    resolver = MagicMock(return_value=mock_ws)

    channel = PhoneChannel(connection_resolver=resolver)
    delivery = asyncio.run(channel.send(sample_alert))

    assert delivery.status == "OK"
    resolver.assert_called_once_with("sess-alpha")
    mock_ws.send_text.assert_called_once()


def test_phone_channel_transmission_failure_isolated(sample_alert):
    """WebSocket transmission errors are isolated and return status=FAILED."""
    mock_ws = AsyncMock()
    mock_ws.send_text.side_effect = RuntimeError("Broken pipe / socket aborted")

    channel = PhoneChannel(active_connections={"sess-alpha": mock_ws})
    delivery = asyncio.run(channel.send(sample_alert))

    assert delivery.status == "FAILED"
    assert delivery.channel == "phone"
    assert "Broken pipe" in delivery.detail


def test_dispatcher_fans_out_to_phone_channel(sample_alert):
    """AlertDispatcher coordinates phone channel alongside other channels."""
    mock_ws = AsyncMock()
    phone_ch = PhoneChannel(active_connections={"sess-alpha": mock_ws})
    dispatcher = AlertDispatcher(channels=[phone_ch])

    alert_res = asyncio.run(dispatcher.dispatch(sample_alert))

    assert len(alert_res.delivery) == 1
    assert alert_res.delivery[0].channel == "phone"
    assert alert_res.delivery[0].status == "OK"
    mock_ws.send_text.assert_called_once()

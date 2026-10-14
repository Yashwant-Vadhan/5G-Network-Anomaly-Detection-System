"""Unit tests for Contract C7 models in streaming/schema.py (T10-005)."""

import pytest
from pydantic import TypeAdapter, ValidationError

from streaming.schema import (
    SCHEMA_VERSION,
    Ack,
    AlertPush,
    ClientMessage,
    ErrorMsg,
    HelloAck,
    IngestBye,
    IngestHello,
    IngestPayload,
    IngestPing,
    IngestSample,
    Pong,
)


def test_schema_version_constant_exported():
    assert SCHEMA_VERSION == 2


def test_golden_valid_sample_with_real_collector_timestamp():
    # Real collector row from data/raw/5G_measurements_Samsung_Indoor-Movement.csv
    # 01-10-26 18:26:32,SM-A156E,samsung,16,airtel,LTE,NSA,NR_NSA,FALSE,-97,-12,3,NA,NA,NA,861,0,629952
    sample_json = {
        "type": "sample",
        "schema_version": 2,
        "seq": 119,
        "sent_at": "2026-10-01T18:26:32.412+05:30",
        "payload": {
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
            "csi_rsrp": "NA",
            "csi_rsrq": "NA",
            "csi_sinr": "NA",
            "pci": 861,
            "nci": 0,
            "nrarfcn": 629952,
        },
        "edge": {
            "if_score": 0.42,
            "model_version": "if_v1",
            "feature_hash": "abc123hash",
        },
        "extra_top_level_field": "should_be_ignored",
    }

    adapter = TypeAdapter(ClientMessage)
    msg = adapter.validate_python(sample_json)
    assert isinstance(msg, IngestSample)
    assert msg.seq == 119
    assert msg.payload.timestamp == "01-10-26 18:26:32"
    assert msg.payload.csi_rsrp is None  # 'NA' coerced to None
    assert msg.payload.ss_rsrp == -97.0
    assert msg.edge is not None
    assert msg.edge.if_score == 0.42

    # Round trip test
    dumped = msg.model_dump(mode="json")
    reloaded = adapter.validate_python(dumped)
    assert reloaded == msg


def test_unknown_fields_in_payload_rejected():
    payload_data = {
        "timestamp": "28-09-26 22:42:06",
        "device": "Redmi 13 5G",
        "manufacturer": "Xiaomi",
        "android": "14",
        "operator": "Airtel",
        "network_type": "5G NR",
        "unknown_measurement_column": 123.4,  # forbidden
    }
    with pytest.raises(ValidationError) as exc_info:
        IngestPayload.model_validate(payload_data)
    assert "unknown_measurement_column" in str(exc_info.value)


def test_unknown_top_level_fields_ignored():
    hello_json = {
        "type": "hello",
        "schema_version": 2,
        "client_id": "b1e2c3d4-test-uuid",
        "session_label": "redmi-walk-01",
        "device": "Redmi 13 5G",
        "manufacturer": "Xiaomi",
        "android": "14",
        "operator": "Airtel",
        "app_version": "1.3.0",
        "unrecognized_future_field": "allowed_and_ignored",
    }
    hello = IngestHello.model_validate(hello_json)
    assert hello.client_id == "b1e2c3d4-test-uuid"
    assert not hasattr(hello, "unrecognized_future_field")


def test_negative_seq_rejected():
    sample_json = {
        "type": "sample",
        "schema_version": 2,
        "seq": -5,
        "sent_at": "2026-10-09T10:15:03.412+05:30",
        "payload": {
            "timestamp": "28-09-26 22:42:06",
            "device": "Redmi",
            "manufacturer": "Xiaomi",
            "android": "14",
            "operator": "Airtel",
            "network_type": "5G NR",
        },
    }
    with pytest.raises(ValidationError):
        IngestSample.model_validate(sample_json)


def test_sent_at_without_tz_rejected():
    sample_json = {
        "type": "sample",
        "schema_version": 2,
        "seq": 10,
        "sent_at": "2026-10-09T10:15:03",  # Missing timezone offset!
        "payload": {
            "timestamp": "28-09-26 22:42:06",
            "device": "Redmi",
            "manufacturer": "Xiaomi",
            "android": "14",
            "operator": "Airtel",
            "network_type": "5G NR",
        },
    }
    with pytest.raises(ValidationError) as exc_info:
        IngestSample.model_validate(sample_json)
    assert "timezone offset" in str(exc_info.value)


def test_unknown_message_type_rejected():
    bad_msg = {
        "type": "unsupported_type",
        "schema_version": 2,
    }
    adapter = TypeAdapter(ClientMessage)
    with pytest.raises(ValidationError):
        adapter.validate_python(bad_msg)


def test_server_messages_round_trip():
    hello_ack = HelloAck(
        session_id="session-001",
        server_time="2026-10-09T10:15:04+05:30",
        last_seq_acked=100,
    )
    assert hello_ack.type == "hello_ack"
    assert hello_ack.limits.max_message_bytes == 8192

    ack = Ack(seq=105)
    assert ack.type == "ack"
    assert ack.seq == 105

    err = ErrorMsg(code="BAD_MESSAGE", message="Payload invalid", fatal=False)
    assert err.type == "error"
    assert not err.fatal

    pong = Pong(server_time="2026-10-09T10:15:05+05:30")
    assert pong.type == "pong"

    alert = AlertPush(alert={"title": "Test Alert", "severity": "HIGH"})
    assert alert.type == "alert"

    bye = IngestBye(reason="battery_low")
    assert bye.type == "bye"
    assert bye.reason == "battery_low"

    ping = IngestPing(queue_depth=5, dropped_from_queue=0)
    assert ping.type == "ping"
    assert ping.queue_depth == 5

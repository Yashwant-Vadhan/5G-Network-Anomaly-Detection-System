"""Fuzz-style hardening and property tests for streaming ingest (T14-002).

Validates:
1. seq jump cap enforcement (> MAX_SEQ_JUMP returns BAD_MESSAGE).
2. Robustness against 1,000 randomized/fuzzed payloads with wrong dtypes,
   malformed structures, huge strings, and unknown types without unhandled exceptions.
"""

from __future__ import annotations

import json
import random
import string
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ml.config import MAX_SEQ_JUMP
from streaming.schema import SCHEMA_VERSION
from streaming.server import ServerConfig, create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_valid_hello(client_id: str = "fuzz-device-1") -> dict[str, Any]:
    """Return a baseline valid IngestHello message."""
    return {
        "type": "hello",
        "schema_version": SCHEMA_VERSION,
        "client_id": client_id,
        "session_label": "fuzz-session",
        "device": "Pixel 7 Pro",
        "manufacturer": "Google",
        "android": "14",
        "operator": "Jio",
        "app_version": "2.0.0",
        "resume_from_seq": 0,
        "queue_depth": 0,
        "dropped_from_queue": 0,
    }


def make_valid_sample(seq: int = 1) -> dict[str, Any]:
    """Return a baseline valid IngestSample message."""
    return {
        "type": "sample",
        "schema_version": SCHEMA_VERSION,
        "seq": seq,
        "sent_at": "2026-10-17T15:30:00.000+05:30",
        "payload": {
            "timestamp": "17-10-26 15:30:00",
            "device": "Pixel 7 Pro",
            "manufacturer": "Google",
            "android": "14",
            "operator": "Jio",
            "network_type": "5G NR",
            "deployment_mode": "UNKNOWN",
            "display_override": None,
            "registered": True,
            "ss_rsrp": -95.0,
            "ss_rsrq": -10.0,
            "ss_sinr": 12.0,
            "csi_rsrp": None,
            "csi_rsrq": None,
            "csi_sinr": None,
            "pci": 312,
            "nci": 12345678,
            "nrarfcn": 631392,
        },
    }


def test_seq_jump_cap_enforced() -> None:
    """Extreme sequence jumps exceeding MAX_SEQ_JUMP are rejected with BAD_MESSAGE."""
    app = create_app(ServerConfig(retention_enabled=False))
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ingest") as ws:
        # Hello handshake
        ws.send_json(make_valid_hello(client_id="seq-cap-test"))
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"

        # Baseline: send 5 samples to trigger cumulative ack at seq=5
        for s in range(1, 6):
            ws.send_json(make_valid_sample(seq=s))
        cum_ack = ws.receive_json()
        assert cum_ack["type"] == "ack"
        assert cum_ack["seq"] == 5

        # Attempt extreme jump exceeding MAX_SEQ_JUMP (e.g. 5 + 100_001 = 100_006)
        extreme_seq = 5 + MAX_SEQ_JUMP + 1
        bad_sample = make_valid_sample(seq=extreme_seq)
        ws.send_json(bad_sample)

        err_resp = ws.receive_json()
        assert err_resp["type"] == "error"
        assert err_resp["code"] == "BAD_MESSAGE"
        assert "Sequence jump too large" in err_resp["message"]
        assert err_resp["fatal"] is False

        # Verify server state is unaffected - idempotent re-ack still functions
        ws.send_json(make_valid_sample(seq=3))
        re_ack = ws.receive_json()
        assert re_ack["type"] == "ack"
        assert re_ack["seq"] == 3


def generate_fuzz_message(seq: int, rng: random.Random) -> dict[str, Any] | list[Any] | str:
    """Generate a malformed or boundary fuzzed message to test server robustness."""
    strategy = rng.choice(
        [
            "unknown_type",
            "wrong_dtypes",
            "invalid_json_syntax",
            "non_dict_json",
            "forbidden_extra_fields",
            "missing_required_fields",
            "huge_field_strings",
            "invalid_datetime_tz",
            "extreme_seq_jump",
        ]
    )

    if strategy == "unknown_type":
        bad_type = rng.choice(["unknown_action", "null", 12345, True, "DROP_TABLE", ""])
        return {"type": bad_type, "schema_version": 2, "seq": seq}

    if strategy == "wrong_dtypes":
        sample = make_valid_sample(seq=seq)
        sample["seq"] = rng.choice(["not_an_int", [1, 2], {"seq": 1}, "invalid_num"])
        return sample

    if strategy == "invalid_json_syntax":
        broken_prefixes = ["{", "{'type':", '{"type": "sample"', "INVALID_JSON"]
        return rng.choice(broken_prefixes)

    if strategy == "non_dict_json":
        return rng.choice([[1, 2, 3], "plain_string", 42, False])

    if strategy == "forbidden_extra_fields":
        sample = make_valid_sample(seq=seq)
        # IngestPayload has model_config extra="forbid"
        sample["payload"]["injected_forbidden_col"] = "unexpected_data"
        return sample

    if strategy == "missing_required_fields":
        sample = make_valid_sample(seq=seq)
        key_to_pop = rng.choice(["device", "network_type", "timestamp", "operator"])
        sample["payload"].pop(key_to_pop, None)
        return sample

    if strategy == "huge_field_strings":
        sample = make_valid_sample(seq=seq)
        # device max_length is 100; send 250 characters (stays well under frame cap)
        huge_str = "".join(rng.choices(string.ascii_letters, k=250))
        sample["payload"]["device"] = huge_str
        return sample

    if strategy == "invalid_datetime_tz":
        sample = make_valid_sample(seq=seq)
        # sent_at requires explicit timezone
        sample["sent_at"] = "2026-10-17T15:30:00"
        return sample

    # extreme_seq_jump
    sample = make_valid_sample(seq=seq + MAX_SEQ_JUMP + 500)
    return sample


def test_fuzz_1000_random_messages_no_crash() -> None:
    """Server answers BAD_MESSAGE/SCHEMA_ERROR without unhandled exceptions across 1000 messages."""
    # Configure high rate limit so rapid fuzz tests do not get throttled
    app = create_app(ServerConfig(max_msgs_per_min=100_000, retention_enabled=False))
    client = TestClient(app)

    rng = random.Random(1337)

    with client.websocket_connect("/api/v1/ingest") as ws:
        # Initial hello handshake
        ws.send_json(make_valid_hello(client_id="fuzz-tester-1000"))
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"

        unhandled_errors = 0
        handled_errors = 0

        for i in range(1, 1001):
            fuzz_msg = generate_fuzz_message(seq=i, rng=rng)
            if isinstance(fuzz_msg, str):
                ws.send_text(fuzz_msg)
            else:
                ws.send_text(json.dumps(fuzz_msg))

            # Server must answer BAD_MESSAGE or SCHEMA_ERROR without crashing
            resp_text = ws.receive_text()
            resp = json.loads(resp_text)
            assert resp.get("type") == "error", (
                f"Expected error response on message {i}, got {resp}"
            )
            assert resp.get("code") in ("BAD_MESSAGE", "SCHEMA_ERROR"), (
                f"Unexpected error code {resp.get('code')} on message {i}"
            )
            assert resp.get("fatal") is False
            handled_errors += 1

        assert unhandled_errors == 0
        assert handled_errors == 1000, f"Expected 1,000 handled errors, got {handled_errors}"

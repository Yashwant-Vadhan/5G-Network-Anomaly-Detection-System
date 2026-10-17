"""Tests for alert dispatcher and in-app channel (T13-003, Contract C9, Guardrail G13).

Acceptance Criteria:
- A raising channel never reaches the engine
- alerts.jsonl has one valid C9 per line
- No LLM import on this path (G13)
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from streaming.alerts.channels.in_app import InAppChannel
from streaming.alerts.dispatcher import AlertDispatcher, format_alert_body_with_template
from streaming.hub import LiveHub
from streaming.schema import AlertDelivery, AlertRecord, deserialize_alert_jsonl


class RaisingChannel:
    """Mock channel that always raises an unhandled runtime error."""

    name: str = "raising_channel"

    def __init__(self) -> None:
        self.call_count: int = 0

    async def send(self, alert: AlertRecord) -> AlertDelivery:
        self.call_count += 1
        raise RuntimeError("Network down or webhook crashed")


class SlowTimingOutChannel:
    """Mock channel that hangs and exceeds timeout."""

    name: str = "timeout_channel"

    def __init__(self) -> None:
        self.call_count: int = 0

    async def send(self, alert: AlertRecord) -> AlertDelivery:
        self.call_count += 1
        await asyncio.sleep(0.5)
        return AlertDelivery(channel=self.name, status="OK")


def _make_dummy_alert(alert_id: str = "alt-001", session_id: str = "sess-1") -> AlertRecord:
    now_iso = datetime.now(UTC).isoformat()
    body = format_alert_body_with_template(
        anomaly_type="SIGNAL_DEGRADATION",
        summary="Persistent degradation observed",
        evidence=["ss_rsrp < -110 dBm for 6 samples"],
    )
    return AlertRecord(
        alert_id=alert_id,
        created_at=now_iso,
        event_id="evt-101",
        session_id=session_id,
        source="phone",
        kind="NEW",
        severity="HIGH",
        anomaly_type="SIGNAL_DEGRADATION",
        event_status="PROVISIONAL",
        title="5G Signal Degradation Alert",
        body=body,
        evidence=["ss_rsrp < -110 dBm"],
    )


def test_raising_channel_never_reaches_engine() -> None:
    """Exceptions from failing/raising channels are isolated and recorded as FAILED."""
    async def _run() -> None:
        bad_channel = RaisingChannel()
        good_channel = InAppChannel(hub=None, alerts_path=Path("build/test_alerts.jsonl"))

        dispatcher = AlertDispatcher(
            channels=[bad_channel, good_channel],
            timeout_seconds=0.1,
            max_retries=1,
        )

        alert = _make_dummy_alert("alt-isolated")

        # Dispatching must not raise an exception even though bad_channel raises
        res = await dispatcher.dispatch(alert)
        assert res is alert

        # Check call count: 1 initial attempt + 1 retry = 2 attempts
        assert bad_channel.call_count == 2

        # Check delivery records
        deliveries = {d.channel: d for d in alert.delivery}
        assert "raising_channel" in deliveries
        assert deliveries["raising_channel"].status == "FAILED"
        assert "crashed" in deliveries["raising_channel"].detail

        assert "in_app" in deliveries
        assert deliveries["in_app"].status == "OK"

    asyncio.run(_run())


def test_timeout_channel_handled_with_retry() -> None:
    """Slow channel exceeding per-channel timeout is aborted and retried without blocking."""
    async def _run() -> None:
        slow_channel = SlowTimingOutChannel()
        dispatcher = AlertDispatcher(channels=[slow_channel], timeout_seconds=0.05, max_retries=1)

        alert = _make_dummy_alert("alt-timeout")
        await dispatcher.dispatch(alert)

        assert slow_channel.call_count == 2  # initial + 1 retry
        assert len(alert.delivery) == 1
        assert alert.delivery[0].status == "FAILED"
        assert "Timed out" in alert.delivery[0].detail

    asyncio.run(_run())


def test_in_app_channel_appends_valid_c9_per_line(tmp_path: Path) -> None:
    """in_app.py appends exactly one valid C9 JSON line per alert to alerts.jsonl."""
    async def _run() -> None:
        test_jsonl = tmp_path / "alerts.jsonl"
        hub = LiveHub()
        _sub_id, queue = await hub.subscribe()

        channel = InAppChannel(hub=hub, alerts_path=test_jsonl)

        alert1 = _make_dummy_alert("alt-1", session_id="sess-1")
        alert2 = _make_dummy_alert("alt-2", session_id="sess-1")

        d1 = await channel.send(alert1)
        d2 = await channel.send(alert2)
        assert d1.status == "OK"
        assert d2.status == "OK"

        # Hub received broadcast events
        ev1 = await queue.get()
        assert ev1["type"] == "alert"
        assert ev1["alert"]["alert_id"] == "alt-1"

        ev2 = await queue.get()
        assert ev2["type"] == "alert"
        assert ev2["alert"]["alert_id"] == "alt-2"

        # Verify alerts.jsonl has exactly 2 lines and each deserializes into valid AlertRecord
        lines = test_jsonl.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

        rec1 = deserialize_alert_jsonl(lines[0])
        assert rec1.alert_id == "alt-1"
        assert rec1.anomaly_type == "SIGNAL_DEGRADATION"

        rec2 = deserialize_alert_jsonl(lines[1])
        assert rec2.alert_id == "alt-2"

    asyncio.run(_run())


def test_no_llm_import_on_alert_dispatch_path() -> None:
    """Guardrail G13: No LLM/LangChain modules imported on the real-time alerting path."""
    forbidden_modules = [
        "langchain",
        "openai",
        "google.generativeai",
        "anthropic",
        "transformers",
    ]

    for mod in forbidden_modules:
        assert mod not in sys.modules, f"Forbidden LLM dependency '{mod}' imported on live path!"

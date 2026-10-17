"""In-app alert channel for live dashboard notifications (T13-003, Contract C9).

Delivers alert records to the live pub/sub hub and appends each alert to
data/live/alerts.jsonl (one valid C9 line per alert) with deterministic explanation
text formatted via agents.text_renderer.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from ml.config import DATA_DIR
from streaming.hub import LiveHub
from streaming.schema import AlertDelivery, AlertRecord, serialize_alert_jsonl

logger = logging.getLogger("streaming.alerts.channels.in_app")


class InAppChannel:
    """Delivers alerts to the in-memory LiveHub and data/live/alerts.jsonl (T13-003)."""

    name: str = "in_app"

    def __init__(
        self,
        hub: LiveHub | None = None,
        alerts_path: Path | str | None = None,
    ) -> None:
        self.hub = hub
        if alerts_path is not None:
            self.alerts_path = Path(alerts_path)
        else:
            self.alerts_path = DATA_DIR / "live" / "alerts.jsonl"

    async def send(self, alert: AlertRecord) -> AlertDelivery:
        """Publish alert to the live hub and append to alerts.jsonl."""
        try:
            # 1. Append valid C9 JSON line to alerts.jsonl
            self.alerts_path.parent.mkdir(parents=True, exist_ok=True)
            line = serialize_alert_jsonl(alert)
            with self.alerts_path.open("a", encoding="utf-8") as f:
                f.write(line)

            # 2. Publish alert message to live hub if connected
            if self.hub is not None:
                alert_ev = {
                    "type": "alert",
                    "schema_version": 2,
                    "server_time": datetime.now(UTC).isoformat(),
                    "session_id": alert.session_id,
                    "alert": alert.model_dump(mode="json"),
                }
                await self.hub.broadcast(alert_ev, session_id=alert.session_id)

            return AlertDelivery(channel=self.name, status="OK")
        except Exception as e:
            logger.error("Failed to deliver in-app alert %s: %s", alert.alert_id, e)
            raise

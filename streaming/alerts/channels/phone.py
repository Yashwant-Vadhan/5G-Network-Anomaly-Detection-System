"""Phone push alert notification channel delivering Contract C7 AlertPush messages (T13-006).

Sends compact alert push payloads back to the connected phone client over its active
ingest connection (Contract C7) to trigger local notifications during field sessions.
If the phone is disconnected, marks delivery as SKIPPED (no queueing in v2).
LOW severity alerts are suppressed by default.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from streaming.schema import AlertDelivery, AlertPush, AlertRecord

logger = logging.getLogger("streaming.alerts.channels.phone")


def to_compact_c9(alert: AlertRecord) -> dict[str, Any]:
    """Convert an AlertRecord into a compact Contract C9 payload for phone notifications."""
    return {
        "alert_id": alert.alert_id,
        "session_id": alert.session_id,
        "event_id": alert.event_id,
        "created_at": alert.created_at,
        "kind": alert.kind,
        "severity": alert.severity,
        "anomaly_type": alert.anomaly_type,
        "event_status": alert.event_status,
        "title": alert.title,
        "body": alert.body,
    }


class PhoneChannel:
    """Phone push alert notification channel delivering Contract C7 AlertPush messages (T13-006)."""

    name: str = "phone"

    def __init__(
        self,
        connection_resolver: Callable[[str], Any | None] | None = None,
        active_connections: dict[str, Any] | None = None,
        allow_low_severity: bool = False,
    ) -> None:
        self.connection_resolver = connection_resolver
        self.active_connections = active_connections
        self.allow_low_severity = allow_low_severity

    def _get_connection(self, session_id: str) -> Any | None:
        """Resolve active WebSocket connection for the specified session_id."""
        if self.connection_resolver is not None:
            try:
                return self.connection_resolver(session_id)
            except Exception as e:
                logger.warning("Error resolving connection for session %s: %s", session_id, e)
                return None
        if self.active_connections is not None:
            return self.active_connections.get(session_id)
        return None

    async def send(self, alert: AlertRecord) -> AlertDelivery:
        """Deliver compact C7 alert push to the connected phone client."""
        # 1. LOW severity not pushed by default
        if alert.severity.upper() == "LOW" and not self.allow_low_severity:
            return AlertDelivery(
                channel=self.name,
                status="SKIPPED",
                detail="Low severity alerts suppressed by default",
            )

        # 2. Resolve active ingest connection for the event's session
        conn = self._get_connection(alert.session_id)
        if conn is None:
            return AlertDelivery(
                channel=self.name,
                status="SKIPPED",
                detail=f"Phone client for session {alert.session_id} disconnected",
            )

        # 3. Construct C7 AlertPush message
        compact = to_compact_c9(alert)
        push_obj = AlertPush(alert=compact)
        payload_text = push_obj.model_dump_json()

        # 4. Transmit over active WebSocket connection only to this session's client
        try:
            if hasattr(conn, "send_text"):
                res = conn.send_text(payload_text)
                if asyncio.iscoroutine(res):
                    await res
            elif hasattr(conn, "send_json"):
                res = conn.send_json(push_obj.model_dump(mode="json"))
                if asyncio.iscoroutine(res):
                    await res
            else:
                raise TypeError(f"Unsupported connection object type: {type(conn)}")

            return AlertDelivery(
                channel=self.name,
                status="OK",
                detail=f"Pushed alert {alert.alert_id} to session {alert.session_id}",
            )
        except Exception as e:
            logger.warning(
                "Failed to push alert %s to session %s: %s",
                alert.alert_id,
                alert.session_id,
                e,
            )
            return AlertDelivery(
                channel=self.name,
                status="FAILED",
                detail=f"{type(e).__name__}: {e}",
            )

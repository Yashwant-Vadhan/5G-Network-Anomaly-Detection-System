"""Asynchronous alert notification dispatcher and multi-channel fan-out coordinator (T13-003).

Enforces per-channel timeouts, one retry on transient failure, exception isolation
so channel failures never bubble up to or block the core streaming engine, and records
delivery outcomes in the C9 alert delivery list.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from streaming.schema import AlertDelivery, AlertRecord

logger = logging.getLogger("streaming.alerts.dispatcher")


class AlertChannel(Protocol):
    """Protocol that all alert delivery channels must implement."""

    name: str

    async def send(self, alert: AlertRecord) -> AlertDelivery:
        """Deliver the alert to the target destination."""
        ...


class AlertDispatcher:
    """Asynchronous multi-channel alert dispatcher with exception isolation (T13-003)."""

    def __init__(
        self,
        channels: list[AlertChannel] | None = None,
        timeout_seconds: float = 5.0,
        max_retries: int = 1,
    ) -> None:
        self.channels: list[AlertChannel] = channels or []
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def register_channel(self, channel: AlertChannel) -> None:
        """Register an alert channel for fan-out."""
        self.channels.append(channel)

    async def dispatch(self, alert: AlertRecord) -> AlertRecord:
        """Fan out alert to all registered channels with timeout, retry, and isolation."""
        deliveries: list[AlertDelivery] = []

        for channel in self.channels:
            delivery = await self._send_to_channel(channel, alert)
            deliveries.append(delivery)

        alert.delivery = deliveries
        return alert

    async def _send_to_channel(self, channel: AlertChannel, alert: AlertRecord) -> AlertDelivery:
        """Send alert to a single channel with timeout, 1 retry, and complete isolation."""
        attempts = 0
        last_error = ""

        while attempts <= self.max_retries:
            attempts += 1
            try:
                delivery = await asyncio.wait_for(
                    channel.send(alert),
                    timeout=self.timeout_seconds,
                )
                if isinstance(delivery, AlertDelivery):
                    return delivery
                return AlertDelivery(channel=channel.name, status="OK")
            except TimeoutError:
                last_error = f"Timed out after {self.timeout_seconds}s"
                logger.warning(
                    "Channel '%s' timed out (attempt %d/%d) for alert %s",
                    channel.name,
                    attempts,
                    self.max_retries + 1,
                    alert.alert_id,
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Channel '%s' error (attempt %d/%d) for alert %s: %s",
                    channel.name,
                    attempts,
                    self.max_retries + 1,
                    alert.alert_id,
                    e,
                )

        # Retries exhausted - record failure without raising (Engine Isolation)
        return AlertDelivery(
            channel=channel.name,
            status="FAILED",
            detail=last_error,
        )


def format_alert_body_with_template(
    anomaly_type: str,
    summary: str,
    evidence: list[str] | None = None,
    rec_kind: str = "MONITORING",
    rec_text: str = "Monitor radio signal metrics for persistent degradation.",
) -> str:
    """Format explanation body using deterministic agents.text_renderer templates (T13-003)."""
    from agents.contracts import Diagnosis, Recommendation
    from agents.text_renderer import render

    diag = Diagnosis(
        summary=summary,
        evidence=evidence or [],
        anomaly_type=anomaly_type,
    )
    rec = Recommendation(kind=rec_kind, text=rec_text)
    return render(diag, rec)

"""Outbound HTTP webhook channel for external alert notification (T13-004).

Conforms strictly to Guardrail G26:
- Dispatches only the minimal data subset via alert.to_webhook_body().
- Webhook URL is loaded from NADS_ALERT_WEBHOOK_URL or explicit configuration.
- Webhook URL is sensitive and NEVER logged.
- Timeout is 5.0s with at most one retry.
- Dry-run mode outputs payload to stdout without sending HTTP requests.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

import httpx

from streaming.schema import AlertDelivery, AlertRecord

logger = logging.getLogger("streaming.alerts.channels.webhook")


class WebhookChannel:
    """Outbound webhook channel implementing Contract C9 and Guardrail G26."""

    name: str = "webhook"

    def __init__(
        self,
        webhook_url: str | None = None,
        timeout_seconds: float = 5.0,
        max_retries: int = 1,
        dry_run: bool = False,
    ) -> None:
        self.webhook_url = webhook_url or os.getenv("NADS_ALERT_WEBHOOK_URL")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.dry_run = dry_run

    async def send(self, alert: AlertRecord) -> AlertDelivery:
        """Deliver minimal alert payload to the configured webhook endpoint."""
        if not self.webhook_url:
            return AlertDelivery(
                channel=self.name,
                status="SKIPPED",
                detail="Webhook URL not configured",
            )

        # Minimal payload conforming strictly to Guardrail G26
        payload: dict[str, Any] = alert.to_webhook_body(include_evidence=False)

        if self.dry_run:
            payload_str = json.dumps(payload, indent=2)
            sys.stdout.write(f"[DRY-RUN WEBHOOK PAYLOAD]\n{payload_str}\n")
            sys.stdout.flush()
            return AlertDelivery(
                channel=self.name,
                status="OK",
                detail="dry-run",
            )

        attempts = 0
        last_detail = ""

        while attempts <= self.max_retries:
            attempts += 1
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(
                        self.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.is_success:
                        return AlertDelivery(
                            channel=self.name,
                            status="OK",
                            detail=f"HTTP {resp.status_code}",
                        )
                    last_detail = f"HTTP {resp.status_code}"
                    logger.warning(
                        "Webhook delivery failed with HTTP %s on attempt %d/%d",
                        resp.status_code,
                        attempts,
                        self.max_retries + 1,
                    )
            except httpx.TimeoutException:
                last_detail = f"Timed out after {self.timeout_seconds:.1f}s"
                logger.warning(
                    "Webhook delivery timed out on attempt %d/%d",
                    attempts,
                    self.max_retries + 1,
                )
            except Exception as e:
                last_detail = f"Network error: {type(e).__name__}"
                logger.warning(
                    "Webhook delivery network error on attempt %d/%d: %s",
                    attempts,
                    self.max_retries + 1,
                    type(e).__name__,
                )

        return AlertDelivery(
            channel=self.name,
            status="FAILED",
            detail=last_detail,
        )

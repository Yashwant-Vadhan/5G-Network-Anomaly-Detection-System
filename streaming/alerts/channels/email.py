"""Email notification channel utilizing standard library smtplib (T13-005).

Conforms strictly to Guardrail G26:
- Dispatches only the minimal plain-text data subset.
- Configured via environment variables (NADS_ALERT_EMAIL_*), off by default.
- Credentials and passwords are NEVER logged or exported in error messages.
- 10.0s timeout with exception isolation so failures never disrupt the streaming pipeline.
- Dry-run mode outputs message to stdout without sending network traffic.
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import sys
from email.message import EmailMessage

from streaming.schema import AlertDelivery, AlertRecord

logger = logging.getLogger("streaming.alerts.channels.email")


def format_email_body(alert: AlertRecord, include_evidence: bool = False) -> str:
    """Format minimal plain-text alert notification body conforming to Guardrail G26."""
    lines = [
        "5G-NADS Telemetry Anomaly Alert",
        "================================",
        f"Alert ID:     {alert.alert_id}",
        f"Session ID:   {alert.session_id}",
        f"Event ID:     {alert.event_id}",
        f"Created At:   {alert.created_at}",
        f"Severity:     {alert.severity}",
        f"Anomaly Type: {alert.anomaly_type}",
        "",
        "Title:",
        f"{alert.title}",
        "",
        "Details:",
        f"{alert.body}",
    ]
    if include_evidence and alert.evidence:
        lines.append("")
        lines.append("Evidence:")
        for item in alert.evidence:
            lines.append(f" - {item}")

    return "\n".join(lines)


class EmailChannel:
    """Standard library SMTP email notification channel with STARTTLS support."""

    name: str = "email"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        from_addr: str | None = None,
        to_addrs: list[str] | None = None,
        timeout_seconds: float = 10.0,
        dry_run: bool = False,
        include_evidence: bool = False,
    ) -> None:
        self.host = host or os.getenv("NADS_ALERT_EMAIL_HOST")
        port_raw = os.getenv("NADS_ALERT_EMAIL_PORT", "587")
        try:
            self.port = port if port is not None else int(port_raw)
        except ValueError:
            self.port = 587

        self.user = user or os.getenv("NADS_ALERT_EMAIL_USER")
        self.password = password or os.getenv("NADS_ALERT_EMAIL_PASSWORD")
        self.from_addr = from_addr or os.getenv("NADS_ALERT_EMAIL_FROM", "alerts@5g-nads.internal")

        raw_to = os.getenv("NADS_ALERT_EMAIL_TO", "")
        self.to_addrs = (
            to_addrs
            if to_addrs is not None
            else [t.strip() for t in raw_to.split(",") if t.strip()]
        )
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run
        inc_ev_env = os.getenv("NADS_ALERT_INCLUDE_EVIDENCE", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        self.include_evidence = include_evidence or inc_ev_env

    def build_message(self, alert: AlertRecord) -> EmailMessage:
        """Create a MIME plain-text email message for the alert."""
        msg = EmailMessage()
        msg["Subject"] = f"[5G-NADS {alert.severity}] Alert: {alert.anomaly_type}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.set_content(format_email_body(alert, include_evidence=self.include_evidence))
        return msg

    def _send_sync(self, msg: EmailMessage) -> None:
        """Synchronous SMTP delivery executed in a thread pool worker."""
        if not self.host:
            raise ValueError("SMTP host not configured")

        with smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds) as server:
            server.ehlo()
            if server.has_extn("STARTTLS"):
                server.starttls()
                server.ehlo()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.send_message(msg)

    async def send(self, alert: AlertRecord) -> AlertDelivery:
        """Deliver minimal alert notification via SMTP with failure isolation."""
        # Off by default unless host and recipients are specified
        if not self.host or not self.to_addrs:
            return AlertDelivery(
                channel=self.name,
                status="SKIPPED",
                detail="Email channel not configured",
            )

        msg = self.build_message(alert)

        if self.dry_run:
            payload_str = msg.as_string()
            sys.stdout.write(f"[DRY-RUN EMAIL MESSAGE]\n{payload_str}\n")
            sys.stdout.flush()
            return AlertDelivery(
                channel=self.name,
                status="OK",
                detail=f"dry-run ({len(self.to_addrs)} recipients)",
            )

        try:
            await asyncio.to_thread(self._send_sync, msg)
            return AlertDelivery(
                channel=self.name,
                status="OK",
                detail=f"Delivered to {len(self.to_addrs)} recipients",
            )
        except Exception as e:
            # Exception isolation: sanitize error to prevent password/credential leakage
            err_msg = str(e)
            if self.password and self.password in err_msg:
                err_msg = err_msg.replace(self.password, "******")
            logger.warning("Email delivery failure: %s", err_msg)
            return AlertDelivery(
                channel=self.name,
                status="FAILED",
                detail=f"{type(e).__name__}: {err_msg}",
            )

"""Notification channel adapters for alert dispatching.

Provides transport-specific delivery channels including in-app dashboard
alerts, phone push notifications over WebSocket, outbound HTTP webhooks,
and email alerts via standard library SMTP.
"""

from streaming.alerts.channels.in_app import InAppChannel

__all__ = ["InAppChannel"]


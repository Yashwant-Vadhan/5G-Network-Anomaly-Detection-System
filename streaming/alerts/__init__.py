"""Real-time alerting policy evaluation and notification dispatch subsystem.

Encapsulates deterministic policy decision logic, alert state deduplication,
cooldown timers, and multi-channel notification dispatchers across in-app,
phone, webhook, and email destinations.
"""

from streaming.alerts.channels.email import EmailChannel
from streaming.alerts.channels.in_app import InAppChannel
from streaming.alerts.channels.phone import PhoneChannel
from streaming.alerts.channels.webhook import WebhookChannel
from streaming.alerts.dispatcher import AlertDispatcher
from streaming.alerts.policy import decide, has_agent_rule_evidence

__all__ = [
    "AlertDispatcher",
    "EmailChannel",
    "InAppChannel",
    "PhoneChannel",
    "WebhookChannel",
    "decide",
    "has_agent_rule_evidence",
]

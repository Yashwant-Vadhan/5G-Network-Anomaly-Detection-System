"""Bounded pub/sub live fan-out hub for dashboard client subscriptions.

Broadcasts real-time events, scored samples, connection status transitions,
and alert notifications to connected dashboard WebSocket clients with bounded
subscriber queues and drop-oldest backpressure mitigation.
"""

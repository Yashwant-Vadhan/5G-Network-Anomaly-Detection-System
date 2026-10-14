"""Outbound HTTP webhook channel for external monitoring system integration.

Dispatches minimized alert payloads containing only title, body, severity,
event status, anomaly type, and timestamps to external webhook URLs with
enforced timeouts and complete exclusion of sensitive cell identifiers.
"""

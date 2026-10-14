"""Asynchronous alert notification dispatcher and multi-channel fan-out coordinator.

Enforces alert cooldown windows to prevent notification floods, handles
stateful escalation and resolution tracking, and isolates delivery failures
so individual channel timeouts never block the core telemetry stream.
"""

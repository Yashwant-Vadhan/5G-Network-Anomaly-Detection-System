"""Unit tests for the streaming package skeleton (T11-001)."""

import importlib

STREAMING_MODULES = [
    "streaming",
    "streaming.schema",
    "streaming.server",
    "streaming.session_manager",
    "streaming.engine",
    "streaming.event_tracker",
    "streaming.hub",
    "streaming.store",
    "streaming.metrics",
    "streaming.alerts",
    "streaming.alerts.policy",
    "streaming.alerts.dispatcher",
    "streaming.alerts.channels",
    "streaming.alerts.channels.in_app",
    "streaming.alerts.channels.phone",
    "streaming.alerts.channels.webhook",
    "streaming.alerts.channels.email",
]


def test_streaming_modules_importable_and_documented():
    for mod_name in STREAMING_MODULES:
        mod = importlib.import_module(mod_name)
        assert mod.__doc__ is not None, f"Module {mod_name} must have a docstring"
        assert len(mod.__doc__.strip()) > 30, f"Module {mod_name} docstring is too short"

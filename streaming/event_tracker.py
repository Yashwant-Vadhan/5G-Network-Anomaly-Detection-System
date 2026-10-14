"""Lifecycle tracker for streaming anomaly events and multi-agent diagnosis.

Tracks the progression of anomaly events from PROVISIONAL open state through
developing updates to immutable FINAL closure, invoking the multi-agent diagnostic
layer on state changes while maintaining caching to prevent redundant execution.
"""

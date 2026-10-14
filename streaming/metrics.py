"""Telemetry metrics and performance counters for the streaming pipeline.

Calculates end-to-end and per-stage processing latency percentiles (p50, p95, max),
detects sequence number gaps, measures device-server clock skew, and tracks queue
depths and subscriber drop statistics for live health monitoring.
"""

"""Append-only persistent file store for live session captures and alerts.

Persists incoming telemetry to data/live/ in raw C1 CSV format with accompanying
JSON metadata sidecars, generates SHA-256 integrity digests upon session
completion, and records dispatched alert logs to an append-only JSONL file.
"""

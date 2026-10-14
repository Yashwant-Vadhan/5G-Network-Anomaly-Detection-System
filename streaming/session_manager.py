"""In-memory session buffer and state tracking for active client connections.

Manages bounded per-(client_id, session) sample buffers, maintains strict
device-timestamp ordering, detects sequence gaps, ignores duplicate deliveries,
and triggers session rollover when buffer size limits are reached.
"""

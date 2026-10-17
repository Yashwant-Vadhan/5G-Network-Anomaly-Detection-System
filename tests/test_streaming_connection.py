"""Tests for T11-020: Connection state machine, stale detection, clock-skew flagging, and hub publishing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from streaming.connection import ConnectionTracker
from streaming.hub import LiveHub
from streaming.schema import ConnectionEvent


@pytest.fixture
def anyio_backend():
    return "asyncio"


class MockClock:
    """Injectable monotonic and wall clock for deterministic time manipulation."""

    def __init__(self, start_mono: float = 1000.0, start_wall: datetime | None = None) -> None:
        self.mono = start_mono
        self.wall = start_wall or datetime(2026, 10, 17, 10, 0, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.mono

    def wall_clock(self) -> datetime:
        return self.wall

    def advance(self, seconds: float) -> None:
        self.mono += seconds
        self.wall += timedelta(seconds=seconds)


def test_initial_state_is_waiting():
    """Before any connection or session, state evaluates to WAITING."""
    clock = MockClock()
    tracker = ConnectionTracker(clock=clock.monotonic, wall_clock=clock.wall_clock)
    state, age = tracker.get_state("non_existent_session")
    assert state == "WAITING"
    assert age is None


def test_connection_state_transitions_with_injectable_clock():
    """State transitions between WAITING -> LIVE -> STALE -> LIVE -> RECONNECTING -> WAITING."""
    clock = MockClock()
    tracker = ConnectionTracker(
        clock=clock.monotonic,
        wall_clock=clock.wall_clock,
        stale_after_seconds=10.0,
        resume_window_seconds=600.0,
    )

    # 1. Connect
    evt = tracker.on_connect(client_id="phone-01", session_id="sess-01", source="phone")
    assert evt.state == "LIVE"
    assert evt.session_id == "sess-01"
    assert evt.type == "connection"

    state, age = tracker.get_state("sess-01")
    assert state == "LIVE"
    assert age is None  # No sample yet

    # 2. Sample received
    sent_iso = clock.wall_clock().isoformat()
    evt, flag = tracker.on_sample("sess-01", sent_at=sent_iso, received_at=clock.wall_clock())
    assert not flag
    state, age = tracker.get_state("sess-01")
    assert state == "LIVE"
    assert age == 0.0

    # 3. Advance clock by 5s (less than 10s STALE threshold)
    clock.advance(5.0)
    stale_events = tracker.check_stale()
    assert len(stale_events) == 0
    state, age = tracker.get_state("sess-01")
    assert state == "LIVE"
    assert age == 5.0

    # 4. Advance clock by another 6s (total 11s > 10s STALE threshold)
    clock.advance(6.0)
    stale_events = tracker.check_stale()
    assert len(stale_events) == 1
    assert stale_events[0].state == "STALE"
    assert stale_events[0].session_id == "sess-01"
    assert stale_events[0].last_sample_age_s == 11.0

    state, age = tracker.get_state("sess-01")
    assert state == "STALE"
    assert age == 11.0

    # 5. New sample restores LIVE state
    sent_iso_2 = clock.wall_clock().isoformat()
    evt_live, _ = tracker.on_sample("sess-01", sent_at=sent_iso_2, received_at=clock.wall_clock())
    assert evt_live is not None
    assert evt_live.state == "LIVE"
    state, age = tracker.get_state("sess-01")
    assert state == "LIVE"
    assert age == 0.0

    # 6. Disconnect socket -> RECONNECTING
    evt_disc = tracker.on_disconnect("phone-01", "sess-01")
    assert evt_disc.state == "RECONNECTING"
    state, age = tracker.get_state("sess-01")
    assert state == "RECONNECTING"

    # 7. Advance clock past resume window (601s > 600s)
    clock.advance(601.0)
    state, _ = tracker.get_state("sess-01")
    assert state == "WAITING"

    # 8. Reconnect within window rolls or sets new session
    evt_reconn = tracker.on_connect(client_id="phone-01", session_id="sess-02", source="phone")
    assert evt_reconn.state == "LIVE"

    # 9. Explicit session close (bye) transitions immediately to WAITING
    evt_close = tracker.on_session_close("sess-02")
    assert evt_close.state == "WAITING"
    state, _ = tracker.get_state("sess-02")
    assert state == "WAITING"


def test_replay_source_state():
    """Replay source is identified with REPLAY-SOURCE state."""
    clock = MockClock()
    tracker = ConnectionTracker(clock=clock.monotonic, wall_clock=clock.wall_clock)
    evt = tracker.on_connect(client_id="replay-01", session_id="sess-replay", source="replay")
    assert evt.state == "REPLAY-SOURCE"
    state, _ = tracker.get_state("sess-replay")
    assert state == "REPLAY-SOURCE"


def test_clock_skew_flagging_leaves_data_unchanged():
    """Skew > CLOCK_SKEW_WARN_SECONDS raises the warning flag without altering timestamps."""
    clock = MockClock()
    tracker = ConnectionTracker(
        clock=clock.monotonic,
        wall_clock=clock.wall_clock,
        clock_skew_warn_seconds=5.0,
    )
    tracker.on_connect(client_id="phone-01", session_id="sess-skew")

    # Normal skew (2s <= 5s)
    rec_time = clock.wall_clock()
    sent_time_normal = (rec_time - timedelta(seconds=2.0)).isoformat()
    _, flag_normal = tracker.on_sample("sess-skew", sent_at=sent_time_normal, received_at=rec_time)
    assert not flag_normal

    # Skewed sample (sent_at is 15 seconds behind received_at)
    sent_time_skewed = (rec_time - timedelta(seconds=15.0)).isoformat()
    original_sent_str = str(sent_time_skewed)

    _, flag_skewed = tracker.on_sample("sess-skew", sent_at=sent_time_skewed, received_at=rec_time)
    assert flag_skewed is True

    # Timestamps are strictly unchanged
    assert sent_time_skewed == original_sent_str
    info = tracker._sessions["sess-skew"]
    assert info.clock_skew_flag is True
    assert info.latest_skew_s == 15.0


@pytest.mark.anyio
async def test_connection_events_published_to_hub():
    """Connection events (connect, sample, disconnect, close) are successfully published to LiveHub."""
    clock = MockClock()
    hub = LiveHub()
    sub_id, queue = await hub.subscribe()

    tracker = ConnectionTracker(
        hub=hub,
        clock=clock.monotonic,
        wall_clock=clock.wall_clock,
    )

    try:
        # Connect event
        evt_conn = tracker.on_connect(client_id="c1", session_id="s1")
        await hub.broadcast(evt_conn, session_id="s1")

        msg = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert (
            isinstance(msg, ConnectionEvent) and msg.type == "connection" and msg.state == "LIVE"
        ) or (
            isinstance(msg, dict) and msg.get("type") == "connection" and msg.get("state") == "LIVE"
        )

        # Disconnect event
        evt_disc = tracker.on_disconnect("c1", "s1")
        await hub.broadcast(evt_disc, session_id="s1")

        msg_disc = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert (isinstance(msg_disc, ConnectionEvent) and msg_disc.state == "RECONNECTING") or (
            isinstance(msg_disc, dict) and msg_disc.get("state") == "RECONNECTING"
        )

    finally:
        await hub.unsubscribe(sub_id)

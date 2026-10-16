"""Tests for streaming EventTracker lifecycle and immutability (T11-007)."""

from __future__ import annotations

import pytest

from streaming.event_tracker import EventTracker, ImmutableEventError
from streaming.schema import AlertDecision


def make_sample(
    timestamp: str,
    anomaly_type: str = "NORMAL",
    severity: str = "LOW",
    is_anom: bool = False,
) -> dict:
    return {
        "timestamp": timestamp,
        "device": "SM-A156E",
        "anomaly_type": anomaly_type,
        "severity": severity,
        "is_anom": is_anom,
        "seq": 1,
    }


def test_event_tracker_lifecycle_gap_closing():
    """Event opens on first anomaly, updates as it develops, and closes after gap threshold."""
    tracker = EventTracker(session_id="sm-a156e-1", device="SM-A156E", close_gap_samples=3)

    # 1. Normal sample - no event
    action, evt = tracker.process_sample(make_sample("2026-10-09T10:00:00", is_anom=False))
    assert action == "NONE"
    assert evt is None
    assert tracker.active_event is None

    # 2. First anomalous sample -> OPEN provisional event
    action, evt = tracker.process_sample(
        make_sample(
            "2026-10-09T10:00:03",
            anomaly_type="SIGNAL_DEGRADATION",
            severity="LOW",
            is_anom=True,
        )
    )
    assert action == "OPEN"
    assert evt is not None
    assert evt.event_id == "sm-a156e-1-e001"
    assert evt.status == "PROVISIONAL"
    assert evt.anomaly_type == "SIGNAL_DEGRADATION"
    assert evt.severity == "LOW"
    assert evt.ml["sample_count"] == 1

    # 3. Second anomalous sample with higher severity -> UPDATE
    action, evt = tracker.process_sample(
        make_sample(
            "2026-10-09T10:00:06",
            anomaly_type="PERSISTENT_POOR_QUALITY",
            severity="MEDIUM",
            is_anom=True,
        )
    )
    assert action == "UPDATE"
    assert evt is not None
    assert evt.event_id == "sm-a156e-1-e001"
    assert evt.status == "PROVISIONAL"
    assert evt.anomaly_type == "PERSISTENT_POOR_QUALITY"
    assert evt.severity == "MEDIUM"
    assert evt.ml["sample_count"] == 2
    assert evt.end == "2026-10-09T10:00:06"

    # 4. First normal sample (gap = 1) -> event stays open
    action, evt = tracker.process_sample(make_sample("2026-10-09T10:00:09", is_anom=False))
    assert action == "NONE"
    assert tracker.active_event is not None

    # 5. Second normal sample (gap = 2) -> event stays open
    action, evt = tracker.process_sample(make_sample("2026-10-09T10:00:12", is_anom=False))
    assert action == "NONE"
    assert tracker.active_event is not None

    # 6. Third normal sample (gap = 3 >= close_gap_samples) -> CLOSED to FINAL
    action, evt = tracker.process_sample(make_sample("2026-10-09T10:00:15", is_anom=False))
    assert action == "CLOSED"
    assert evt is not None
    assert evt.event_id == "sm-a156e-1-e001"
    assert evt.status == "FINAL"
    assert tracker.active_event is None
    assert len(tracker.closed_events) == 1


def test_event_id_format_matches_batch_convention():
    """Event IDs must match <session>-eNNN format."""
    tracker = EventTracker(session_id="redmi-1", device="Redmi 13 5G", close_gap_samples=2)

    # Event 1
    tracker.process_sample(
        make_sample("2026-10-09T10:00:00", anomaly_type="STATISTICAL_ONLY", is_anom=True)
    )
    tracker.process_sample(make_sample("2026-10-09T10:00:03", is_anom=False))
    tracker.process_sample(make_sample("2026-10-09T10:00:06", is_anom=False))

    # Event 2
    tracker.process_sample(
        make_sample("2026-10-09T10:00:09", anomaly_type="COMBINED_ANOMALY", is_anom=True)
    )
    tracker.process_sample(make_sample("2026-10-09T10:00:12", is_anom=False))
    tracker.process_sample(make_sample("2026-10-09T10:00:15", is_anom=False))

    events = tracker.closed_events
    assert len(events) == 2
    assert events[0].event_id == "redmi-1-e001"
    assert events[1].event_id == "redmi-1-e002"


def test_final_event_is_immutable():
    """Modifying a FINAL event must raise ImmutableEventError."""
    tracker = EventTracker(session_id="redmi-1", device="Redmi 13 5G", close_gap_samples=1)

    # Open and close an event
    tracker.process_sample(
        make_sample("2026-10-09T10:00:00", anomaly_type="SIGNAL_DEGRADATION", is_anom=True)
    )
    action, closed_evt = tracker.process_sample(make_sample("2026-10-09T10:00:03", is_anom=False))
    assert action == "CLOSED"
    assert closed_evt.status == "FINAL"

    # Attempting to modify closed event raises ImmutableEventError
    with pytest.raises(ImmutableEventError, match="Cannot modify immutable FINAL event"):
        tracker.update_event_metadata(
            event_id="redmi-1-e001",
            diagnosis={"summary": "Hacked diagnosis"},
        )


def test_session_end_closes_open_event():
    """Calling close_session() closes any open PROVISIONAL event to FINAL."""
    tracker = EventTracker(session_id="session-xyz", device="Redmi 13 5G", close_gap_samples=5)

    tracker.process_sample(
        make_sample("2026-10-09T10:00:00", anomaly_type="STATISTICAL_ONLY", is_anom=True)
    )
    assert tracker.active_event is not None
    assert tracker.active_event.status == "PROVISIONAL"

    # End session before gap threshold
    closed_evt = tracker.close_session()
    assert closed_evt is not None
    assert closed_evt.status == "FINAL"
    assert closed_evt.event_id == "session-xyz-e001"
    assert tracker.active_event is None
    assert len(tracker.closed_events) == 1


def test_provisional_event_metadata_update():
    """Updating a PROVISIONAL event metadata succeeds."""
    tracker = EventTracker(session_id="session-001", device="Redmi 13 5G")

    tracker.process_sample(
        make_sample("2026-10-09T10:00:00", anomaly_type="SIGNAL_DEGRADATION", is_anom=True)
    )
    updated = tracker.update_event_metadata(
        event_id="session-001-e001",
        diagnosis={"summary": "Gradual radio degradation"},
        recommendation={"text": "Check base station coverage"},
        alert_decision=AlertDecision(alerted=True, reason="Alert triggered"),
    )
    assert updated.diagnosis["summary"] == "Gradual radio degradation"
    assert updated.alert_decision.alerted is True

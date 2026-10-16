"""Lifecycle tracker for streaming anomaly events and multi-agent diagnosis (T11-007).

Tracks the progression of anomaly events from PROVISIONAL open state through
developing updates to immutable FINAL closure. Closes events after
EVENT_CLOSE_GAP_SAMPLES consecutive normal samples or at session end.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel

from ml.config import EVENT_CLOSE_GAP_SAMPLES
from streaming.schema import AlertDecision, EventRecord, EventStatus, ScoredSample

# Precedence order for anomaly types (highest priority first)
ANOMALY_PRECEDENCE = [
    "COMBINED_ANOMALY",
    "PERSISTENT_POOR_QUALITY",
    "SUDDEN_SIGNAL_DEGRADATION",
    "SIGNAL_DEGRADATION",
    "NETWORK_STATE_TRANSITION",
    "CELL_TRANSITION",
    "STATISTICAL_ONLY",
]

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


class ImmutableEventError(RuntimeError):
    """Raised when attempting to modify an event that has reached FINAL status."""


def get_highest_precedence_type(anomaly_types: list[str]) -> str:
    """Return the anomaly type with highest severity/precedence in the list."""
    if not anomaly_types:
        return "NORMAL"
    # Find the earliest anomaly type in the precedence list that appears in samples
    for atype in ANOMALY_PRECEDENCE:
        if atype in anomaly_types:
            return atype
    # Fallback to most common if not in precedence list
    return Counter(anomaly_types).most_common(1)[0][0]


def get_max_severity(severities: list[str]) -> str:
    """Compute maximum severity level (LOW, MEDIUM, HIGH) across a set of samples."""
    max_rank = 0
    highest = "LOW"
    for sev in severities:
        sev_upper = sev.upper() if isinstance(sev, str) else "LOW"
        rank = SEVERITY_RANK.get(sev_upper, 0)
        if rank > max_rank:
            max_rank = rank
            highest = sev_upper
    return highest


class EventTracker:
    """Tracks state and transitions of streaming anomaly events (T11-007).

    - Opens an event upon first classified anomaly sample.
    - Keeps event PROVISIONAL while developing; updates type & severity as samples accumulate.
    - Closes event to FINAL after `close_gap_samples` consecutive normal samples or session end.
    - Enforces strict immutability once an event reaches FINAL status.
    """

    def __init__(
        self,
        session_id: str,
        device: str,
        close_gap_samples: int = EVENT_CLOSE_GAP_SAMPLES,
    ) -> None:
        self.session_id = session_id
        self.device = device
        self.close_gap_samples = close_gap_samples

        self._event_counter = 1
        self._current_event: EventRecord | None = None
        self._current_samples: list[dict[str, Any]] = []
        self._gap_count = 0
        self._closed_events: list[EventRecord] = []

    @property
    def active_event(self) -> EventRecord | None:
        """Return the currently open PROVISIONAL event, or None."""
        return self._current_event

    @property
    def closed_events(self) -> list[EventRecord]:
        """Return all finalized events."""
        return list(self._closed_events)

    @property
    def all_events(self) -> list[EventRecord]:
        """Return all events (closed + active)."""
        events = list(self._closed_events)
        if self._current_event is not None:
            events.append(self._current_event)
        return events

    def get_event(self, event_id: str) -> EventRecord | None:
        """Retrieve an event by ID."""
        for evt in self.all_events:
            if evt.event_id == event_id:
                return evt
        return None

    def process_sample(
        self,
        sample: ScoredSample | dict[str, Any],
    ) -> tuple[str, EventRecord | None]:
        """Process a scored sample and advance the event tracking lifecycle.

        Returns:
            Tuple of (action, event_record) where action is one of:
            - "OPEN": A new provisional event was opened.
            - "UPDATE": The current provisional event was updated with new sample data.
            - "CLOSED": The provisional event closed and transitioned to FINAL.
            - "NONE": No change in event state.
        """
        if isinstance(sample, BaseModel):
            s_dict = sample.model_dump(mode="python")
        else:
            s_dict = sample

        # Check if sample is anomalous
        is_anom = s_dict.get("is_anom", False)
        if not is_anom:
            # Fallback check on anomaly_type
            atype = s_dict.get("anomaly_type", "NORMAL")
            is_anom = atype in (
                "SIGNAL_DEGRADATION",
                "SUDDEN_SIGNAL_DEGRADATION",
                "PERSISTENT_POOR_QUALITY",
                "COMBINED_ANOMALY",
                "STATISTICAL_ONLY",
            )

        ts = str(s_dict.get("timestamp", ""))

        if is_anom:
            # Reset consecutive normal sample gap counter
            self._gap_count = 0

            if self._current_event is None:
                # 1. Open new event
                event_id = f"{self.session_id}-e{self._event_counter:03d}"
                self._event_counter += 1
                self._current_samples = [s_dict]

                initial_atype = s_dict.get("anomaly_type", "NORMAL")
                initial_sev = s_dict.get("severity", "LOW")

                self._current_event = EventRecord(
                    event_id=event_id,
                    session_id=self.session_id,
                    start=ts,
                    end=ts,
                    anomaly_type=initial_atype,
                    severity=initial_sev,
                    ml={
                        "anomaly_type": initial_atype,
                        "max_severity": initial_sev,
                        "sample_count": 1,
                    },
                    status="PROVISIONAL",
                    alert_decision=AlertDecision(
                        alerted=False, reason="Below persistence/severity threshold"
                    ),
                )
                return "OPEN", self._current_event
            else:
                # 2. Update existing provisional event
                self._current_samples.append(s_dict)
                sample_types = [s.get("anomaly_type", "NORMAL") for s in self._current_samples]
                sample_sevs = [s.get("severity", "LOW") for s in self._current_samples]

                updated_atype = get_highest_precedence_type(sample_types)
                updated_sev = get_max_severity(sample_sevs)

                self._current_event = self._current_event.model_copy(
                    update={
                        "end": ts,
                        "anomaly_type": updated_atype,
                        "severity": updated_sev,
                        "ml": {
                            "anomaly_type": updated_atype,
                            "max_severity": updated_sev,
                            "sample_count": len(self._current_samples),
                        },
                    }
                )
                return "UPDATE", self._current_event
        else:
            # Sample is normal
            if self._current_event is not None:
                self._gap_count += 1
                if self._gap_count >= self.close_gap_samples:
                    # 3. Close event after gap threshold
                    closed_evt = self._current_event.model_copy(update={"status": "FINAL"})
                    self._closed_events.append(closed_evt)
                    self._current_event = None
                    self._current_samples = []
                    self._gap_count = 0
                    return "CLOSED", closed_evt

            return "NONE", None

    def close_session(self) -> EventRecord | None:
        """Close any open provisional event at the end of the streaming session."""
        if self._current_event is not None:
            closed_evt = self._current_event.model_copy(update={"status": "FINAL"})
            self._closed_events.append(closed_evt)
            self._current_event = None
            self._current_samples = []
            self._gap_count = 0
            return closed_evt
        return None

    def update_event_metadata(
        self,
        event_id: str,
        diagnosis: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
        alert_decision: AlertDecision | None = None,
        status: EventStatus | None = None,
    ) -> EventRecord:
        """Update diagnostic fields of an active event. Raises ImmutableEventError if FINAL."""
        # Check closed events
        for closed in self._closed_events:
            if closed.event_id == event_id:
                raise ImmutableEventError(f"Cannot modify immutable FINAL event: {event_id}")

        if self._current_event is not None and self._current_event.event_id == event_id:
            updates: dict[str, Any] = {}
            if diagnosis is not None:
                updates["diagnosis"] = diagnosis
            if recommendation is not None:
                updates["recommendation"] = recommendation
            if alert_decision is not None:
                updates["alert_decision"] = alert_decision
            if status is not None:
                updates["status"] = status

            self._current_event = self._current_event.model_copy(update=updates)
            return self._current_event

        raise KeyError(f"Event not found: {event_id}")

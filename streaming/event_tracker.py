"""Lifecycle tracker for streaming anomaly events and multi-agent diagnosis (T11-007).

Tracks the progression of anomaly events from PROVISIONAL open state through
developing updates to immutable FINAL closure. Closes events after
EVENT_CLOSE_GAP_SAMPLES consecutive normal samples or at session end.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from typing import Any

import pandas as pd
from pydantic import BaseModel

from agents.orchestrator import build_event_window, run_agents, validate_c5_record
from ml.config import EVENT_CLOSE_GAP_SAMPLES
from streaming.schema import AlertDecision, EventRecord, EventStatus, ScoredSample

logger = logging.getLogger(__name__)

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


def compute_window_hash(event_id: str, window_df: pd.DataFrame, ml: dict[str, Any]) -> str:
    """Compute deterministic hash for caching agent results per (event_id, window_hash)."""
    h = hashlib.sha256()
    atype = ml.get("anomaly_type", "")
    sev = ml.get("max_severity", "")
    h.update(f"{event_id}:{len(window_df)}:{atype}:{sev}".encode())
    if "timestamp" in window_df.columns:
        ts_str = "".join(window_df["timestamp"].astype(str).tolist())
        h.update(ts_str.encode("utf-8"))
    return h.hexdigest()


class EventTracker:
    """Tracks state and transitions of streaming anomaly events (T11-007, T11-008).

    - Opens an event upon first classified anomaly sample.
    - Keeps event PROVISIONAL while developing; updates type & severity as samples accumulate.
    - Runs agents on event open, on type/severity change, and on close (cached by window hash).
    - Closes event to FINAL after `close_gap_samples` consecutive normal samples or session end.
    - Enforces strict immutability once an event reaches FINAL status.
    """

    def __init__(
        self,
        session_id: str,
        device: str,
        close_gap_samples: int = EVENT_CLOSE_GAP_SAMPLES,
        context_samples: int = 5,
        enable_agents: bool = True,
    ) -> None:
        self.session_id = session_id
        self.device = device
        self.close_gap_samples = close_gap_samples
        self.context_samples = context_samples
        self.enable_agents = enable_agents

        self._event_counter = 1
        self._current_event: EventRecord | None = None
        self._current_samples: list[dict[str, Any]] = []
        self._history_samples: list[dict[str, Any]] = []
        self._gap_count = 0
        self._closed_events: list[EventRecord] = []
        self._agent_cache: dict[tuple[str, str], dict[str, Any]] = {}

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

    def _diagnose_event(
        self,
        event: EventRecord,
        status: EventStatus,
        scores_df: pd.DataFrame | None = None,
    ) -> EventRecord:
        """Run agents on event window, caching by (event_id, window_hash) and validating C5."""
        if not self.enable_agents:
            return event.model_copy(update={"status": status})

        # Build scores_df if not provided
        if scores_df is None or scores_df.empty:
            if self._history_samples:
                scores_df = pd.DataFrame(self._history_samples)
            elif self._current_samples:
                scores_df = pd.DataFrame(self._current_samples)
            else:
                scores_df = pd.DataFrame(
                    [
                        {
                            "session_id": self.session_id,
                            "timestamp": event.start,
                            "device": self.device,
                        }
                    ]
                )

        df_copy = scores_df.copy()
        if "session_id" not in df_copy.columns:
            df_copy["session_id"] = self.session_id
        if "timestamp" in df_copy.columns:
            df_copy["timestamp"] = pd.to_datetime(df_copy["timestamp"])

        evt_dict = {
            "event_id": event.event_id,
            "session_id": self.session_id,
            "start_time": pd.to_datetime(event.start),
            "end_time": pd.to_datetime(event.end),
            "start": event.start,
            "end": event.end,
            "anomaly_type": event.anomaly_type,
            "max_severity": event.severity,
            "sample_count": event.ml.get("sample_count", len(self._current_samples) or 1),
        }

        try:
            window = build_event_window(df_copy, evt_dict, context_samples=self.context_samples)
            w_hash = compute_window_hash(event.event_id, window.df, window.ml)
            cache_key = (event.event_id, w_hash)

            if cache_key in self._agent_cache:
                record = self._agent_cache[cache_key]
            else:
                record = run_agents(window)
                record["status"] = status
                validate_c5_record(record)
                self._agent_cache[cache_key] = record

            return event.model_copy(
                update={
                    "status": status,
                    "signal": record.get("signal"),
                    "cell": record.get("cell"),
                    "network": record.get("network"),
                    "signal_report": record.get("signal_report"),
                    "cell_report": record.get("cell_report"),
                    "network_report": record.get("network_report"),
                    "diagnosis": record.get("diagnosis"),
                    "recommendation": record.get("recommendation"),
                    "explanation_text": record.get("explanation_text"),
                }
            )
        except Exception as e:
            logger.warning("Failed to run agents on event %s: %s", event.event_id, e)
            return event.model_copy(update={"status": status})

    def process_sample(
        self,
        sample: ScoredSample | dict[str, Any],
        scores_df: pd.DataFrame | None = None,
    ) -> tuple[str, EventRecord | None]:
        """Process a scored sample and advance the event tracking lifecycle.

        Returns:
            Tuple of (action, event_record) where action is one of:
            - "OPEN": A new provisional event was opened and diagnosed.
            - "UPDATE": The current provisional event was updated with new sample data.
            - "CLOSED": The provisional event closed and transitioned to FINAL.
            - "NONE": No change in event state.
        """
        if isinstance(sample, BaseModel):
            s_dict = sample.model_dump(mode="python")
        else:
            s_dict = sample

        self._history_samples.append(s_dict)

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

                raw_event = EventRecord(
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
                self._current_event = self._diagnose_event(raw_event, "PROVISIONAL", scores_df)
                return "OPEN", self._current_event
            else:
                # 2. Update existing provisional event
                prev_atype = self._current_event.anomaly_type
                prev_sev = self._current_event.severity

                self._current_samples.append(s_dict)
                sample_types = [s.get("anomaly_type", "NORMAL") for s in self._current_samples]
                sample_sevs = [s.get("severity", "LOW") for s in self._current_samples]

                updated_atype = get_highest_precedence_type(sample_types)
                updated_sev = get_max_severity(sample_sevs)

                updated_event = self._current_event.model_copy(
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

                # Re-diagnose if type or severity changed
                if updated_atype != prev_atype or updated_sev != prev_sev:
                    self._current_event = self._diagnose_event(
                        updated_event, "PROVISIONAL", scores_df
                    )
                else:
                    self._current_event = updated_event

                return "UPDATE", self._current_event
        else:
            # Sample is normal
            if self._current_event is not None:
                self._gap_count += 1
                if self._gap_count >= self.close_gap_samples:
                    # 3. Close event after gap threshold
                    closed_evt = self._diagnose_event(self._current_event, "FINAL", scores_df)
                    self._closed_events.append(closed_evt)
                    self._current_event = None
                    self._current_samples = []
                    self._gap_count = 0
                    return "CLOSED", closed_evt

            return "NONE", None

    def close_session(self, scores_df: pd.DataFrame | None = None) -> EventRecord | None:
        """Close any open provisional event at the end of the streaming session."""
        if self._current_event is not None:
            closed_evt = self._diagnose_event(self._current_event, "FINAL", scores_df)
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

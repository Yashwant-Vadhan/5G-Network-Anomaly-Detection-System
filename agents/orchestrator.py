"""Multi-agent orchestrator module for 5G-NADS (T5-001).

Builds EventWindow objects from detection results and orchestrates the multi-agent
pipeline execution (Signal -> Cell -> Network -> Diagnosis -> Recommendation).

Guardrail G9: Orchestrator MUST NOT import sklearn or load ML models directly.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from agents.contracts import (
    CellReport,
    Diagnosis,
    EventWindow,
    NetworkReport,
    Recommendation,
    SignalReport,
)

logger = logging.getLogger(__name__)


def build_event_window(
    scores_df: pd.DataFrame,
    event: dict[str, Any],
    context_samples: int = 5,
) -> EventWindow:
    """Build an EventWindow dataclass containing event samples plus context before the event.

    Ensures context never crosses session boundaries.

    Args:
        scores_df: DataFrame containing preprocessed measurements and anomaly scores.
        event: Dictionary containing event metadata (event_id, session_id, start_time, end_time).
        context_samples: Number of preceding context samples to include.

    Returns:
        EventWindow contract object ready for agent analysis.
    """
    session_id = event["session_id"]
    sess_df = scores_df[scores_df["session_id"] == session_id].sort_values("timestamp")

    start_time = pd.to_datetime(event["start_time"])
    end_time = pd.to_datetime(event["end_time"])

    event_indices = sess_df[
        (sess_df["timestamp"] >= start_time) & (sess_df["timestamp"] <= end_time)
    ].index

    if len(event_indices) == 0:
        event_indices = sess_df.index[:1]

    first_idx = event_indices[0]
    last_idx = event_indices[-1]

    sess_pos_map = {idx: pos for pos, idx in enumerate(sess_df.index)}
    first_pos = sess_pos_map[first_idx]
    last_pos = sess_pos_map[last_idx]

    start_pos = max(0, first_pos - context_samples)
    window_df = sess_df.iloc[start_pos : last_pos + 1].copy()

    ml_summary = {
        "anomaly_type": event.get("anomaly_type", "NORMAL"),
        "max_severity": event.get("max_severity", "LOW"),
        "sample_count": event.get("sample_count", len(event_indices)),
    }

    context_count = first_pos - start_pos

    return EventWindow(
        df=window_df,
        event_id=str(event.get("event_id", "evt-000")),
        session_id=str(session_id),
        start=str(start_time),
        end=str(end_time),
        context_before=context_count,
        ml=ml_summary,
    )


def run_agents(window: EventWindow) -> dict[str, Any]:
    """Orchestrate sequential agent execution.

    Pipeline: Signal -> Cell -> Network -> Diagnosis -> Recommendation.

    Args:
        window: EventWindow input context.

    Returns:
        Dictionary containing all structured agent reports matching Contract C5.
    """
    from agents.cell_agent import analyze as analyze_cell
    from agents.diagnosis_agent import diagnose
    from agents.network_agent import analyze as analyze_network
    from agents.recommendation_agent import recommend
    from agents.signal_agent import analyze as analyze_signal
    from agents.text_renderer import render

    # 1. Signal Agent
    signal_report: SignalReport = analyze_signal(window)

    # 2. Cell Agent
    cell_report: CellReport = analyze_cell(window)

    # 3. Network Agent
    network_report: NetworkReport = analyze_network(window)

    # 4. Diagnosis Agent
    diagnosis_report: Diagnosis = diagnose(
        signal=signal_report,
        cell=cell_report,
        network=network_report,
        ml=window.ml,
        anomaly_type=window.ml.get("anomaly_type", "NORMAL"),
    )

    # 5. Recommendation Agent
    recommendation_report: Recommendation = recommend(diagnosis=diagnosis_report)

    # Render explanation text
    rendered_text: str = render(diagnosis_report, recommendation_report)

    return {
        "event_id": window.event_id,
        "session_id": window.session_id,
        "start": window.start,
        "end": window.end,
        "anomaly_type": window.ml.get("anomaly_type", "NORMAL"),
        "severity": window.ml.get("max_severity", "LOW"),
        "ml": window.ml,
        "signal": signal_report.to_dict(),
        "cell": cell_report.to_dict(),
        "network": network_report.to_dict(),
        "signal_report": signal_report.to_dict(),
        "cell_report": cell_report.to_dict(),
        "network_report": network_report.to_dict(),
        "diagnosis": diagnosis_report.to_dict(),
        "recommendation": recommendation_report.to_dict(),
        "explanation_text": rendered_text,
    }


REQUIRED_C5_KEYS: set[str] = {
    "event_id",
    "session_id",
    "start",
    "end",
    "anomaly_type",
    "severity",
    "ml",
    "signal",
    "cell",
    "network",
    "diagnosis",
    "recommendation",
}


def validate_c5_record(record: dict[str, Any]) -> None:
    """Validate that an event record contains all required C5 contract keys."""
    missing = REQUIRED_C5_KEYS - set(record.keys())
    if missing:
        evt_id = record.get("event_id", "unknown")
        raise ValueError(f"Invalid C5 record '{evt_id}': missing required keys {sorted(missing)}")


def run_all_events(
    scores_df: pd.DataFrame,
    events: list[dict[str, Any]],
    context_samples: int = 5,
) -> list[dict[str, Any]]:
    """Run agent pipeline for all detected events in a dataset.

    Args:
        scores_df: Scored measurements DataFrame.
        events: List of event dictionaries.
        context_samples: Number of preceding context samples to include.

    Returns:
        List of diagnosed event dictionaries adhering to Contract C5.
    """
    diagnosed_events = []
    for event in events:
        window = build_event_window(scores_df, event, context_samples=context_samples)
        record = run_agents(window)
        diagnosed_events.append(record)
    return diagnosed_events


def write_events_diagnosed(
    events: list[dict[str, Any]],
    path: Path | str,
) -> None:
    """Validate all event records against Contract C5 and write to JSON.

    Fails loudly without writing a partial file if any record is invalid.

    Args:
        events: List of diagnosed event dictionaries.
        path: Path to output JSON file.
    """
    import json

    for record in events:
        validate_c5_record(record)

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    logger.info("Successfully wrote %d diagnosed events to %s", len(events), output_path)

"""Agent data contracts for 5G-NADS (T1-009).

Defines frozen dataclasses per Contract C6 in `docs/planning/TECH_RULES.md` and
`project-overview.md` §28. Dataclasses represent structured agent input/output
reports across the agent pipeline (Signal -> Cell -> Network -> Diagnosis -> Recommendation).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from ml.config import DEPLOYMENT_MODES

if TYPE_CHECKING:
    import pandas as pd

VALID_RECOMMENDATION_KINDS: set[str] = {"MONITORING", "OPERATOR_ACTION"}


@dataclass(frozen=True)
class EventWindow:
    """Window of event data and context passed to agents (Contract C6, project-overview.md §28).

    Attributes:
        df: Pandas DataFrame slice containing the event window.
        event_id: Unique event identifier.
        session_id: Session identifier (<device>-<n>).
        start: Event start timestamp (ISO-8601 string).
        end: Event end timestamp (ISO-8601 string).
        context_before: Number of context samples preceding the event.
        ml: Dictionary containing ML scores and flags (e.g. if_score, if_flag, baseline_flag).
    """

    df: pd.DataFrame
    event_id: str
    session_id: str
    start: str
    end: str
    context_before: int
    ml: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert EventWindow metadata to a serializable dictionary (omits DataFrame object)."""
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "start": self.start,
            "end": self.end,
            "context_before": self.context_before,
            "ml": self.ml,
        }


@dataclass(frozen=True)
class SignalReport:
    """Signal Agent evaluation output (Contract C6, project-overview.md §28).

    Attributes:
        signal_condition: Evaluated signal state (e.g. 'good', 'fair', 'degraded', 'unknown').
        evidence: List of concrete human-readable evidence strings.
    """

    signal_condition: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class CellReport:
    """Cell Transition Agent evaluation output (Contract C6, project-overview.md §28).

    Attributes:
        cell_event: Cell change event classification
            (e.g. 'CELL_CHANGE', 'REPEATED_CELL_CHANGE', 'NONE').
        evidence: List of concrete human-readable evidence strings.
    """

    cell_event: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class NetworkReport:
    """Network-State Agent evaluation output (Contract C6, project-overview.md §28).

    Attributes:
        network_state: Network stability or transition classification.
        deployment_mode: Observed deployment mode ('NSA', 'SA', or 'UNKNOWN').
        evidence: List of concrete human-readable evidence strings.
    """

    network_state: str
    deployment_mode: str
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate deployment_mode against DEPLOYMENT_MODES (overview §28 & G4)."""
        if self.deployment_mode not in DEPLOYMENT_MODES:
            raise ValueError(
                f"Invalid deployment_mode '{self.deployment_mode}'. "
                f"Must be one of {DEPLOYMENT_MODES}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class Diagnosis:
    """Diagnosis Agent evaluation output (Contract C6, project-overview.md §28).

    Attributes:
        summary: High-level summary of the diagnosed anomaly or normal condition.
        evidence: Aggregated evidence statements from upstream reports.
        confidence_note: Hedged attribution note (e.g. 'correlation, not confirmed cause').
        anomaly_type: Anomaly classification matching ANOMALY_TYPES.
    """

    summary: str
    evidence: list[str] = field(default_factory=list)
    confidence_note: str = "correlation, not confirmed cause"
    anomaly_type: str = "NORMAL"

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class Recommendation:
    """Recommendation Agent evaluation output (Contract C6, project-overview.md §28).

    Attributes:
        text: Actionable advice text for operator/monitoring.
        kind: Type of recommendation ('MONITORING' or 'OPERATOR_ACTION').
    """

    text: str
    kind: str

    def __post_init__(self) -> None:
        """Validate recommendation kind."""
        if self.kind not in VALID_RECOMMENDATION_KINDS:
            raise ValueError(
                f"Invalid recommendation kind '{self.kind}'. "
                f"Must be one of {VALID_RECOMMENDATION_KINDS}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return asdict(self)

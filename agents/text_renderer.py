"""Deterministic Explanation Text Renderer for 5G-NADS (T5-007).

Renders Diagnosis and Recommendation contract objects into structured, readable,
hedged explanation text using fixed templates without LLM dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.contracts import Diagnosis, Recommendation

# Forbidden words to strictly enforce Copy Rules (no causal claims)
FORBIDDEN_WORDS: set[str] = {
    "caused",
    "because of",
    "guarantees",
    "fault",
    "root cause",
    "proved",
}

# Template map for all anomaly types + STATISTICAL_ONLY + NORMAL/NONE
TEMPLATES: dict[str, str] = {
    "NORMAL": (
        "Summary: {summary}\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
    "NONE": (
        "Summary: {summary}\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
    "SIGNAL_DEGRADATION": (
        "Summary: {summary}\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
    "SUDDEN_SIGNAL_DEGRADATION": (
        "Summary: {summary}\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
    "CELL_TRANSITION": (
        "Summary: {summary}\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
    "NETWORK_STATE_TRANSITION": (
        "Summary: {summary}\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
    "PERSISTENT_POOR_QUALITY": (
        "Summary: {summary}\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
    "COMBINED_ANOMALY": (
        "Summary: {summary}\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
    "STATISTICAL_ONLY": (
        "Summary: Statistically unusual signal patterns detected without rule-based trigger.\n"
        "Evidence: {evidence_text}\n"
        "Confidence Note: {confidence_note}\n"
        "Recommendation ({rec_kind}): {rec_text}"
    ),
}


def render(diagnosis: Diagnosis, recommendation: Recommendation) -> str:
    """Render diagnosis and recommendation into a deterministic text explanation.

    Args:
        diagnosis: Diagnosis contract object.
        recommendation: Recommendation contract object.

    Returns:
        Formatted explanation string.
    """
    atype = diagnosis.anomaly_type
    template = TEMPLATES.get(atype, TEMPLATES["STATISTICAL_ONLY"])

    evidence_text = (
        "; ".join(diagnosis.evidence) if diagnosis.evidence else "No specific evidence flagged."
    )

    rendered = template.format(
        summary=diagnosis.summary,
        evidence_text=evidence_text,
        confidence_note=diagnosis.confidence_note,
        rec_kind=recommendation.kind,
        rec_text=recommendation.text,
    )

    return rendered

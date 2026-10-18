"""Unit tests for streaming alert quality and volume evaluation runner (T14-012).

Verifies v1 FPR verification, suppression breakdown, report formatting,
and line length constraints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.eval_alert_quality import (
    V1_VERIFIED_METRICS,
    generate_alert_quality_report,
    update_results_v2,
)


def _mock_quality_summary() -> dict[str, Any]:
    return {
        "timestamp": "2026-10-18T10:00:00+00:00",
        "total_frames": 3771,
        "total_alerts": 0,
        "suppression_counts": {
            "ML-only (no rule evidence)": 445,
            "Below persistence/severity threshold": 14,
            "Transition only": 0,
        },
        "v1_benchmarks": V1_VERIFIED_METRICS,
        "sessions": [
            {
                "session_id": "5G_measurements_Redmi_Stable",
                "samples": 800,
                "duration_hours": 0.67,
                "alerts": 0,
                "suppressed": 120,
                "alert_rate_per_hour": 0.0,
            },
            {
                "session_id": "5G_measurements_Samsung_Indoor-Movement",
                "samples": 900,
                "duration_hours": 0.75,
                "alerts": 0,
                "suppressed": 150,
                "alert_rate_per_hour": 0.0,
            },
        ],
    }


def test_v1_metrics_verification() -> None:
    """v1 FPR benchmarks in V1_VERIFIED_METRICS match figures cited in docs/results.md."""
    v1 = V1_VERIFIED_METRICS
    assert v1["total_evaluated_samples"] == 3771
    assert v1["actual_positives"] == 319
    assert v1["actual_negatives"] == 3452
    assert v1["if_false_positives"] == 2539
    assert pytest.approx(v1["if_raw_fpr"], rel=1e-3) == 0.7355
    assert v1["base_false_positives"] == 332
    assert pytest.approx(v1["base_raw_fpr"], rel=1e-3) == 0.0962


def test_generate_alert_quality_report_structure() -> None:
    """Report contains required markdown sections, tables, and root-cause summaries."""
    summary = _mock_quality_summary()
    report = generate_alert_quality_report(summary)

    assert "## 6. Alert Quality, Volume & False Alert Investigation" in report
    assert "Raw Model Noise vs Gated Alert Volume" in report
    assert "Suppression Breakdown by Root Cause" in report
    assert "False Alert Rate by Replay Session" in report
    assert "Stationary Normal Traces" in report
    assert "0.00 alerts/hour" in report

    # Verify line length constraint on all lines
    for line_idx, line in enumerate(report.splitlines(), 1):
        assert len(line) <= 100, f"Line {line_idx} exceeds 100 characters ({len(line)}): {line}"


def test_update_results_v2_section6_append_and_replace(tmp_path: Path) -> None:
    """update_results_v2 properly appends and idempotently updates Section 6."""
    target_file = tmp_path / "results_v2.md"
    initial_content = "# Results V2\n\n## 5. Detection Latency\nNotes.\n"
    target_file.write_text(initial_content, encoding="utf-8")

    summary = _mock_quality_summary()
    report = generate_alert_quality_report(summary)

    # 1. Append Section 6
    update_results_v2(report, path=target_file)
    content1 = target_file.read_text(encoding="utf-8")
    assert "## 5. Detection Latency" in content1
    assert "## 6. Alert Quality, Volume & False Alert Investigation" in content1

    # 2. Idempotent update
    update_results_v2(report, path=target_file)
    content2 = target_file.read_text(encoding="utf-8")
    assert content2.count("## 6. Alert Quality, Volume & False Alert Investigation") == 1

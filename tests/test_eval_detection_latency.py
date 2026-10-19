"""Unit tests for streaming detection latency evaluation runner (T14-011).

Verifies latency evaluation logic, small-sample caveats, table formatting,
and honest reporting comparing Isolation Forest vs Baseline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.eval_detection_latency import (
    generate_latency_report,
    update_results_v2,
)


def _mock_summary() -> dict[str, Any]:
    return {
        "timestamp": "2026-10-18T10:00:00+00:00",
        "total_events": 9,
        "if_detected_count": 8,
        "if_detection_rate": 8 / 9,
        "if_mean_latency_samples": 1.0,
        "if_mean_latency_seconds": 3.0,
        "base_detected_count": 6,
        "base_detection_rate": 6 / 9,
        "base_mean_latency_samples": 7.67,
        "base_mean_latency_seconds": 23.0,
        "events": [
            {
                "session_id": "5G_measurements_Redmi_Stable",
                "window": "[148, 168]",
                "label": "SIGNAL_DEGRADATION",
                "window_len": 21,
                "first_if_samples": 0,
                "first_if_seconds": 0.0,
                "first_base_samples": 3,
                "first_base_seconds": 9.0,
                "first_prov_samples": 0,
                "first_prov_seconds": 0.0,
                "first_alert": None,
                "comparison": "IF faster",
            },
            {
                "session_id": "5G_measurements_Samsung_Travel",
                "window": "[178, 202]",
                "label": "COMBINED_ANOMALY",
                "window_len": 25,
                "first_if_samples": None,
                "first_if_seconds": None,
                "first_base_samples": None,
                "first_base_seconds": None,
                "first_prov_samples": 0,
                "first_prov_seconds": 0.0,
                "first_alert": None,
                "comparison": "Rule/Prov only",
            },
        ],
    }


def test_generate_latency_report_structure() -> None:
    """Report contains required markdown sections, tables, and caveats."""
    summary = _mock_summary()
    report = generate_latency_report(summary)

    assert "## 5. Streaming Detection Latency Evaluation (T14-011)" in report
    assert "Ground-Truth Window Latency Benchmark Table" in report
    assert "Aggregate Performance & Method Comparison" in report
    assert "Small-Sample Caveats & Statistical Uncertainty" in report
    assert "Does Isolation Forest beat Baseline?" in report
    assert "Yes." in report
    assert "N = 9" in report

    # Check line length constraint
    for line_idx, line in enumerate(report.splitlines(), 1):
        assert len(line) <= 100, f"Line {line_idx} exceeds 100 characters ({len(line)}): {line}"


def test_update_results_v2_append_and_replace(tmp_path: Path) -> None:
    """update_results_v2 properly appends and replaces Section 5."""
    target_file = tmp_path / "results_v2.md"
    initial_content = "# Results V2\n\n## 1. Intro\nInitial notes.\n"
    target_file.write_text(initial_content, encoding="utf-8")

    summary = _mock_summary()
    report = generate_latency_report(summary)

    # 1. Append Section 5
    update_results_v2(report, path=target_file)
    content1 = target_file.read_text(encoding="utf-8")
    assert "## 1. Intro" in content1
    assert "## 5. Streaming Detection Latency Evaluation" in content1

    # 2. Idempotent update/replacement
    update_results_v2(report, path=target_file)
    content2 = target_file.read_text(encoding="utf-8")
    assert content2.count("## 5. Streaming Detection Latency Evaluation") == 1

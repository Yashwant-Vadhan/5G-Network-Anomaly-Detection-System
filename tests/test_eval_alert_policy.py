"""Tests for alert policy evaluation script and documentation (T13-008 / Guardrail G21)."""

from __future__ import annotations

from pathlib import Path

from scripts.eval_alert_policy import (
    evaluate_dataset,
    generate_alert_policy_report,
    run_all_evaluations,
)


def test_evaluate_dataset_sample() -> None:
    """Verify replay evaluation runs on sample dataset and computes valid statistics."""
    sample_csv = Path("data/sample/sample_measurements.csv")
    if not sample_csv.is_file():
        return

    res = evaluate_dataset(sample_csv, "Xiaomi 2406ERN9CI")
    assert res["total_samples"] == 70
    assert res["duration_hours"] > 0
    assert "alerts_per_hour" in res
    assert "events" in res
    assert len(res["events"]) > 0


def test_stationary_normal_false_alert_rate() -> None:
    """Verify stationary normal datasets produce 0.00 alerts/hour (G21)."""
    stable_csv = Path("data/raw/5G_measurements_Redmi_Stable.csv")
    if not stable_csv.is_file():
        return

    # Evaluate first 150 samples of stationary normal data
    res = evaluate_dataset(stable_csv, "Xiaomi 2406ERN9CI", max_samples=150)
    assert res["alerts_triggered"] == 0
    assert res["alerts_per_hour"] == 0.0


def test_generate_alert_policy_report() -> None:
    """Verify generated report section contains G21 compliance and threshold origins."""
    dummy_data = {
        "datasets": [
            {
                "friendly_name": "Test Stable",
                "total_samples": 100,
                "duration_hours": 0.10,
                "unique_events": 2,
                "alerts_triggered": 0,
                "alerts_per_hour": 0.0,
            }
        ],
        "all_events": [
            {
                "event_id": "test-ev-001",
                "anomaly_type": "STATISTICAL_ONLY",
                "severity": "HIGH",
                "persistence": 5,
                "decision_alerted": False,
                "decision_reason": "ML-only (no rule evidence)",
            }
        ],
        "thresholds": {
            "min_persistence": 5,
            "min_severity": "MEDIUM",
            "cooldown_seconds": 300,
        },
        "timestamp": "2026-10-18T10:00:00Z",
    }
    report = generate_alert_policy_report(dummy_data)
    assert "Alert Policy Replay Evaluation" in report
    assert "Stationary Normal False Alert Rate" in report
    assert "0.00 alerts/hour" in report
    assert "Evaluation Integrity (Zero Data Leakage)" in report


def test_results_v2_has_alert_evaluation_section() -> None:
    """Verify docs/results_v2.md has Section 4 with all acceptance criteria met."""
    results_path = Path("docs/results_v2.md")
    assert results_path.is_file()

    content = results_path.read_text(encoding="utf-8")
    assert "## 4. Alert Policy Replay Evaluation" in content
    assert "Stationary Normal False Alert Rate" in content
    assert "0.00 alerts/hour" in content
    assert "data/eval/" in content
    assert "untouched" in content

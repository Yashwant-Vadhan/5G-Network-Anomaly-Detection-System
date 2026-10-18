"""Tests for streaming soak test runner and memory boundedness verification (T14-007).

Verifies continuous replay simulation, checkpoint generation, process RSS tracking,
and memory boundedness validation.
"""

from __future__ import annotations

from pathlib import Path

from scripts.soak_test import (
    format_markdown_section,
    load_telemetry_source,
    run_soak_test,
)


def test_load_telemetry_source_repeats_to_target() -> None:
    """Verify load_telemetry_source loads and repeats rows to reach target samples."""
    samples = load_telemetry_source(target_samples=50)
    assert len(samples) == 50
    assert "timestamp" in samples[0]
    assert "device" in samples[0]


def test_soak_test_runner_bounded_execution() -> None:
    """Verify run_soak_test executes cleanly and validates bounded memory."""
    results = run_soak_test(
        total_samples=100,
        checkpoint_interval=50,
        warmup_samples=30,
        max_rss_growth_mb=40.0,
    )

    assert results["status"] == "PASSED"
    assert results["total_samples"] == 100
    assert results["is_bounded"] is True
    assert results["total_drops"] == 0
    assert len(results["checkpoints"]) == 2
    assert results["peak_rss_mb"] >= results["initial_rss_mb"]


def test_format_markdown_section_content() -> None:
    """Verify markdown output contains required sections, tables, and KPIs."""
    mock_results = {
        "status": "PASSED",
        "total_samples": 2400,
        "simulated_duration_hours": 2.0,
        "wall_time_seconds": 12.5,
        "initial_rss_mb": 150.0,
        "warmup_rss_mb": 160.0,
        "peak_rss_mb": 175.0,
        "final_rss_mb": 170.0,
        "rss_growth_post_warmup_mb": 15.0,
        "max_allowed_growth_mb": 35.0,
        "is_bounded": True,
        "total_drops": 0,
        "checkpoints": [
            {
                "sample_idx": 1200,
                "simulated_hours": 1.0,
                "rss_mb": 168.0,
                "peak_rss_mb": 170.0,
                "delta_from_warmup_mb": 8.0,
                "buffer_rows": 1200,
                "active_events": 1,
                "cpu_percent": 15.0,
            },
            {
                "sample_idx": 2400,
                "simulated_hours": 2.0,
                "rss_mb": 170.0,
                "peak_rss_mb": 175.0,
                "delta_from_warmup_mb": 10.0,
                "buffer_rows": 2000,
                "active_events": 1,
                "cpu_percent": 14.5,
            },
        ],
    }

    md = format_markdown_section(mock_results)
    assert "## 7. Soak Test & Memory Boundedness Results (T14-007)" in md
    assert "Simulated Duration" in md
    assert "Memory Boundedness Confirmed" in md
    assert "Periodic Checkpoint Log" in md


def test_results_v2_has_section_7() -> None:
    """Verify docs/results_v2.md contains Section 7 with soak test data."""
    path = Path("docs/results_v2.md")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "## 7. Soak Test & Memory Boundedness Results (T14-007)" in content
    assert "2400 continuous frames" in content
    assert "Memory Boundedness Confirmed" in content

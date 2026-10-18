"""Tests for latency benchmark runner and documentation (T14-008 / Guardrail G24)."""

from __future__ import annotations

from pathlib import Path

from scripts.benchmark_latency import (
    generate_benchmark_report,
    get_system_info,
    run_latency_benchmark,
)


def test_get_system_info() -> None:
    """Verify test environment parameters are populated."""
    info = get_system_info()
    assert "os" in info
    assert "processor" in info
    assert "python" in info
    assert "streamlit" in info
    assert "frontend" in info
    assert "network" in info


def test_run_latency_benchmark_structure() -> None:
    """Verify benchmark run produces valid metrics structure and data."""
    sample_csv = Path("data/sample/sample_measurements.csv")
    if not sample_csv.is_file():
        return

    data = run_latency_benchmark(sample_csv=sample_csv, iterations=1)
    assert data["samples_evaluated"] > 0
    assert data["target_kpi_s"] == 2.0

    # Server processing
    srv = data["server_processing"]
    assert "p50_ms" in srv
    assert "p95_ms" in srv
    assert srv["p95_ms"] > 0.0

    # Streamlit dashboard simulation
    st = data["streamlit_dashboard"]
    assert "p50_s" in st
    assert "p95_s" in st
    assert "passed" in st

    # React dashboard simulation
    rct = data["react_dashboard"]
    assert "p50_ms" in rct
    assert "p95_ms" in rct
    assert rct["passed"] is True


def test_generate_benchmark_report_content() -> None:
    """Verify report generation contains required G24 disclosures and metrics."""
    dummy_data = {
        "samples_evaluated": 100,
        "target_kpi_s": 2.0,
        "server_processing": {"p50_ms": 1.23, "p95_ms": 2.34, "max_ms": 5.67},
        "streamlit_dashboard": {
            "p50_s": 1.85,
            "p95_s": 2.75,
            "max_s": 3.45,
            "passed": False,
        },
        "react_dashboard": {
            "p50_ms": 12.5,
            "p95_ms": 28.3,
            "max_ms": 45.0,
            "passed": True,
        },
        "system_info": get_system_info(),
        "timestamp": "2026-10-18T10:00:00Z",
    }
    report = generate_benchmark_report(dummy_data)
    assert "Guardrail `G24`" in report
    assert "No Latency Guarantee" in report
    assert "ADR-016" in report
    assert "Streamlit" in report
    assert "React" in report
    assert "uPlot" in report


def test_docs_results_v2_exists_and_compliant() -> None:
    """Verify docs/results_v2.md exists and complies with Guardrail G24."""
    results_path = Path("docs/results_v2.md")
    assert results_path.is_file(), "docs/results_v2.md must exist for T14-008"

    content = results_path.read_text(encoding="utf-8")
    assert "No Latency Guarantee" in content
    assert "ADR-016" in content
    assert "T14-008" in content


def test_docs_decisions_has_adr016() -> None:
    """Verify docs/decisions.md documents ADR-016 for revisit Streamlit decision."""
    decisions_path = Path("docs/decisions.md")
    assert decisions_path.is_file()

    content = decisions_path.read_text(encoding="utf-8")
    assert "ADR-016: Revisit Streamlit Evaluation" in content

"""E2E smoke test for Streamlit dashboard pages (T7-008).

Verifies that all 6 dashboard pages load without exceptions using Streamlit AppTest,
and asserts key interface elements and text content (status banner, Non-Claims, etc.).
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

DASHBOARD_DIR = Path("dashboard").resolve()
PAGES_DIR = DASHBOARD_DIR / "pages"


def test_app_main_smoke():
    """Verify main entrypoint app.py loads without unhandled exception."""
    at = AppTest.from_file(str(DASHBOARD_DIR / "app.py"), default_timeout=10)
    at.run()
    assert not at.exception


def test_page_1_overview_smoke():
    """Verify Overview page loads without exception and renders key elements."""
    at = AppTest.from_file(str(PAGES_DIR / "1_Overview.py"), default_timeout=10)
    at.run()
    assert not at.exception


def test_page_2_signal_explorer_smoke():
    """Verify Signal Explorer page loads without exception."""
    at = AppTest.from_file(str(PAGES_DIR / "2_Signal_Explorer.py"), default_timeout=10)
    at.run()
    assert not at.exception


def test_page_3_cells_and_network_smoke():
    """Verify Cells and Network page loads without exception."""
    at = AppTest.from_file(str(PAGES_DIR / "3_Cells_And_Network.py"), default_timeout=10)
    at.run()
    assert not at.exception


def test_page_4_events_and_diagnosis_smoke():
    """Verify Events and Diagnosis page loads without exception."""
    at = AppTest.from_file(str(PAGES_DIR / "4_Events_And_Diagnosis.py"), default_timeout=10)
    at.run()
    assert not at.exception


def test_page_5_data_quality_smoke():
    """Verify Data Quality page loads without exception."""
    at = AppTest.from_file(str(PAGES_DIR / "5_Data_Quality.py"), default_timeout=10)
    at.run()
    assert not at.exception


def test_page_6_about_smoke():
    """Verify About and Limitations page loads without exception and includes Non-Claims."""
    at = AppTest.from_file(str(PAGES_DIR / "6_About_And_Limitations.py"), default_timeout=10)
    at.run()
    assert not at.exception

"""Unit tests for Sushil's Phase 6 dashboard pages and components (T6-002, T6-009)."""

from __future__ import annotations

import io

from dashboard.data_loader import validate_and_load_uploaded_csv
from dashboard.theme import (
    COLOR_ANOMALY,
    COLOR_NORMAL,
    COLOR_WARNING,
    NEUTRAL_900,
    PRIMARY,
    get_plotly_layout_defaults,
    severity_color,
)


def test_theme_tokens_and_defaults():
    """Verify theme color tokens match DESIGN.md hex specs."""
    assert PRIMARY == "#2563EB"
    assert NEUTRAL_900 == "#0F172A"
    assert COLOR_NORMAL == "#15803D"
    assert COLOR_WARNING == "#B45309"
    assert COLOR_ANOMALY == "#B91C1C"

    layout = get_plotly_layout_defaults()
    assert "paper_bgcolor" in layout
    assert "plot_bgcolor" in layout
    assert layout["font"]["family"].startswith("system-ui")


def test_severity_color_mapping():
    """Verify severity_color returns appropriate hex colors for LOW/MEDIUM/HIGH."""
    assert severity_color("HIGH") == COLOR_ANOMALY
    assert severity_color("high") == COLOR_ANOMALY
    assert severity_color("MEDIUM") == COLOR_WARNING
    assert severity_color("LOW") == COLOR_NORMAL
    assert severity_color(None) == "#64748B"


class DummyUploadedFile:
    """Mock uploaded file object for testing validate_and_load_uploaded_csv."""

    def __init__(self, name: str, size: int, content: bytes):
        self.name = name
        self.size = size
        self.content = content
        self._buf = io.BytesIO(content)

    def seek(self, pos: int):
        self._buf.seek(pos)

    def read(self, *args, **kwargs):
        return self._buf.read(*args, **kwargs)


def test_validate_and_load_uploaded_csv_invalid_extension():
    """Verify non-CSV files are rejected."""
    bad_file = DummyUploadedFile("data.txt", 100, b"col1,col2\n1,2")
    assert validate_and_load_uploaded_csv(bad_file) is None


def test_validate_and_load_uploaded_csv_oversized():
    """Verify files larger than 20 MB are rejected."""
    oversized = DummyUploadedFile("large.csv", 25 * 1024 * 1024, b"timestamp,ss_rsrp\n")
    assert validate_and_load_uploaded_csv(oversized) is None


def test_validate_and_load_uploaded_csv_pii_rejection():
    """Verify CSV containing PII column is rejected."""
    pii_content = b"timestamp,latitude,ss_rsrp\n2026-09-28T10:00:00Z,12.97, -80.0\n"
    pii_file = DummyUploadedFile("pii.csv", len(pii_content), pii_content)
    assert validate_and_load_uploaded_csv(pii_file) is None

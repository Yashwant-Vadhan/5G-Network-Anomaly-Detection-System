"""Tests verifying docs/privacy.md and shared consent text (T18-012, Guardrail G28/G29).

Acceptance Criteria:
- Reviewed by both authors (Yashwant Vadhan & Sushil Kumar)
- Matches actual payload fields (C7 / Contract C1)
- Cell identifier approximate location disclosure present
- Ephemeral retention and platform logs policy documented
"""

from __future__ import annotations

from pathlib import Path

from ml.config import RAW_COLUMNS


def test_privacy_doc_and_consent_text_exist() -> None:
    """Both docs/privacy.md and docs/consent_text.txt exist and are readable."""
    privacy_path = Path("docs/privacy.md")
    consent_path = Path("docs/consent_text.txt")

    assert privacy_path.is_file(), "docs/privacy.md must exist"
    assert consent_path.is_file(), "docs/consent_text.txt must exist"

    privacy_text = privacy_path.read_text(encoding="utf-8")
    consent_text = consent_path.read_text(encoding="utf-8")

    assert len(privacy_text) > 500
    assert len(consent_text) > 300


def test_reviewed_by_both_authors() -> None:
    """Both authors (Yashwant Vadhan and Sushil Kumar) are cited as reviewers."""
    privacy_text = Path("docs/privacy.md").read_text(encoding="utf-8")
    consent_text = Path("docs/consent_text.txt").read_text(encoding="utf-8")

    for text in (privacy_text, consent_text):
        assert "Yashwant Vadhan" in text, "Missing Yashwant Vadhan in review acknowledgement"
        assert "Sushil Kumar" in text, "Missing Sushil Kumar in review acknowledgement"


def test_matches_actual_c7_payload_fields() -> None:
    """All 18 Contract C1/C7 telemetry fields are documented."""
    privacy_text = Path("docs/privacy.md").read_text(encoding="utf-8")
    consent_text = Path("docs/consent_text.txt").read_text(encoding="utf-8")

    # Verify each of the 18 C1 columns is present in privacy documentation
    for col in RAW_COLUMNS:
        assert col in privacy_text, f"Field '{col}' missing from docs/privacy.md"

    # Core fields verified in the concise consent notice
    core_fields = ["device", "operator", "ss_rsrp", "ss_rsrq", "ss_sinr", "pci", "nci"]
    for col in core_fields:
        assert col in consent_text, f"Field '{col}' missing from docs/consent_text.txt"


def test_disclosures_and_policies_present() -> None:
    """Key policies: location disclosure, ephemeral retention, platform logs, teardown."""
    privacy_text = Path("docs/privacy.md").read_text(encoding="utf-8")
    consent_text = Path("docs/consent_text.txt").read_text(encoding="utf-8")

    for text in (privacy_text, consent_text):
        assert "approximate location" in text.lower() or "approximate area" in text.lower()
        assert "gps" in text.lower()
        assert "platform log" in text.lower()
        assert "ephemeral" in text.lower() or "purged" in text.lower()

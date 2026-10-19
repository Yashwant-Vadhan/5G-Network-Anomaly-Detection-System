"""Tests for streaming security specification document (T14-004)."""

from __future__ import annotations

from pathlib import Path

SECURITY_DOC_PATH = Path("docs/streaming_security.md")


def test_streaming_security_doc_exists() -> None:
    """Verify docs/streaming_security.md exists and is non-empty."""
    assert SECURITY_DOC_PATH.is_file(), "docs/streaming_security.md must exist"
    content = SECURITY_DOC_PATH.read_text(encoding="utf-8")
    assert len(content.strip()) > 500


def test_streaming_security_doc_sections() -> None:
    """Verify all required security topics and architectural boundaries are documented."""
    content = SECURITY_DOC_PATH.read_text(encoding="utf-8")

    # Threat model
    assert "Threat Model" in content
    assert "Passive LAN Eavesdropper" in content

    # Token handling
    assert "NADS_INGEST_TOKEN" in content
    assert "compare_digest" in content

    # Bind policy
    assert "--allow-lan" in content
    assert "127.0.0.1" in content
    assert "NADS_ALLOW_REMOTE_VIEW" in content

    # TLS & Third-party behavior verification
    assert "Uvicorn SSL" in content
    assert "--ssl-keyfile" in content
    assert "Android Cleartext Traffic" in content
    assert "network-security-config" in content

    # Known limitations stated plainly
    assert "Known Limitations" in content
    assert "Single Shared Ingest Token" in content
    assert "No Per-Device Revocation" in content


def test_streaming_security_doc_line_lengths() -> None:
    """Verify strict adherence to <= 100 characters per line."""
    lines = SECURITY_DOC_PATH.read_text(encoding="utf-8").splitlines()
    violations = [
        (idx + 1, len(line), line[:40]) for idx, line in enumerate(lines) if len(line) > 100
    ]
    assert not violations, f"Line length violations found: {violations}"

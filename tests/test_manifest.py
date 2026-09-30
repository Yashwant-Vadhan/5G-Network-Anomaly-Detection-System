"""Unit tests for scripts/make_manifest.py (T2-004)."""

from __future__ import annotations

from pathlib import Path

from scripts.make_manifest import generate_manifest, verify_manifest


def test_generate_and_verify_manifest(tmp_path: Path) -> None:
    """Generating a manifest for 2 CSV files and verifying should succeed."""
    file1 = tmp_path / "sample_a.csv"
    file2 = tmp_path / "sample_b.csv"

    file1.write_text("timestamp,device,ss_rsrp\n2026-09-30T12:00:00Z,redmi,-85\n", encoding="utf-8")
    file2.write_text("timestamp,device,ss_rsrp\n2026-09-30T12:00:03Z,redmi,-88\n", encoding="utf-8")

    manifest_path = generate_manifest(tmp_path)
    assert manifest_path.is_file()

    content = manifest_path.read_text(encoding="utf-8")
    assert "sample_a.csv" in content
    assert "sample_b.csv" in content

    # Verify manifest returns True
    assert verify_manifest(tmp_path) is True


def test_verify_manifest_detects_tampered_file(tmp_path: Path) -> None:
    """Modifying one byte in a CSV file should cause verify_manifest to fail."""
    file1 = tmp_path / "data1.csv"
    file1.write_text("initial content", encoding="utf-8")

    generate_manifest(tmp_path)
    assert verify_manifest(tmp_path) is True

    # Tamper with file
    file1.write_text("tampered content", encoding="utf-8")

    assert verify_manifest(tmp_path) is False


def test_verify_manifest_detects_missing_file(tmp_path: Path) -> None:
    """Removing a file listed in the manifest should cause verify_manifest to fail."""
    file1 = tmp_path / "data1.csv"
    file1.write_text("initial content", encoding="utf-8")

    generate_manifest(tmp_path)
    file1.unlink()

    assert verify_manifest(tmp_path) is False

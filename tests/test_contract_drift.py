"""Tests for contract examples and drift detection (T10-008)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.export_contract_examples import FIXTURES_DIR, export_examples


def test_fixtures_directory_contains_schemas_and_examples():
    """All 27 schemas and golden examples must be present in tests/fixtures/stream/."""
    assert FIXTURES_DIR.exists()
    schemas = list(FIXTURES_DIR.glob("*.schema.json"))
    examples = list(FIXTURES_DIR.glob("*.example.json"))

    assert len(schemas) >= 27
    assert len(examples) >= 27

    # Ensure C7 ingest sample fixture exists with collector timestamp format
    c7_sample = FIXTURES_DIR / "c7_ingest_sample.example.json"
    assert c7_sample.exists()
    data = json.loads(c7_sample.read_text(encoding="utf-8"))
    assert data["type"] == "sample"
    assert "timestamp" in data["payload"]
    assert "seq" in data


def test_drift_check_passes_when_synced():
    """export_contract_examples.py --check exits with code 0 when files are in sync."""
    result = subprocess.run(
        [sys.executable, "scripts/export_contract_examples.py", "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "OK:" in result.stdout


def test_drift_check_detects_deliberate_tampering(tmp_path: Path):
    """export_contract_examples.py --check exits with code 1 if a fixture is modified."""
    # Run export into temporary directory
    ret = export_examples(check_mode=False, output_dir=tmp_path)
    assert ret == 0

    # Modify one schema file deliberately
    target = tmp_path / "c7_ack.schema.json"
    assert target.exists()
    target.write_text('{"tampered": true}\n', encoding="utf-8")

    # Drift check must fail
    ret_tampered = export_examples(check_mode=True, output_dir=tmp_path)
    assert ret_tampered == 1


def test_kotlin_client_readable_fixtures():
    """Contract C7 golden fixtures can be read as standard JSON without Python-specific types."""
    c7_files = list(FIXTURES_DIR.glob("c7_*.example.json"))
    assert len(c7_files) >= 9

    for f in c7_files:
        content = f.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)
        assert "type" in parsed
        # Verify timestamps are ISO strings or strings
        for k, v in parsed.items():
            if "time" in k:
                assert isinstance(v, str)

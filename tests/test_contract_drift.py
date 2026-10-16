"""Tests for contract examples and drift detection (T10-008)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.export_contract_examples import FIXTURES_DIR, TYPES_DIR, export_examples


def test_fixtures_directory_contains_schemas_and_examples():
    """All 28 schemas and golden examples must be present in tests/fixtures/stream/."""
    assert FIXTURES_DIR.exists()
    schemas = list(FIXTURES_DIR.glob("*.schema.json"))
    examples = list(FIXTURES_DIR.glob("*.example.json"))

    assert len(schemas) >= 28
    assert len(examples) >= 28

    # Ensure C7 ingest sample fixture exists with collector timestamp format
    c7_sample = FIXTURES_DIR / "c7_ingest_sample.example.json"
    assert c7_sample.exists()
    data = json.loads(c7_sample.read_text(encoding="utf-8"))
    assert data["type"] == "sample"
    assert "timestamp" in data["payload"]
    assert "seq" in data

    # Ensure C11 demo bundle fixture exists
    c11_bundle = FIXTURES_DIR / "c11_demo_bundle.example.json"
    assert c11_bundle.exists()


def test_typescript_types_exist_and_current():
    """TypeScript contract definitions exist and are non-empty."""
    assert TYPES_DIR.exists()
    ts_file = TYPES_DIR / "contracts.ts"
    index_file = TYPES_DIR / "index.ts"

    assert ts_file.exists()
    assert index_file.exists()

    content = ts_file.read_text(encoding="utf-8")
    assert "export interface DemoBundle" in content
    assert "export interface ScoredSample" in content
    assert "export interface EventRecord" in content


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
    """export_contract_examples.py --check exits with code 1 if a fixture or TS is modified."""
    tmp_fixtures = tmp_path / "fixtures"
    tmp_types = tmp_path / "types"

    # Run export into temporary directory
    ret = export_examples(check_mode=False, output_dir=tmp_fixtures, types_dir=tmp_types)
    assert ret == 0

    # Modify one schema file deliberately
    target = tmp_fixtures / "c7_ack.schema.json"
    assert target.exists()
    target.write_text('{"tampered": true}\n', encoding="utf-8")

    # Drift check must fail
    ret_tampered = export_examples(check_mode=True, output_dir=tmp_fixtures, types_dir=tmp_types)
    assert ret_tampered == 1

    # Reset schema file and tamper TypeScript file
    export_examples(check_mode=False, output_dir=tmp_fixtures, types_dir=tmp_types)
    ts_target = tmp_types / "contracts.ts"
    assert ts_target.exists()
    ts_target.write_text("// tampered", encoding="utf-8")
    ret_ts_tampered = export_examples(check_mode=True, output_dir=tmp_fixtures, types_dir=tmp_types)
    assert ret_ts_tampered == 1


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

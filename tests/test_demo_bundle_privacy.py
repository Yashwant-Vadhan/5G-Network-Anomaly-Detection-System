"""Tests for demo bundle cell-ID anonymisation and privacy guardrails (G27, T16-003)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from scripts.build_demo_bundle import build_bundle


def ensure_processed_sources() -> None:
    """Ensure data/processed artifacts exist for tests, generating from sample if absent."""
    scores_path = Path("data/processed/scores.csv")
    if not scores_path.exists():
        from pipelines.run_pipeline import run_pipeline

        run_pipeline(
            input_dir=Path("data/sample"), output_dir=Path("data/processed"), retrain=False
        )


def test_public_bundle_contains_no_raw_cell_ids():
    """Guardrail G27: Public bundle must not contain real cell identifiers."""
    ensure_processed_sources()
    bundle = build_bundle(source="processed", is_public=True)

    # 1. Check samples columns
    pci_idx = bundle["samples"]["columns"].index("pci")
    nci_idx = bundle["samples"]["columns"].index("nci")

    # In public bundle, pci and nci are string labels (Cell-*, NCI-*) or None
    for row in bundle["samples"]["rows"]:
        pci_val = row[pci_idx]
        nci_val = row[nci_idx]
        if pci_val is not None:
            assert isinstance(pci_val, str)
            assert pci_val.startswith("Cell-")
        if nci_val is not None:
            assert isinstance(nci_val, str)
            assert nci_val.startswith("NCI-")

    # 2. Check transitions
    for t in bundle["transitions"]:
        if t["type"] == "PCI":
            assert t["from"].startswith("Cell-")
            assert t["to"].startswith("Cell-")

    # 3. Check privacy metadata
    assert bundle["privacy"]["cell_ids"] == "hashed"
    assert "cell_lookup" in bundle["privacy"]
    assert len(bundle["privacy"]["cell_lookup"]) > 0

    # 4. Check raw real NCIs from scores.csv do not leak
    scores_df = pd.read_csv("data/processed/scores.csv")
    raw_ncis = [str(int(x)) for x in scores_df["nci"].dropna().unique() if len(str(int(x))) > 5]
    import json

    bundle_str = json.dumps(bundle)
    for raw_nci in raw_ncis:
        assert raw_nci not in bundle_str, f"Leaked raw NCI {raw_nci} in public bundle!"


def test_transition_parity_between_hashed_and_unhashed():
    """Cell change events and counts must be identical between raw and hashed bundles."""
    ensure_processed_sources()
    b_pub = build_bundle(source="processed", is_public=True)
    b_raw = build_bundle(source="processed", is_public=False)

    assert len(b_pub["transitions"]) == len(b_raw["transitions"])
    assert [t["ts"] for t in b_pub["transitions"]] == [t["ts"] for t in b_raw["transitions"]]
    assert [t["type"] for t in b_pub["transitions"]] == [t["type"] for t in b_raw["transitions"]]
    assert [t["session_id"] for t in b_pub["transitions"]] == [
        t["session_id"] for t in b_raw["transitions"]
    ]


def test_public_and_raw_cell_ids_mutual_exclusion():
    """G27: --public and --raw-cell-ids together must exit code 2 with fix hint."""
    cmd = [sys.executable, "scripts/build_demo_bundle.py", "--public", "--raw-cell-ids"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 2
    assert "Cannot use --raw-cell-ids with --public" in res.stderr
    assert "Fix:" in res.stderr

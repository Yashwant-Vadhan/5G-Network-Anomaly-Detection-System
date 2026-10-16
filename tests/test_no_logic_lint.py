"""Tests enforcing rule G30: Frontend contains no scoring, transition, or event logic (T16-020).

Frontend code must act solely as a presentation and exploration layer. All statistical
scoring, anomaly classification, transition detection, and event lifecycle logic must
remain exclusively on the backend / Python pipeline.

Allowed operations:
- Data fetching / loading (REST, WS, Demo Bundle)
- Filtering and searching (by device, operator, severity, etc.)
- Sorting (by timestamp, sequence number, etc.)
- Formatting and presentation (timestamps, units, rounding)
- Visualization and plotting (charts, tables, badges)

Forbidden operations (checked by denylist):
- Isolation Forest scoring or inference
- Rolling statistics and baseline z-score computations
- Handover or PCI/NCI transition detection
- Event grouping, boundary detection, or gap closure
- Anomaly type classification or severity evaluation
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

# Forbidden tokens / identifiers representing backend logic in frontend code.
FORBIDDEN_IDENTIFIERS = [
    # Isolation Forest & ML scoring
    r"\bisolation_?forest\b",
    r"\bcompute_?if_?score\b",
    r"\bcalculate_?if_?score\b",
    r"\bdecision_function\b",
    r"\bpredict_proba\b",
    # Statistical / rolling / z-score computations
    r"\bcompute_?z_?score\b",
    r"\bcalculate_?z_?score\b",
    r"\bcompute_?rolling\b",
    r"\bcalculate_?rolling\b",
    r"\bcalc_?rolling\b",
    r"\brollingMean\b",
    r"\brollingStd\b",
    # Transition detection
    r"\bdetect_?transitions?\b",
    r"\bdetectTransitions?\b",
    r"\bdetect_?handovers?\b",
    r"\bdetectHandovers?\b",
    r"\bcompute_?transitions?\b",
    r"\bcomputeTransitions?\b",
    # Event grouping and classification
    r"\bgroup_?events?\b",
    r"\bgroupEvents?\b",
    r"\bdetect_?events?\b",
    r"\bdetectEvents?\b",
    r"\bclassify_?anomal(?:y|ies)\b",
    r"\bclassifyAnomal(?:y|ies)\b",
    r"\bassign_?severity\b",
    r"\bassignSeverity\b",
    # Diagnostic generation
    r"\bdiagnose_?events?\b",
    r"\bdiagnoseEvents?\b",
    r"\bgenerate_?diagnosis\b",
    r"\bgenerateDiagnosis\b",
]

COMPILED_FORBIDDEN_PATTERNS = [
    (pattern, re.compile(pattern, re.IGNORECASE)) for pattern in FORBIDDEN_IDENTIFIERS
]


def scan_directory_for_forbidden_logic(
    directory: Path,
    exclude_files: set[str] | None = None,
) -> list[str]:
    """Scan TypeScript/JavaScript source files for forbidden computational logic."""
    if exclude_files is None:
        exclude_files = set()

    violations: list[str] = []
    extensions = {".ts", ".tsx", ".js", ".jsx"}

    for path in directory.rglob("*"):
        if path.is_file() and path.suffix in extensions:
            if path.name in exclude_files or any(part.endswith(".test.ts") for part in path.parts):
                continue
            if any(part.endswith(".test.tsx") for part in path.parts):
                continue

            content = path.read_text(encoding="utf-8")
            for raw_pattern, regex in COMPILED_FORBIDDEN_PATTERNS:
                matches = regex.findall(content)
                if matches:
                    violations.append(
                        f"Forbidden identifier '{matches[0]}' (rule {raw_pattern}) found in {path}"
                    )

    return violations


def test_frontend_src_contains_no_backend_logic():
    """Ensure frontend/src contains no forbidden computational or ML identifiers."""
    assert FRONTEND_SRC.exists(), f"Frontend source path missing: {FRONTEND_SRC}"

    # contracts.ts defines interface types with field names (e.g. if_score), so we
    # scan all executable code outside contract schema definitions.
    violations = scan_directory_for_forbidden_logic(
        FRONTEND_SRC,
        exclude_files={"contracts.ts", "setupTests.ts"},
    )
    assert not violations, "Rule G30 violations detected:\n" + "\n".join(violations)


def test_no_logic_lint_fails_on_forbidden_identifier(tmp_path: Path):
    """The lint must detect and fail when forbidden computational logic is added."""
    dummy_code = """
    // Attempting to calculate handover transitions client-side
    export function detectTransitions(samples: any[]) {
        const transitions = [];
        for (let i = 1; i < samples.length; i++) {
            if (samples[i].pci !== samples[i-1].pci) {
                transitions.push({ index: i });
            }
        }
        return transitions;
    }
    """
    test_file = tmp_path / "handover_logic.ts"
    test_file.write_text(dummy_code, encoding="utf-8")

    violations = scan_directory_for_forbidden_logic(tmp_path)
    assert len(violations) >= 1
    assert any("detectTransitions" in v for v in violations)


def test_no_logic_lint_fails_on_ml_scoring(tmp_path: Path):
    """The lint must detect and fail when ML scoring functions are added."""
    dummy_code = """
    export function compute_if_score(sample: any): number {
        return sample.ss_rsrp < -100 ? 0.8 : 0.2;
    }
    """
    test_file = tmp_path / "scoring.ts"
    test_file.write_text(dummy_code, encoding="utf-8")

    violations = scan_directory_for_forbidden_logic(tmp_path)
    assert len(violations) >= 1
    assert any("compute_if_score" in v for v in violations)

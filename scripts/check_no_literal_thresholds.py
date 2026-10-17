#!/usr/bin/env python3
"""Check that no numeric threshold literals exist in streaming/ outside config.

Guardrail check for T10-009 and v2 Coding Standards.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Known threshold literal values that MUST come from config
CONFIG_THRESHOLDS = {
    50000: "SESSION_MAX_ROWS",
    600: "SESSION_RESUME_WINDOW_SECONDS",
    8192: "MAX_MESSAGE_BYTES",
    300: "ALERT_COOLDOWN_SECONDS",
}


def check_file(path: Path) -> list[str]:
    """Check a single python file for hardcoded threshold literals."""
    errors = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        return [f"{path}: could not parse ({exc})"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            # Disallow hardcoded values matching known thresholds
            if node.value in CONFIG_THRESHOLDS:
                const_name = CONFIG_THRESHOLDS[node.value]
                errors.append(
                    f"{path}:{node.lineno}: Hardcoded literal {node.value} found. "
                    f"Use ml.config.{const_name} instead."
                )
    return errors


def main() -> int:
    streaming_dir = Path("streaming")
    if not streaming_dir.exists():
        return 0

    all_errors = []
    for py_file in streaming_dir.rglob("*.py"):
        if py_file.name == "config.py":
            continue
        all_errors.extend(check_file(py_file))

    if all_errors:
        print("Literal threshold errors found in streaming/:", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print("Check passed: No numeric threshold literals found in streaming/ outside config.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

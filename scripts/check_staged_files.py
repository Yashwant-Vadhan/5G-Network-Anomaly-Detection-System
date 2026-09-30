"""Pre-commit guard: block raw data and oversized files from being committed.

todo.md T1-004 requires a hook that refuses files under `data/raw/` (other
than ``README.md`` and ``MANIFEST.sha256``) and files larger than 5 MB.  This
implements guardrail G7 ("preserve raw data") and the data-loss risk in the
``todo.md`` risk register.

Run directly (``python scripts/check_staged_files.py``) or via pre-commit with
``pass_filenames: false``, in which case the staged file list is read from git.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAW_PREFIX = "data/raw/"
RAW_ALLOWED = {
    "data/raw/README.md",
    "data/raw/meta.template.json",
    "data/raw/MANIFEST.sha256",
}
MAX_SIZE_BYTES = 5 * 1024 * 1024


def staged_files() -> list[str]:
    """Return paths staged for commit, forward-slashed, without the rename pair."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(f"could not read the git index: {result.stderr.strip()}")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def violations(files: list[str]) -> list[str]:
    """Return one human-readable message per blocked path."""
    problems: list[str] = []
    for name in files:
        if name.startswith(RAW_PREFIX) and name not in RAW_ALLOWED:
            problems.append(
                f"{name}: raw measurement data must not be committed (guardrail G7). "
                f"Keep it in {RAW_PREFIX} locally and manifest it with "
                f"`python scripts/make_manifest.py data/raw`."
            )
            continue
        path = Path(name)
        if path.is_file() and path.stat().st_size > MAX_SIZE_BYTES:
            size_mb = path.stat().st_size / (1024 * 1024)
            problems.append(f"{name}: {size_mb:.1f} MB exceeds the 5 MB commit limit.")
    return problems


def main() -> int:
    problems = violations(staged_files())
    if not problems:
        return 0
    for problem in problems:
        sys.stderr.write(f"BLOCKED {problem}\n")
    sys.stderr.write("Unstage the files above; raw data and large artifacts stay local.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate and verify SHA-256 checksum manifest for raw dataset files (T2-004).

Usage:
    python scripts/make_manifest.py data/raw
    python scripts/make_manifest.py data/raw --verify
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_manifest(raw_dir: Path) -> Path:
    """Generate or overwrite MANIFEST.sha256 for all CSV files in raw_dir."""
    if not raw_dir.is_dir():
        print(f"Error: Directory '{raw_dir}' does not exist.", file=sys.stderr)
        sys.exit(2)

    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        print(f"Warning: No CSV files found in '{raw_dir}'.", file=sys.stderr)

    manifest_path = raw_dir / "MANIFEST.sha256"
    lines: list[str] = []

    for csv_file in csv_files:
        checksum = compute_sha256(csv_file)
        lines.append(f"{checksum}  {csv_file.name}")

    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))

    print(f"Successfully generated manifest for {len(csv_files)} file(s) -> {manifest_path}")
    return manifest_path


def verify_manifest(raw_dir: Path) -> bool:
    """Verify MANIFEST.sha256 against actual CSV files in raw_dir.

    Returns True if all files exist and match checksums; False otherwise.
    """
    manifest_path = raw_dir / "MANIFEST.sha256"
    if not manifest_path.is_file():
        print(f"Error: Manifest file '{manifest_path}' not found.", file=sys.stderr)
        return False

    with open(manifest_path, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        print("Warning: Manifest file is empty.", file=sys.stderr)
        return True

    mismatches: list[str] = []

    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            mismatches.append(f"Invalid manifest entry format: '{line}'")
            continue

        expected_hash, filename = parts[0], parts[1]
        filepath = raw_dir / filename

        if not filepath.is_file():
            mismatches.append(f"Missing file: '{filename}'")
            continue

        actual_hash = compute_sha256(filepath)
        if actual_hash != expected_hash:
            mismatches.append(
                f"Checksum mismatch for '{filename}': expected {expected_hash}, got {actual_hash}"
            )

    if mismatches:
        print("MANIFEST VERIFICATION FAILED:", file=sys.stderr)
        for err in mismatches:
            print(f"  - {err}", file=sys.stderr)
        return False

    print(f"MANIFEST VERIFICATION SUCCESSFUL: All {len(lines)} file(s) match integrity hashes.")
    return True


def main() -> None:
    """CLI entry point for make_manifest.py."""
    parser = argparse.ArgumentParser(
        description="Generate or verify SHA-256 checksum manifest for raw dataset files."
    )
    parser.add_argument(
        "dir",
        type=Path,
        nargs="?",
        default=Path("data/raw"),
        help="Target directory containing raw CSV files (default: data/raw).",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing MANIFEST.sha256 against actual files on disk.",
    )

    args = parser.parse_args()

    if args.verify:
        success = verify_manifest(args.dir)
        sys.exit(0 if success else 1)
    else:
        generate_manifest(args.dir)
        sys.exit(0)


if __name__ == "__main__":
    main()

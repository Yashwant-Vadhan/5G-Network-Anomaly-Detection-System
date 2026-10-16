"""Append-only persistent file store for live session captures and alerts (T11-009).

Persists incoming telemetry to data/live/ in raw Contract C1 CSV format with accompanying
JSON metadata sidecars, generates SHA-256 integrity digests upon session completion,
and guards against any write targeting data/raw/ (Guardrails G7, G22).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ml.config import RAW_COLUMNS
from streaming.schema import SessionStatus, StreamSource

DEFAULT_LIVE_DIR = Path("data/live")


def sanitize_filename_token(token: str) -> str:
    """Sanitize identifiers to ensure safe filesystem filenames without path traversal."""
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", token)
    return cleaned.strip("._") or "unnamed"


def compute_sha256(file_path: Path) -> str:
    """Compute the SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class LiveCaptureStore:
    """Append-only storage for live session captures and metadata (Contract C1, T11-009).

    Each session creates:
    - `data/live/<client>_<session>_<YYYYMMDD>_<HHMM>.csv`: C1 format rows
    - `data/live/<client>_<session>_<YYYYMMDD>_<HHMM>.meta.json`: session sidecar
    """

    def __init__(
        self,
        client_id: str,
        session_id: str,
        base_dir: str | Path = DEFAULT_LIVE_DIR,
        source: StreamSource = "phone",
        start_time: datetime | str | None = None,
        initial_status: SessionStatus = "OPEN",
    ) -> None:
        self.client_id = client_id
        self.session_id = session_id
        self.source: StreamSource = source
        self.base_dir = Path(base_dir).resolve()

        # Enforce Guardrails G7 / G22: Never write to or under data/raw
        self._validate_path_safety(self.base_dir)

        # Parse or default start time
        if start_time is None:
            self._start_dt = datetime.now(UTC)
        elif isinstance(start_time, datetime):
            self._start_dt = start_time
        else:
            try:
                self._start_dt = datetime.fromisoformat(start_time)
            except ValueError:
                self._start_dt = datetime.now(UTC)

        ts_str = self._start_dt.strftime("%Y%m%d_%H%M")
        safe_client = sanitize_filename_token(self.client_id)
        safe_session = sanitize_filename_token(self.session_id)
        filename_prefix = f"{safe_client}_{safe_session}_{ts_str}"

        self.csv_path = self.base_dir / f"{filename_prefix}.csv"
        self.meta_path = self.base_dir / f"{filename_prefix}.meta.json"

        # Secondary path check after resolving full file paths
        self._validate_path_safety(self.csv_path)
        self._validate_path_safety(self.meta_path)

        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.status: SessionStatus = initial_status
        self.sample_count = 0
        self._file = None
        self._writer = None

        self._init_files()

    @staticmethod
    def _validate_path_safety(target_path: Path) -> None:
        """Enforce Guardrail G7/G22: Refuse any path under data/raw/."""
        resolved = target_path.resolve()
        parts = [p.lower() for p in resolved.parts]

        # Check if 'data' and 'raw' are consecutive path parts
        for i in range(len(parts) - 1):
            if parts[i] == "data" and parts[i + 1] == "raw":
                raise ValueError(
                    f"Refusing to write to data/raw/ (Guardrails G7/G22): {target_path}"
                )

    def _init_files(self) -> None:
        """Initialize CSV with Contract C1 header and create initial sidecar."""
        file_is_new = not self.csv_path.exists() or self.csv_path.stat().st_size == 0
        self._file = self.csv_path.open("a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)

        if file_is_new:
            self._writer.writerow(RAW_COLUMNS)
            self._file.flush()
            os.fsync(self._file.fileno())

        self._write_meta()

    def _write_meta(self, sha256_digest: str | None = None) -> None:
        """Write session sidecar metadata to disk and fsync."""
        meta_dict = {
            "client_id": self.client_id,
            "session_id": self.session_id,
            "source": self.source,
            "status": self.status,
            "sample_count": self.sample_count,
            "created_at": self._start_dt.isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "sha256": sha256_digest,
        }
        with self.meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

    def append_sample(self, sample: dict[str, Any] | BaseModel) -> None:
        """Append an accepted measurement sample in exact Contract C1 format."""
        if self.status == "CLOSED":
            raise RuntimeError(f"Cannot append to closed session: {self.session_id}")

        if isinstance(sample, BaseModel):
            data = sample.model_dump(mode="python")
        else:
            data = sample

        row = []
        for col in RAW_COLUMNS:
            val = data.get(col)
            if val is None:
                row.append("")
            elif isinstance(val, bool):
                row.append("True" if val else "False")
            else:
                row.append(str(val))

        self._writer.writerow(row)
        self.sample_count += 1
        self._file.flush()

    def flush(self) -> None:
        """Flush and fsync the CSV file to physical storage."""
        if self._file and not self._file.closed:
            self._file.flush()
            os.fsync(self._file.fileno())

    def mark_incomplete(self, reason: str | None = None) -> None:
        """Mark session as INCOMPLETE following an unexpected interruption or crash."""
        self.status = "INCOMPLETE"
        self.flush()
        if self._file and not self._file.closed:
            self._file.close()

        digest = compute_sha256(self.csv_path) if self.csv_path.exists() else None
        self._write_meta(sha256_digest=digest)

    def close(self, status: SessionStatus = "CLOSED") -> None:
        """Close capture file, fsync to disk, compute SHA-256, and finalize sidecar."""
        if self.status == "CLOSED":
            return

        self.status = status
        self.flush()
        if self._file and not self._file.closed:
            self._file.close()

        sha256_digest = compute_sha256(self.csv_path)
        self._write_meta(sha256_digest=sha256_digest)

    def __enter__(self) -> LiveCaptureStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is not None:
            self.mark_incomplete(reason=str(exc_val))
        else:
            if self.status != "CLOSED":
                self.close(status="CLOSED")

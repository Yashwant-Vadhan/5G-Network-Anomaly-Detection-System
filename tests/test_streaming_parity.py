"""Stream–batch parity tests (T11-006 / Guardrail G17).

Validates that the StreamingEngine produces identical anomaly detection
results as the batch ``ml.anomaly_analysis.detect()`` pipeline for the
same ordered input samples.

Numerical tolerance for ``if_score`` and ``baseline_z_max``: <= 1e-6.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.anomaly_analysis import detect
from ml.config import ANOMALY_TYPES
from ml.preprocessing import (
    add_missing_flags,
    add_sessions,
    coerce_numeric,
    flag_invalid,
    parse_timestamps,
)
from streaming.engine import StreamingEngine

TOLERANCE = 1e-6
SAMPLE_CSV = Path("data/sample/sample_measurements.csv")
SYNTHETIC_CSV = Path("tests/fixtures/edge_cases_synthetic.csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _preprocess(raw: pd.DataFrame, *, is_synthetic: bool = False) -> pd.DataFrame:
    """Run full batch preprocessing on a raw DataFrame."""
    valid_ts, _ = parse_timestamps(raw)
    coerced = coerce_numeric(valid_ts)
    flagged = flag_invalid(coerced)
    with_flags = add_missing_flags(flagged)
    sessionized = add_sessions(with_flags)
    if "is_synthetic" not in sessionized.columns:
        sessionized["is_synthetic"] = is_synthetic
    return sessionized


def _batch_detect_per_session(
    preprocessed: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Run ``detect()`` on each session independently."""
    out: dict[str, pd.DataFrame] = {}
    for sid in preprocessed["session_id"].unique():
        sdf = preprocessed[preprocessed["session_id"] == sid].reset_index(drop=True)
        scores, _ = detect(sdf)
        out[sid] = scores
    return out


def _sort_raw_by_timestamp(raw: pd.DataFrame) -> pd.DataFrame:
    """Sort raw rows by parsed timestamp to match batch ordering."""
    tmp = raw.copy()
    tmp["_ts"] = pd.to_datetime(tmp["timestamp"], format="mixed", dayfirst=True)
    return tmp.sort_values("_ts", kind="stable").drop(columns=["_ts"]).reset_index(drop=True)


def _stream_ordered(raw: pd.DataFrame) -> list:
    """Feed raw rows to a fresh StreamingEngine in order, return scored results."""
    engine = StreamingEngine()
    results = []
    for idx in range(len(raw)):
        row = raw.iloc[idx]
        scored = engine.process(
            {"seq": idx + 1, "payload": dict(row)},
            client_id=str(row["device"]),
        )
        results.append(scored)
    return results


def _assert_parity(b: pd.Series, s, label: str) -> None:
    """Assert flag / type / severity / score parity."""
    assert bool(b["baseline_flag"]) == bool(s.baseline_flag), (
        f"{label}: baseline_flag batch={b['baseline_flag']} stream={s.baseline_flag}"
    )
    assert bool(b["if_flag"]) == bool(s.if_flag), (
        f"{label}: if_flag batch={b['if_flag']} stream={s.if_flag}"
    )
    assert str(b["anomaly_type"]) == str(s.anomaly_type), (
        f"{label}: anomaly_type batch={b['anomaly_type']} stream={s.anomaly_type}"
    )
    assert str(b["severity"]) == str(s.severity), (
        f"{label}: severity batch={b['severity']} stream={s.severity}"
    )

    b_if, s_if = b.get("if_score"), s.if_score
    if pd.notna(b_if) and s_if is not None:
        assert abs(float(b_if) - float(s_if)) <= TOLERANCE, (
            f"{label}: if_score diff={abs(float(b_if) - float(s_if))}"
        )
    else:
        assert pd.isna(b_if) == (s_if is None), (
            f"{label}: if_score null mismatch batch={b_if} stream={s_if}"
        )

    b_z = float(b.get("baseline_z_max", 0.0))
    s_z = float(s.baseline_z_max) if s.baseline_z_max is not None else 0.0
    assert abs(b_z - s_z) <= TOLERANCE, f"{label}: baseline_z_max diff={abs(b_z - s_z)}"


# ---------------------------------------------------------------------------
# Tests: data/sample/sample_measurements.csv  (single device / session)
# ---------------------------------------------------------------------------


class TestSampleDataParity:
    """Full row-by-row parity on the real sample dataset."""

    def test_ordered_delivery(self):
        """G17: sample-by-sample ordered replay matches batch detect()."""
        raw = pd.read_csv(SAMPLE_CSV)
        preprocessed = _preprocess(raw)
        batch_scores, _ = detect(preprocessed)

        stream_results = _stream_ordered(raw)

        assert len(batch_scores) == len(stream_results)
        for i in range(len(batch_scores)):
            _assert_parity(batch_scores.iloc[i], stream_results[i], f"sample[{i}]")

    def test_chunked_delivery(self):
        """G17: delivery in groups of 5 produces identical results."""
        raw = pd.read_csv(SAMPLE_CSV)
        preprocessed = _preprocess(raw)
        batch_scores, _ = detect(preprocessed)

        engine = StreamingEngine()
        results: list = []
        for start in range(0, len(raw), 5):
            chunk = raw.iloc[start : start + 5]
            for global_idx, row in chunk.iterrows():
                scored = engine.process(
                    {"seq": int(global_idx) + 1, "payload": dict(row)},
                    client_id=str(row["device"]),
                )
                results.append(scored)

        assert len(batch_scores) == len(results)
        for i in range(len(batch_scores)):
            _assert_parity(batch_scores.iloc[i], results[i], f"chunk[{i}]")


# ---------------------------------------------------------------------------
# Tests: tests/fixtures/edge_cases_synthetic.csv  (multi-device / session)
# ---------------------------------------------------------------------------


class TestSyntheticFixtureParity:
    """Per-device, per-session parity on synthetic edge-case fixture."""

    def test_per_device_session_parity(self):
        """G17: per-session comparison on multi-device synthetic data."""
        raw_all = pd.read_csv(SYNTHETIC_CSV)

        for device in raw_all["device"].unique():
            device_raw = raw_all[raw_all["device"] == device].reset_index(drop=True)
            device_sorted = _sort_raw_by_timestamp(device_raw)

            # Batch: preprocess and detect per session
            preprocessed = _preprocess(device_sorted, is_synthetic=True)
            batch_by_session = _batch_detect_per_session(preprocessed)

            # Stream: process sorted device rows
            stream_results = _stream_ordered(device_sorted)

            # Group stream results by session_id
            stream_by_session: dict[str, list] = {}
            for s in stream_results:
                stream_by_session.setdefault(s.session_id, []).append(s)

            for sid, bdf in batch_by_session.items():
                assert sid in stream_by_session, f"{device}: session {sid} absent from stream"
                slist = stream_by_session[sid]
                assert len(bdf) == len(slist), (
                    f"{device}/{sid}: len batch={len(bdf)} stream={len(slist)}"
                )
                for i in range(len(bdf)):
                    _assert_parity(bdf.iloc[i], slist[i], f"{device}/{sid}[{i}]")


# ---------------------------------------------------------------------------
# Shuffled arrival variant
# ---------------------------------------------------------------------------


class TestShuffledArrival:
    """Out-of-order delivery must not crash or produce invalid output."""

    def test_shuffled_produces_valid_output(self):
        """Shuffled arrival on sample data completes and returns valid types."""
        raw = pd.read_csv(SAMPLE_CSV)
        shuffled = raw.sample(frac=1, random_state=42).reset_index(drop=True)

        engine = StreamingEngine()
        results = []
        for idx in range(len(shuffled)):
            row = shuffled.iloc[idx]
            scored = engine.process(
                {"seq": idx + 1, "payload": dict(row)},
                client_id=str(row["device"]),
            )
            results.append(scored)

        assert len(results) == len(raw)
        valid_types = set(ANOMALY_TYPES) | {"STATISTICAL_ONLY"}
        for r in results:
            assert r.anomaly_type in valid_types
            assert r.severity in {"LOW", "MEDIUM", "HIGH"}


# ---------------------------------------------------------------------------
# Negative / mutation test
# ---------------------------------------------------------------------------


class TestMutationBreaksParity:
    """Deliberately corrupted input must cause at least one divergence."""

    def test_altered_signal_breaks_parity(self):
        """Injecting extreme ss_rsrp forces a scoring divergence from batch."""
        raw = pd.read_csv(SAMPLE_CSV)
        preprocessed = _preprocess(raw)
        batch_scores, _ = detect(preprocessed)

        engine = StreamingEngine()
        altered: list = []
        for idx in range(len(raw)):
            row_dict = dict(raw.iloc[idx])
            if 10 <= idx <= 20:
                row_dict["ss_rsrp"] = -130.0
            scored = engine.process(
                {"seq": idx + 1, "payload": row_dict},
                client_id=str(row_dict["device"]),
            )
            altered.append(scored)

        diverged = 0
        for i in range(10, min(21, len(batch_scores))):
            b_row = batch_scores.iloc[i]
            s_row = altered[i]
            if (
                bool(b_row["baseline_flag"]) != bool(s_row.baseline_flag)
                or bool(b_row["if_flag"]) != bool(s_row.if_flag)
                or str(b_row["anomaly_type"]) != str(s_row.anomaly_type)
                or str(b_row["severity"]) != str(s_row.severity)
            ):
                diverged += 1
            else:
                b_if = b_row.get("if_score")
                if pd.notna(b_if) and s_row.if_score is not None:
                    if abs(float(b_if) - float(s_row.if_score)) > TOLERANCE:
                        diverged += 1

        assert diverged > 0, "Mutating ss_rsrp should cause at least one parity divergence"

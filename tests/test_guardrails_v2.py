"""Guardrail test stubs for v2 rules G17–G26 (T10-009).

Each test function represents one guardrail from docs/planning/TECH_RULES_v2.md,
quotes the official rule text in its docstring, and is marked xfail(strict=True)
naming the implementing task until that task implements it.
"""

from __future__ import annotations

import pytest

from scripts.check_no_literal_thresholds import main as check_thresholds_main


def test_no_threshold_literals_in_streaming():
    """Grep check: No numeric threshold literals in streaming/ outside config (T10-009)."""
    exit_code = check_thresholds_main()
    assert exit_code == 0, "Hardcoded numeric threshold literals found in streaming/"


def test_g17_stream_batch_parity():
    """Guardrail G17: Stream–batch parity (T11-006).

    The streaming engine yields the same flags/types/severities and scores
    (tolerance 1e-6) as the batch pipeline for the same ordered samples.
    No duplicated feature/classification logic.

    Delegates to :func:`tests.test_streaming_parity.TestSampleDataParity.test_ordered_delivery`.
    """
    from tests.test_streaming_parity import TestSampleDataParity

    TestSampleDataParity().test_ordered_delivery()


@pytest.mark.xfail(strict=True, reason="Implementing task: T12-007")
def test_g18_streaming_must_never_harm_or_alter_logging():
    """Guardrail G18: Streaming must never harm or alter logging.

    CSV logging on the phone is independent of the stream; a stream failure
    never drops or changes a logged sample; missing samples are reported,
    never synthesised.
    """
    pytest.fail("Stub: G18 logging independence is implemented in task T12-007.")


@pytest.mark.xfail(strict=True, reason="Implementing task: T11-013")
def test_g19_idempotent_ordered_ingest():
    """Guardrail G19: Idempotent, ordered ingest.

    Duplicate/replayed seq never creates a second row; ordering uses device timestamps.
    """
    pytest.fail("Stub: G19 deduplication/ordering is implemented in task T11-013.")


@pytest.mark.xfail(strict=True, reason="Implementing task: T14-001")
def test_g20_authenticated_and_bounded_ingest():
    """Guardrail G20: Authenticated and bounded ingest.

    Non-loopback binding requires a non-empty token; wrong token rejected;
    message size/rate caps enforced; constant-time token comparison; token never logged.
    """
    pytest.fail("Stub: G20 auth and bounding is implemented in task T14-001.")


@pytest.mark.xfail(strict=True, reason="Implementing task: T13-008")
def test_g21_alerts_require_rule_evidence():
    """Guardrail G21: Alerts require rule evidence.

    No alert (any channel) from ML-only flags, from a single weak metric,
    from UNKNOWN, or from a cell/network change alone.
    """
    pytest.fail("Stub: G21 evidence-gated alerting is implemented in task T13-008.")


@pytest.mark.xfail(strict=True, reason="Implementing task: T11-009")
def test_g22_live_data_is_raw_data():
    """Guardrail G22: Live data is raw data.

    Live captures are C1-format, append-only while open, hashed on close,
    promoted to data/raw/ only by the script with a manifest entry; replay
    sessions are labelled source=replay and never counted as new real data.
    """
    pytest.fail("Stub: G22 live data promotion is implemented in task T11-009.")


@pytest.mark.xfail(strict=True, reason="Implementing task: T11-008")
def test_g23_provisional_not_equal_final():
    """Guardrail G23: Provisional != final.

    Open events are labelled PROVISIONAL in every output (API, dashboard,
    alert, JSON); only closed events are FINAL and immutable.
    """
    pytest.fail("Stub: G23 event lifecycle status is implemented in task T11-008.")


@pytest.mark.xfail(strict=True, reason="Implementing task: T14-006")
def test_g24_honest_latency():
    """Guardrail G24: Honest latency.

    Latency is measured with recorded timestamps and reported with its setup
    and caveats; no code, doc, or UI states a guaranteed latency.
    """
    pytest.fail("Stub: G24 latency documentation/lint is implemented in task T14-006.")


@pytest.mark.xfail(strict=True, reason="Implementing task: T12-016")
def test_g25_edge_is_advisory_and_parity_gated():
    """Guardrail G25: Edge is advisory and parity-gated.

    Edge scores never override server results and never ship without passing
    the golden-vector parity test.
    """
    pytest.fail("Stub: G25 edge parity gating is implemented in task T12-016.")


@pytest.mark.xfail(strict=True, reason="Implementing task: T13-005")
def test_g26_secrets_and_payload_minimisation():
    """Guardrail G26: Secrets and payload minimisation.

    Token, SMTP, webhook URL only via env vars; .env ignored; external-channel
    payloads exclude raw measurements, IDs and PII by default; no precise
    location anywhere.
    """
    pytest.fail("Stub: G26 payload minimisation is implemented in task T13-005.")

"""Unit tests for StreamingEngine.process() (T11-005)."""

import ast
from pathlib import Path

import pytest

from ml.schema import ConfigError
from streaming.engine import StreamingEngine
from streaming.schema import IngestPayload, IngestSample, ScoredSample


@pytest.fixture
def sample_payload() -> dict:
    return {
        "timestamp": "09-10-26 10:15:00",
        "device": "Samsung Galaxy S21",
        "manufacturer": "Samsung",
        "android": "13",
        "operator": "Jio",
        "network_type": "5G",
        "deployment_mode": "NSA",
        "display_override": "None",
        "registered": "True",
        "ss_rsrp": "-95.0",
        "ss_rsrq": "-11.0",
        "ss_sinr": "18.5",
        "csi_rsrp": "NA",
        "csi_rsrq": "NA",
        "csi_sinr": "NA",
        "pci": "42",
        "nci": "13322280247",
        "nrarfcn": "632000",
    }


def test_model_and_meta_verified_at_startup_config_error(tmp_path):
    """Engine must verify model metadata at startup and raise ConfigError on mismatch."""
    # Empty directory missing metadata
    with pytest.raises(ConfigError):
        StreamingEngine(models_dir=tmp_path)


def test_no_sklearn_import_in_streaming_engine():
    """Verify that streaming/engine.py does not directly import sklearn."""
    engine_file = Path("streaming/engine.py")
    tree = ast.parse(engine_file.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("sklearn"), (
                    f"Forbidden sklearn import in {engine_file}: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert not node.module.startswith("sklearn"), (
                    f"Forbidden sklearn import in {engine_file}: {node.module}"
                )


def test_streaming_engine_process_sample(sample_payload):
    """StreamingEngine.process correctly returns a valid ScoredSample."""
    engine = StreamingEngine()

    ingest_sample = IngestSample(
        seq=1,
        sent_at="2026-10-09T10:15:00+05:30",
        payload=IngestPayload(**sample_payload),
    )

    scored = engine.process(ingest_sample)

    assert isinstance(scored, ScoredSample)
    assert scored.seq == 1
    assert scored.device == "Samsung Galaxy S21"
    assert scored.session_id == "samsung-galaxy-s21-1"
    assert scored.sample_idx == 0
    assert scored.model_eligible is True
    assert scored.is_valid is True
    assert scored.anomaly_type in {"NORMAL", "STATISTICAL_ONLY", "SIGNAL_DEGRADATION"}
    assert scored.severity in {"NONE", "LOW", "MEDIUM", "HIGH"}
    assert scored.published_at is not None


def test_ineligible_sample_gets_no_if_score(sample_payload):
    """Samples missing model signal metrics receive model_eligible=False and no IF score."""
    engine = StreamingEngine()

    # Missing ss_rsrp -> model ineligible
    ineligible_payload = dict(sample_payload)
    ineligible_payload["ss_rsrp"] = "NA"

    scored = engine.process(
        {"seq": 2, "payload": ineligible_payload},
        client_id="client-ineligible",
    )

    assert scored.model_eligible is False
    assert scored.if_score is None
    assert scored.if_flag is False


def test_no_fillna_on_signal_metrics(sample_payload):
    """G2: missing ss_* or csi_* metrics must remain None and never be filled with 0."""
    engine = StreamingEngine()

    sample_with_missing_csi = dict(sample_payload)
    sample_with_missing_csi["csi_rsrp"] = "NA"
    sample_with_missing_csi["csi_rsrq"] = "2147483647"

    scored = engine.process(
        {"seq": 3, "payload": sample_with_missing_csi},
        client_id="client-g2",
    )

    assert scored.csi_rsrp is None
    assert scored.csi_rsrq is None
    assert scored.csi_available is False

"""Unit tests for ml/config.py streaming constants (T10-004)."""

import sys


def test_streaming_constants_presence_and_types():
    from ml import config

    assert isinstance(config.SESSION_MAX_ROWS, int)
    assert config.SESSION_MAX_ROWS == 50000

    assert isinstance(config.EVENT_CLOSE_GAP_SAMPLES, int)
    assert config.EVENT_CLOSE_GAP_SAMPLES == 5

    assert isinstance(config.STALE_AFTER_SECONDS, float)
    assert config.STALE_AFTER_SECONDS == 10.0

    assert isinstance(config.CLOCK_SKEW_WARN_SECONDS, float)
    assert config.CLOCK_SKEW_WARN_SECONDS == 5.0

    assert isinstance(config.SESSION_RESUME_WINDOW_SECONDS, int)
    assert config.SESSION_RESUME_WINDOW_SECONDS == 600

    assert isinstance(config.MAX_MESSAGE_BYTES, int)
    assert config.MAX_MESSAGE_BYTES == 8192

    assert isinstance(config.MAX_MSGS_PER_MIN, int)
    assert config.MAX_MSGS_PER_MIN == 120

    assert isinstance(config.MAX_INFLIGHT_UNACKED, int)
    assert config.MAX_INFLIGHT_UNACKED == 50

    assert isinstance(config.ALERT_MIN_PERSISTENCE_SAMPLES, int)
    assert config.ALERT_MIN_PERSISTENCE_SAMPLES == 6

    assert isinstance(config.ALERT_MIN_SEVERITY, str)
    assert config.ALERT_MIN_SEVERITY == "MEDIUM"

    assert isinstance(config.ALERT_COOLDOWN_SECONDS, int)
    assert config.ALERT_COOLDOWN_SECONDS == 300


def test_existing_constants_preserved():
    from ml import config

    assert config.SESSION_GAP_SECONDS == 30
    assert config.DEFAULT_WINDOW == 10
    assert config.SAMPLING_SECONDS == 3
    assert config.RANDOM_STATE == 42
    assert isinstance(config.PERSIST_THRESHOLDS, dict)
    assert isinstance(config.SENTINEL_INTS, list)


def test_import_config_does_not_import_sklearn():
    # Verify in an isolated Python process that ml.config does not import sklearn
    import subprocess

    cmd = [sys.executable, "-c", "import ml.config, sys; assert 'sklearn' not in sys.modules"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"ml.config imported sklearn: {result.stderr}"

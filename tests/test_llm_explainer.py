"""Unit tests for optional LLM explainer module and fallback guardrails (T9-002)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from agents.llm_explainer import explain_diagnosis, is_llm_enabled


def test_llm_disabled_by_default() -> None:
    """Assert LLM is disabled by default when NADS_USE_LLM environment variable is unset."""
    with patch.dict(os.environ, {}, clear=True):
        assert not is_llm_enabled()
        res = explain_diagnosis("Summary", ["Evidence 1"], "Note", "COMBINED_ANOMALY")
        assert res is None


def test_llm_timeout_fallback() -> None:
    """Assert timeout or connection failure cleanly falls back to None."""
    with patch.dict(os.environ, {"NADS_USE_LLM": "true"}):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
            res = explain_diagnosis("Summary", ["Evidence 1"], "Note", "COMBINED_ANOMALY")
            assert res is None


def test_llm_success_mock() -> None:
    """Assert valid 200 response returns rephrased string."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"response": "Rephrased 5G anomaly description."}'
    mock_response.__enter__.return_value = mock_response

    with patch.dict(os.environ, {"NADS_USE_LLM": "true"}):
        with patch("urllib.request.urlopen", return_value=mock_response):
            res = explain_diagnosis("Summary", ["Evidence 1"], "Note", "COMBINED_ANOMALY")
            assert res == "Rephrased 5G anomaly description."

"""Optional local LLM explainer module via Ollama (T9-001).

Implements fallback-safe integration with a local Ollama LLM endpoint.
By default, NADS_USE_LLM is false, so deterministic template text is used.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3"
TIMEOUT_SECONDS = 10.0


def is_llm_enabled() -> bool:
    """Check if local LLM explainer is enabled via environment variable."""
    return os.getenv("NADS_USE_LLM", "false").lower() in ("true", "1", "yes")


def explain_diagnosis(
    summary: str,
    evidence: list[str],
    confidence_note: str,
    anomaly_type: str,
) -> str | None:
    """Send structured diagnosis payload to Ollama LLM if enabled, returning rephrased string.

    Args:
        summary: Original template summary string.
        evidence: List of evidence strings.
        confidence_note: Confidence disclaimer note.
        anomaly_type: Classified anomaly category.

    Returns:
        Rephrased explanation string from LLM, or None if disabled/unreachable.
    """
    if not is_llm_enabled():
        logger.debug("NADS_USE_LLM is false; skipping Ollama call.")
        return None

    ollama_url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
    api_endpoint = f"{ollama_url}/api/generate"

    prompt = (
        f"You are a network telemetry assistant. Rephrase the following 5G anomaly diagnosis "
        f"clearly without altering facts, numbers, or introducing unverified root causes:\n\n"
        f"Anomaly Type: {anomaly_type}\n"
        f"Summary: {summary}\n"
        f"Evidence: {', '.join(evidence)}\n"
        f"Note: {confidence_note}\n\n"
        f"Provide a 2-sentence concise explanation."
    )

    payload = {
        "model": os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
        "prompt": prompt,
        "stream": False,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            api_endpoint, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            if response.status == 200:
                result = json.loads(response.read().decode("utf-8"))
                response_text = result.get("response", "").strip()
                if response_text:
                    return response_text
    except (urllib.error.URLError, TimeoutError, Exception) as exc:
        logger.warning("Ollama LLM call failed or timed out: %s. Using template text.", exc)

    return None

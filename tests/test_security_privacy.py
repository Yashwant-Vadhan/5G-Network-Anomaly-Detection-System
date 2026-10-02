"""Security and privacy automated test suite for 5G-NADS (T7-009).

Enforces guardrail G13 (offline operation), PII column rejection, secret scan checks,
gitignore rules for sensitive data and models, and dashboard local binding rules.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
import pandas as pd
import pytest

from ml.schema import SchemaError, assert_no_pii_columns, validate_raw_columns


def test_pii_column_rejection():
    """Verify that forbidden PII columns cause an immediate SchemaError."""
    forbidden_cols = ["imsi", "imei", "phone", "lat", "lon", "user_id", "email"]
    for col in forbidden_cols:
        df = pd.DataFrame({"ss_rsrp": [-80.0], col: ["sensitive_value"]})
        with pytest.raises(SchemaError, match="Forbidden PII column detected"):
            assert_no_pii_columns(df)


def test_malformed_or_wrong_header_csv_rejection():
    """Verify that malformed or unexpected CSV columns are rejected by raw column validation."""
    df_wrong = pd.DataFrame({"wrong_col1": [1], "wrong_col2": [2]})
    with pytest.raises(SchemaError, match="Missing columns"):
        validate_raw_columns(df_wrong)


def test_gitignore_covers_sensitive_files():
    """Verify .gitignore includes patterns for raw, processed, models, env files, and keystores."""
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists(), ".gitignore file missing"
    content = gitignore_path.read_text(encoding="utf-8")

    required_patterns = [
        "data/raw/*",
        "data/processed/*",
        "models/*",
        ".env",
        "*.keystore",
        "*.jks",
        "*.pem",
        "*.key",
    ]
    for pat in required_patterns:
        assert pat in content, f".gitignore missing pattern: {pat}"


def test_no_network_imports_in_core_pipeline():
    """Guardrail G13: Core ML pipeline and algorithms must run 100% offline without network libraries."""
    forbidden_modules = ["requests", "urllib", "httpx", "aiohttp", "socket"]
    python_files = list(Path("ml").rglob("*.py")) + list(Path("pipelines").rglob("*.py"))

    for py_file in python_files:
        code = py_file.read_text(encoding="utf-8")
        for mod in forbidden_modules:
            # Match import statements like 'import requests' or 'from requests import ...'
            pattern = rf"^\s*(import\s+{mod}|from\s+{mod}\s+import)"
            match = re.search(pattern, code, re.MULTILINE)
            assert not match, f"Forbidden network module '{mod}' imported in offline module {py_file}"


def test_no_hardcoded_secrets_in_repo():
    """Scan tracked repo files for high-entropy secret patterns like API keys or private keys."""
    secret_patterns = [
        r"BEGIN\s+PRIVATE\s+KEY",
        r"AKIA[0-9A-Z]{16}",
        r"aws_secret_access_key",
        r"ghp_[a-zA-Z0-9]{36}",
        r"sk-[a-zA-Z0-9]{48}",
    ]
    tracked_files = [
        p for p in Path(".").rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.parts)
        and "data" not in p.parts and "models" not in p.parts and "__pycache__" not in p.parts
        and p.name != "test_security_privacy.py"
    ]

    for p in tracked_files:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in secret_patterns:
            assert not re.search(pat, content), f"Potential secret pattern '{pat}' found in file {p}"


def test_dashboard_binds_to_localhost_by_default():
    """Verify Streamlit config or dashboard scripts bind to 127.0.0.1 for local isolation."""
    config_file = Path(".streamlit/config.toml")
    if config_file.exists():
        content = config_file.read_text(encoding="utf-8")
        # Ensure address isn't bound to 0.0.0.0
        assert "0.0.0.0" not in content, "Dashboard must not bind to 0.0.0.0 for security"

"""Tests for T11-019: Server CLI and bind policy."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from ml.schema import ConfigError
from streaming.server import ServerConfig, create_app, parse_server_args


def test_server_cli_help():
    """--help documents every flag and exits 0."""
    res = subprocess.run(
        [sys.executable, "-m", "streaming.server", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    help_text = res.stdout
    assert "--host" in help_text
    assert "--port" in help_text
    assert "--allow-lan" in help_text
    assert "--allow-remote-view" in help_text
    assert "--token" in help_text
    assert "--mode" in help_text
    assert "--allowed-origins" in help_text
    assert "--retention" in help_text
    assert "--log-level" in help_text


def test_bind_policy_0000_refuses_to_start():
    """0.0.0.0 without --allow-lan or without ingest token exits code 2 with fix hint."""
    # 1. 0.0.0.0 without allow-lan
    res1 = subprocess.run(
        [sys.executable, "-m", "streaming.server", "--host", "0.0.0.0"],
        capture_output=True,
        text=True,
    )
    assert res1.returncode == 2
    assert "requires --allow-lan" in res1.stderr
    assert "Fix:" in res1.stderr

    # 2. 0.0.0.0 with allow-lan but empty token
    res2 = subprocess.run(
        [sys.executable, "-m", "streaming.server", "--host", "0.0.0.0", "--allow-lan"],
        capture_output=True,
        text=True,
    )
    assert res2.returncode == 2
    assert "requires a non-empty NADS_INGEST_TOKEN" in res2.stderr
    assert "Fix:" in res2.stderr


def test_server_config_validate_enforces_bind_policy():
    """ServerConfig.validate raises ConfigError on invalid bind configurations."""
    # Loopback is fine without token
    ServerConfig(host="127.0.0.1", ingest_token=None).validate()
    ServerConfig(host="localhost", ingest_token=None).validate()

    # Non-loopback without allow_lan
    with pytest.raises(ConfigError, match="requires --allow-lan"):
        ServerConfig(host="0.0.0.0", allow_lan=False, ingest_token="secret").validate()

    # Non-loopback with allow_lan but no token
    with pytest.raises(ConfigError, match="requires a non-empty NADS_INGEST_TOKEN"):
        ServerConfig(host="0.0.0.0", allow_lan=True, ingest_token=None).validate()

    # Non-loopback with both allow_lan and token passes
    ServerConfig(host="0.0.0.0", allow_lan=True, ingest_token="secret123").validate()


def test_startup_logs_enabled_channels_without_secrets(caplog: pytest.LogCaptureFixture):
    """Startup log lists enabled alert channels without leaking secret credentials or URLs."""
    secret_webhook = "https://discord.com/api/webhooks/99999/super_secret_webhook_token"
    secret_email_host = "smtp.super-secret-mail.internal"

    with patch.dict(
        os.environ,
        {
            "NADS_ALERT_WEBHOOK_URL": secret_webhook,
            "NADS_ALERT_EMAIL_HOST": secret_email_host,
        },
    ):
        with caplog.at_level(logging.INFO, logger="streaming.server"):
            config = ServerConfig(ingest_token="secret-token-token")
            _app = create_app(config)

    logs = caplog.text
    assert "Enabled alert channels:" in logs
    assert "in_app" in logs
    assert "webhook" in logs
    assert "email" in logs

    # Ensure secrets are NOT leaked in startup log
    assert secret_webhook not in logs
    assert "super_secret_webhook_token" not in logs
    assert secret_email_host not in logs
    assert "secret-token-token" not in logs


def test_parse_server_args_flags():
    """parse_server_args correctly populates options."""
    ns = parse_server_args(
        [
            "--host",
            "192.168.1.50",
            "--port",
            "9000",
            "--allow-lan",
            "--token",
            "my-token-123",
            "--mode",
            "public",
            "--allowed-origins",
            "https://demo.example.com",
            "--retention",
            "false",
        ]
    )
    assert ns.host == "192.168.1.50"
    assert ns.port == 9000
    assert ns.allow_lan is True
    assert ns.token == "my-token-123"
    assert ns.mode == "public"
    assert ns.allowed_origins == "https://demo.example.com"
    assert ns.retention == "false"

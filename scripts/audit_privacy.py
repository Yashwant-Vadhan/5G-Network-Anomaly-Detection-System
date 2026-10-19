"""Automated privacy and PII audit runner for streaming telemetry (T14-005).

Audits Contract C7, C8, and C9 schemas, server loggers, data/live/ persistent files,
outbound webhook/email notification channels, and Android collector source code
for inadvertent exposure of auth tokens, hardware identifiers, location, or PII.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from streaming.alerts.channels.email import format_email_body
from streaming.alerts.channels.phone import to_compact_c9
from streaming.schema import (
    AlertRecord,
    IngestPayload,
    ScoredSample,
)

FORBIDDEN_PII_FIELDS = {
    "imei",
    "imsi",
    "msisdn",
    "phone_number",
    "mac_address",
    "mac",
    "android_id",
    "serial_number",
    "device_serial",
    "latitude",
    "longitude",
    "altitude",
    "gps_lat",
    "gps_lon",
    "user_name",
    "username",
    "email_address",
    "ssn",
}


def audit_c7_schema() -> dict[str, Any]:
    """Audit IngestPayload to ensure forbidden PII fields are strictly forbidden."""
    field_names = set(IngestPayload.model_fields.keys())
    leaked = field_names.intersection(FORBIDDEN_PII_FIELDS)
    extra_forbidden = IngestPayload.model_config.get("extra") == "forbid"
    return {
        "check": "C7 IngestPayload schema",
        "passed": len(leaked) == 0 and extra_forbidden,
        "details": {
            "fields_count": len(field_names),
            "forbidden_detected": list(leaked),
            "extra_forbid_enforced": extra_forbidden,
        },
    }


def audit_c8_schema() -> dict[str, Any]:
    """Audit ScoredSample to ensure live telemetry model contains no PII fields."""
    field_names = set(ScoredSample.model_fields.keys())
    leaked = field_names.intersection(FORBIDDEN_PII_FIELDS)
    return {
        "check": "C8 ScoredSample schema",
        "passed": len(leaked) == 0,
        "details": {
            "fields_count": len(field_names),
            "forbidden_detected": list(leaked),
        },
    }


def audit_c9_payloads() -> dict[str, Any]:
    """Audit AlertRecord, webhook, email, and phone push serialization."""
    sample_alert = AlertRecord(
        alert_id="alt-privacy-audit-001",
        created_at="2026-10-18T10:00:00+00:00",
        event_id="evt-001",
        session_id="sess-001",
        source="phone",
        kind="NEW",
        severity="HIGH",
        anomaly_type="SIGNAL_DEGRADATION",
        event_status="PROVISIONAL",
        title="Signal Degradation Alert",
        body="SS-RSRP dropped below -110 dBm",
        evidence=["ss_rsrp < -110 dBm for 5 samples"],
    )

    webhook_body = sample_alert.to_webhook_body(include_evidence=False)
    compact_phone = to_compact_c9(sample_alert)
    email_text = format_email_body(sample_alert, include_evidence=False)

    webhook_keys = set(webhook_body.keys())
    phone_keys = set(compact_phone.keys())

    wb_leaked = webhook_keys.intersection(FORBIDDEN_PII_FIELDS)
    phone_leaked = phone_keys.intersection(FORBIDDEN_PII_FIELDS)
    email_has_tokens = any(k in email_text.lower() for k in ["bearer", "token=", "password="])

    passed = len(wb_leaked) == 0 and len(phone_leaked) == 0 and not email_has_tokens

    return {
        "check": "C9 Alert outbound payloads (Webhook, Phone, Email)",
        "passed": passed,
        "details": {
            "webhook_keys": sorted(webhook_keys),
            "phone_keys": sorted(phone_keys),
            "webhook_leaked": list(wb_leaked),
            "phone_leaked": list(phone_leaked),
            "email_has_sensitive_tokens": email_has_tokens,
        },
    }


def audit_server_loggers(base_dir: str = "streaming") -> dict[str, Any]:
    """Scan all Python files in streaming/ to verify no tokens or credentials are logged."""
    patterns = [
        re.compile(r"logger\.\w+\(.*(?:auth_)?token", re.IGNORECASE),
        re.compile(r"logger\.\w+\(.*(?:user_)?password", re.IGNORECASE),
        re.compile(r"logger\.\w+\(.*(?:client_)?secret", re.IGNORECASE),
        re.compile(r"logger\.\w+\(.*webhook_url", re.IGNORECASE),
    ]

    violations: list[str] = []
    base_path = Path(base_dir)

    for py_file in base_path.rglob("*.py"):
        try:
            with py_file.open("r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, 1):
                    for pat in patterns:
                        if pat.search(line):
                            violations.append(f"{py_file}:{line_idx}: {line.strip()[:80]}")
        except Exception as e:
            violations.append(f"Could not read {py_file}: {e}")

    return {
        "check": "Server loggers token & credential scan",
        "passed": len(violations) == 0,
        "details": {
            "files_scanned": len(list(base_path.rglob("*.py"))),
            "violations_found": violations,
        },
    }


def audit_data_live_files(live_dir: str = "data/live") -> dict[str, Any]:
    """Inspect CSV, JSON metadata, and JSONL alert records in data/live/ for PII."""
    live_path = Path(live_dir)
    if not live_path.exists():
        return {
            "check": "data/live/ storage scan",
            "passed": True,
            "details": {"message": f"{live_dir} does not exist"},
        }

    violations: list[str] = []
    file_count = 0

    for fpath in live_path.iterdir():
        if fpath.suffix == ".csv":
            file_count += 1
            try:
                with fpath.open("r", encoding="utf-8") as csvfile:
                    reader = csv.reader(csvfile)
                    header = next(reader, [])
                    header_lower = {h.strip().lower() for h in header}
                    leaked = header_lower.intersection(FORBIDDEN_PII_FIELDS)
                    if leaked:
                        violations.append(f"{fpath.name}: header contains {leaked}")
            except Exception as e:
                violations.append(f"{fpath.name}: error reading csv {e}")

        elif fpath.suffix == ".json":
            file_count += 1
            try:
                with fpath.open("r", encoding="utf-8") as metafile:
                    data = json.load(metafile)
                    keys_lower = {k.strip().lower() for k in data.keys()}
                    leaked = keys_lower.intersection(FORBIDDEN_PII_FIELDS)
                    if leaked:
                        violations.append(f"{fpath.name}: meta contains {leaked}")
                    for val in data.values():
                        if isinstance(val, str) and ("bearer " in val.lower() or "token" in val):
                            violations.append(f"{fpath.name}: meta value contains token")
            except Exception as e:
                violations.append(f"{fpath.name}: error reading json {e}")

    return {
        "check": "data/live/ storage scan",
        "passed": len(violations) == 0,
        "details": {
            "files_inspected": file_count,
            "violations_found": violations,
        },
    }


def audit_android_collector(
    android_path: str = "android-collector/5GNetworkTester/app/src/main/java",
) -> dict[str, Any]:
    """Audit Android source code for forbidden location, hardware ID, or subscriber APIs."""
    path = Path(android_path)
    if not path.exists():
        return {
            "check": "Android collector code audit",
            "passed": True,
            "details": {"message": "Android source tree not present; skipped"},
        }

    forbidden_api_patterns = [
        re.compile(r"LocationManager", re.IGNORECASE),
        re.compile(r"FusedLocationProviderClient", re.IGNORECASE),
        re.compile(r"getLastKnownLocation", re.IGNORECASE),
        re.compile(r"\bgetDeviceId\b", re.IGNORECASE),
        re.compile(r"\bgetImei\b", re.IGNORECASE),
        re.compile(r"\bgetSubscriberId\b", re.IGNORECASE),
        re.compile(r"\bgetLine1Number\b", re.IGNORECASE),
        re.compile(r"\bgetSimSerialNumber\b", re.IGNORECASE),
    ]

    violations: list[str] = []
    files_scanned = 0

    for kt_file in path.rglob("*.kt"):
        files_scanned += 1
        with kt_file.open("r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                for pat in forbidden_api_patterns:
                    if pat.search(line):
                        violations.append(f"{kt_file.name}:{line_idx}: {line.strip()[:80]}")

    return {
        "check": "Android collector code audit",
        "passed": len(violations) == 0,
        "details": {
            "kt_files_scanned": files_scanned,
            "violations_found": violations,
        },
    }


def run_full_privacy_audit() -> list[dict[str, Any]]:
    """Execute all privacy and PII audit checks."""
    return [
        audit_c7_schema(),
        audit_c8_schema(),
        audit_c9_payloads(),
        audit_server_loggers(),
        audit_data_live_files(),
        audit_android_collector(),
    ]


def main() -> int:
    """CLI entrypoint for running the privacy and PII audit."""
    parser = argparse.ArgumentParser(description="5G-NADS Privacy & PII Audit Scanner")
    parser.add_argument("--json", action="store_true", help="Output audit results as JSON")
    args = parser.parse_args()

    results = run_full_privacy_audit()
    all_passed = all(r["passed"] for r in results)

    if args.json:
        print(json.dumps({"passed": all_passed, "checks": results}, indent=2))
    else:
        print("=" * 70)
        print("5G-NADS PRIVACY & PII COMPLIANCE AUDIT (T14-005)")
        print("=" * 70)
        for r in results:
            status = "[PASS]" if r["passed"] else "[FAIL]"
            print(f"{status} {r['check']}")
            for k, v in r["details"].items():
                print(f"       {k}: {v}")
        print("=" * 70)
        print(f"Overall Status: {'PASSED (Zero PII / Leaks)' if all_passed else 'FAILED'}")
        print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

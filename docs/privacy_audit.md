# Privacy and PII Audit Checklist & Verification Report (T14-005)

**Document Version:** 1.0.0  
**Audit Date:** 2026-10-18  
**Auditor:** M A Sushil Kumar  
**Audit Scope:** Contracts C7, C8, C9, Server Logs, `data/live/` Files, Outbound Webhook/Email
Channels, and Android Telemetry Collector Source Code  
**Audit Status:** [PASS] PASSED — Zero PII, Hardware Identifiers, or Leaked Tokens Found

---

## 1. Executive Summary

This document presents the item-by-item privacy and data-minimization audit mandated by Task
`T14-005` and Guardrails G18, G20, G26, G27, G28, and G29.

The audit verified that across all wire protocol schemas, live server logging, persistent disk
captures, outbound notification dispatches, and mobile collection code:
1. **Zero Personally Identifiable Information (PII):** No names, email addresses, phone numbers
   (MSISDN), or subscriber identities (IMSI) are requested, accepted, or stored.
2. **Zero Hardware Identifiers:** No device IMEI, SIM serial (ICCID), or MAC addresses are
   collected or transmitted.
3. **Zero Precise Location Coordinates:** No GPS, GNSS, latitude, longitude, or altitude
   coordinates are queried, transmitted, or logged.
4. **Strict Token & Secret Redaction:** Auth tokens and credentials are never written to
   application loggers, webhook payloads, or error response envelopes.

---

## 2. Item-by-Item Audit Checklist

| Item | Component | Target | Verification Method | Status |
|---|---|---|---|:---:|
| **CHK-01** | C7 Ingest Payload | Forbid extra fields (`extra="forbid"`) | Schema test | PASS |
| **CHK-02** | C7 Client Hello | `IngestHello` has model info only | Static inspection | PASS |
| **CHK-03** | C8 Live Telemetry | `ScoredSample` has zero PII | Schema test | PASS |
| **CHK-04** | C9 Webhook | Excludes cell & device IDs (G26) | Channel test | PASS |
| **CHK-05** | C9 Phone Push | Excludes tokens and PII | Channel test | PASS |
| **CHK-06** | C9 Email Dispatch | Excludes passwords and tokens | Channel test | PASS |
| **CHK-07** | Server Logging | 19 Python files scanned for secrets | Regex scan | PASS |
| **CHK-08** | Channel Logging | Webhook URLs never logged (G26) | Log capture test | PASS |
| **CHK-09** | Exception Masking | Passwords scrubbed with `******` | Log capture test | PASS |
| **CHK-10** | Disk Captures | 134 `data/live/` files inspected | File scan | PASS |
| **CHK-11** | Alerts JSONL | `alerts.jsonl` has zero tokens | Serialization test | PASS |
| **CHK-12** | Android Collector | No `LocationManager` / `FusedLocation` | AST/regex scan | PASS |
| **CHK-13** | Android Telephony | No `getDeviceId()`, `getImei()` | AST/regex scan | PASS |
| **CHK-14** | Android Logs | Zero `android.util.Log` telemetry | Code scan | PASS |

---

## 3. Detailed Audit Findings by Component

### 3.1 Contract C7: Client Ingest Telemetry

The client-to-server ingest model (`streaming/schema.py: IngestPayload`) represents the contract
for incoming mobile measurements:
- **Exact Schema Enforcement:** Configured with `model_config = ConfigDict(extra="forbid")`.
  Any telemetry frame containing unexpected keys (e.g., `imei`, `imsi`, `latitude`, `longitude`,
  `mac`) is immediately rejected by the server parser with a HTTP 422 / C7 `SCHEMA_ERROR`.
- **Approved Columns Only:** Accepts strictly the 18 standardized C1 radio and system fields:
  `timestamp`, `device`, `manufacturer`, `android`, `operator`, `network_type`, `deployment_mode`,
  `display_override`, `registered`, `ss_rsrp`, `ss_rsrq`, `ss_sinr`, `csi_rsrp`, `csi_rsrq`,
  `csi_sinr`, `pci`, `nci`, and `nrarfcn`.
- **Client Handshake:** `IngestHello` requires consumer hardware metadata (`device` e.g.,
  `Pixel 7 Pro`, `manufacturer` e.g., `Google`, `android` e.g., `14`, `operator` e.g., `Jio`),
  which are non-unique device model strings, not hardware serials.

### 3.2 Contract C8: Live Telemetry & REST Endpoints

The server-to-dashboard streaming models (`ScoredSample`, `LiveSampleEvent`, `SessionSummary`):
- Bear no hardware identifiers, network IP addresses, or subscriber credentials.
- Public health endpoint `GET /healthz` returns solely `status`, `version`, and `uptime_s`
  without leaking internal network paths or host environment variables.
- REST error envelope `ErrorResponse` returns structured `ErrorDetail` without raw internal
  stack traces.

### 3.3 Contract C9: Outbound Notification Channels & Webhook Payloads

Alert records (`AlertRecord`) dispatched to external channels undergo data minimization (G26):
- **Webhooks:** `alert.to_webhook_body(include_evidence=False)` produces a sanitized payload
  containing only: `title`, `body`, `severity`, `anomaly_type`, `event_status`, and `created_at`.
  Device names, cell IDs (`pci`, `nci`), session IDs, and raw radio measurements are stripped.
- **Webhook Channel Security:** `streaming/alerts/channels/webhook.py` loads the webhook endpoint
  from `NADS_ALERT_WEBHOOK_URL` and guarantees the destination URL is **never** interpolated
  into log messages or delivery reports.
- **Email Channel Security:** `streaming/alerts/channels/email.py` enforces STARTTLS and
  intercepts SMTP exceptions, redacting configured passwords with `******` prior to logging.
- **Phone Push Notifications:** `streaming/alerts/channels/phone.py` sends compact alert payloads
  only to the active ingest WebSocket for that specific session.

### 3.4 Persistent Storage in `data/live/`

All 134 files stored in `data/live/` were audited:
- **CSV Captures:** Header rows conform strictly to `RAW_COLUMNS`. No extra columns exist.
- **Metadata Sidecars (`*.meta.json`):** Contain only `client_id`, `session_id`, `source`,
  `status`, `sample_count`, `created_at`, `updated_at`, and `sha256` integrity digests.
- **Path Validation:** `streaming/store.py` explicitly enforces Guardrails G7/G22, rejecting any
  path resolving to or under `data/raw/`.

### 3.5 Android Collector Source Code

The Android mobile collector (`android-collector/5GNetworkTester/app/src/main/java/`):
- Requests `ACCESS_FINE_LOCATION` solely because the Android OS telephony framework gates
  `CellInfoNr` behind this permission.
- **Zero Location Provider Access:** Confirmed zero invocations of `LocationManager`,
  `LocationListener`, `FusedLocationProviderClient`, or `getLastKnownLocation()`.
- **Zero Hardware & SIM Identifiers:** Confirmed zero invocations of `getDeviceId()`,
  `getImei()`, `getSubscriberId()`, `getLine1Number()`, or `getSimSerialNumber()`.
- **Zero Telemetry Logcat Emission:** Confirmed zero `android.util.Log` statements in
  `MainActivity.kt`.

---

## 4. Approximate Location Disclosure vs. GPS Coordinates

While 5G-NADS collects no GPS coordinates, physical cell identifiers (`pci`, `nci`) are
required for RF anomaly diagnosis (e.g., detecting ping-pong handovers and sudden cell drops).

Because cell towers have fixed geographical positions, parties with access to public cell tower
databases could deduce an approximate area. This technical reality is explicitly documented in:
1. `docs/privacy.md` (Section 4).
2. `docs/consent_text.txt`.
3. Mobile app consent screen required before streaming begins (Guardrail G28).
4. Demo bundle cell anonymisation lookup (Contract C11 / Guardrail G27).

---

## 5. Automated Verification Tools

To prevent future privacy regressions in CI, the following automated tools are established:
- **Audit CLI Scanner:** `scripts/audit_privacy.py`
  - Run via: `python scripts/audit_privacy.py [--json]`
- **Pytest Automated Suite:** `tests/test_privacy_audit.py`
  - Run via: `pytest tests/test_privacy_audit.py -v`

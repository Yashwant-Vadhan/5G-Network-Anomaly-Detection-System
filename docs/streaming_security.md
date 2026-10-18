# 5G-NADS v2 Streaming Security & Exposure Policy

> Task: `T14-004` (Write the streaming security document).
> System: 5G Network Anomaly Detection System (v2 Streaming Subsystem).
> Status: Active Security Specification.

---

## 1. Overview & Threat Model for Local Deployments

The 5G-NADS streaming subsystem ingests live cellular telemetry from mobile endpoints
(Android smartphones running the collector app or synthetic replayers) and broadcasts
scored anomalies and multi-agent diagnostic insights to client dashboards.

### 1.1 Deployment Scenarios
5G-NADS v2 targets two primary deployment topologies:
1. **Local Loopback (Development / USB Tethering):**
   - Ingest server binds strictly to `127.0.0.1`.
   - Android device communicates via USB reverse port forwarding:
     `adb reverse tcp:8000 tcp:8000`.
   - Highest security: traffic never crosses a physical network interface.
2. **Local Area Network (LAN / Private Wi-Fi):**
   - Server runs on a local workstation/server on the same Wi-Fi or wired subnet.
   - Server explicitly binds to `0.0.0.0` or a LAN IP using the `--allow-lan` flag.
   - Android collector streams telemetry directly over local 802.11 Wi-Fi.

### 1.2 Threat Actors & Attacker Capabilities
- **Passive LAN Eavesdropper:** An adversary on the same unencrypted or shared Wi-Fi
  monitoring network packets to reconstruct telemetry streams or cell towers.
- **Rogue Ingest Client:** An unauthorized device attempting to inject fabricated
  telemetry, poison ML inference models, or trigger bogus diagnostic alerts.
- **Unauthorized LAN Observer:** A network peer attempting to inspect live sessions,
  download captured traces, or view internal model architectures without permission.
- **Denial of Service (DoS) Attacker:** An actor flooding the WebSocket endpoint or
  handshake port to exhaust server memory and CPU threads.

### 1.3 Protected Assets
- **Telemetry Payloads (Contract C1/C7):** RSRP, RSRQ, SINR, PCI, NCI, NRARFCN.
  *(Note: Cell IDs like NCI can be cross-referenced with public databases to infer
  approximate device physical location).*
- **Authentication Tokens:** `NADS_INGEST_TOKEN` secret bearer strings.
- **Compute & State Resources:** Event correlation engine, ML Isolation Forest workers,
  and in-memory circular telemetry buffers.

---

## 2. Authentication & Token Handling Architecture

All telemetry ingestion requires bearer token authentication.

### 2.1 Ingest Token (`NADS_INGEST_TOKEN`)
- Ingestion endpoints (`/api/v1/ingest`) reject unauthenticated connections with HTTP
  401 / WebSocket close code 4401.
- Tokens may be supplied via:
  1. HTTP/WebSocket Header: `Authorization: Bearer <token>` (Recommended).
  2. Handshake Query Parameter: `?token=<token>` (Fallback for clients unable to set
     custom headers during initial WebSocket upgrade).

### 2.2 Constant-Time Validation
Token verification uses Python's `hmac.compare_digest` to prevent timing side-channel
attacks during string comparison:
```python
import hmac


def verify_token(provided_token: str, expected_token: str) -> bool:
    if not provided_token or not expected_token:
        return False
    return hmac.compare_digest(provided_token.strip(), expected_token.strip())
```

### 2.3 Secret Leakage Prevention
- Tokens are **never** logged to `stdout`, `stderr`, or server rotating log files.
- Tokens are **never** returned in diagnostic endpoints (`/healthz`, `/api/v1/metrics`,
  `/api/v1/model`).
- Captured CSV files saved to `data/live/` contain zero token or credential metadata.
- Rate limiter: `/api/v1/pair` limits connection requests to 5 attempts per IP per minute
  with exponential backoff on sustained failures.

---

## 3. Network Interface Bind & Exposure Policy

A core architectural principle of 5G-NADS is **secure defaults with explicit opt-in**.

### 3.1 Strict Loopback Default
By default, `python -m streaming.server` binds exclusively to `127.0.0.1:8000`. The server
refuses external connections from other machines on the network.

### 3.2 Guarded LAN Exposure (`--allow-lan`)
To expose the ingest server to the local subnet (e.g. for phone testing over Wi-Fi):
1. The administrator must explicitly pass the `--allow-lan` command-line flag.
2. A cryptographically non-empty `NADS_INGEST_TOKEN` environment variable must be set.
3. If `--allow-lan` is passed without a non-empty token, the server exits immediately
   with **exit code 2** and prints a one-line remediation hint:
   `Error: --allow-lan requires a non-empty NADS_INGEST_TOKEN environment variable.`

### 3.3 Segregated Endpoint Access Control
When bound to LAN interfaces, endpoints enforce separate access controls:

| Endpoint | Protocol | LAN Access Rule | Security Mechanism |
|---|---|---|---|
| `/healthz` | HTTP GET | Allowed | Public liveness probe (no secrets) |
| `/api/v1/ingest` | WebSocket | Allowed | Requires `NADS_INGEST_TOKEN` bearer |
| `/api/v1/live` | WebSocket | Loopback Only* | Requires `allow_remote_view=True` |
| `/api/v1/sessions` | HTTP GET | Loopback Only* | Requires `allow_remote_view=True` |
| `/api/v1/samples` | HTTP GET | Loopback Only* | Requires `allow_remote_view=True` |
| `/api/v1/events` | HTTP GET | Loopback Only* | Requires `allow_remote_view=True` |
| `/api/v1/alerts` | HTTP GET | Loopback Only* | Requires `allow_remote_view=True` |
| `/api/v1/metrics` | HTTP GET | Loopback Only* | Requires `allow_remote_view=True` |

*\* Read endpoints return `HTTP 403 Forbidden` to non-loopback IPs unless
`NADS_ALLOW_REMOTE_VIEW=true` is explicitly configured by the operator.*

---

## 4. Transport Layer Security (TLS / HTTPS / WSS)

### 4.1 Uvicorn SSL Configuration (Verified)
The 5G-NADS streaming server is built on Uvicorn and Starlette/FastAPI. Uvicorn natively
supports TLS encryption via the following CLI and programmatic options:
- `--ssl-keyfile <path/to/key.pem>`: Private key file.
- `--ssl-certfile <path/to/cert.pem>`: Certificate PEM file.
- `--ssl-version <int>`: Protocol version (defaults to TLS 1.2+).
- `--ssl-ciphers <str>`: Standard OpenSSL cipher specification string.

When configured with SSL certificates, all WebSocket connections operate over `wss://`
and HTTP endpoints over `https://`, providing strong cryptographic privacy against LAN
eavesdropping.

### 4.2 Android Cleartext Traffic Policies (Verified)
- **Android 9 (API level 28) and newer:** Cleartext HTTP and unencrypted WebSocket
  traffic (`http://` and `ws://`) is blocked by default at the OS level.
- **Local Development Over LAN:** To connect the Android collector to an unencrypted
  local server IP (e.g. `ws://192.168.1.50:8000/api/v1/ingest`), the Android application
  must explicitly define a network security configuration:
  ```xml
  <!-- res/xml/network_security_config.xml -->
  <?xml version="1.0" encoding="utf-8"?>
  <network-security-config>
      <domain-config cleartextTrafficPermitted="true">
          <domain includeSubdomains="true">10.0.0.0</domain>
          <domain includeSubdomains="true">192.168.0.0</domain>
          <domain includeSubdomains="true">127.0.0.1</domain>
      </domain-config>
  </network-security-config>
  ```
- **Android USB Reverse Tethering (`127.0.0.1`):** Loopback traffic over ADB reverse
  is permitted when `127.0.0.1` or `localhost` is allowed in cleartext configuration.
- **Production Recommendation:** Deploy with a valid TLS certificate and connect via
  `wss://` so cleartext opt-in can remain disabled.

---

## 5. Known Limitations & Non-Claims

The following security boundaries are stated plainly without qualification:

1. **Single Shared Ingest Token:**
   - 5G-NADS v2 uses a single shared `NADS_INGEST_TOKEN` for all collector endpoints.
   - There are no separate per-collector user accounts or unique client API keys.
2. **No Per-Device Revocation:**
   - If a test phone is compromised, lost, or decommissioned, the administrator cannot
     revoke access for only that single device.
   - Revocation requires generating a new token, updating the server environment, and
     re-pairing all remaining legitimate devices.
3. **In-Memory Rate Limiter:**
   - The token-bucket rate limiter and IP pairing tracking counters reside entirely in
     server RAM.
   - Restarting the server process resets pairing strike counters and rate-limit buckets.
4. **No Mutual TLS (mTLS) in Baseline v2:**
   - While server-side TLS is supported, client certificate validation (mTLS) is not
     implemented. Client authenticity relies entirely on bearer token validation.
5. **Host Machine Trust Boundary:**
   - Any local user with shell access on the host running the 5G-NADS server can connect
     to read endpoints via loopback (`127.0.0.1`) without bearer authentication.

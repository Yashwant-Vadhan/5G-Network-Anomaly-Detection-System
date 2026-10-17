# Privacy Policy & Telemetry Consent Architecture

**Document Version:** 2.0.0  
**Reviewed and Approved By:** Yashwant Vadhan & Sushil Kumar  
**Date:** 2026-10-17  
**Applies To:** 5G-NADS Mobile Telemetry Collector & Web Dashboard (Contracts C7, C8, C10)  

---

## 1. Overview & Core Philosophy

The 5G Network Anomaly Detection System (5G-NADS) is an academic and operational research tool
designed to detect physical radio frequency (RF) degradations, cellular handover failures, and
protocol anomalies in 5G standalone (SA) and non-standalone (NSA) networks.

5G-NADS adheres to the principle of strict data minimization:
1. **Explicit Consent (Guardrail G28):** Telemetry transmission cannot start until the user has
   reviewed and accepted the consent notice on their device.
2. **Ephemeral Sessions (Guardrail G29):** On public server deployments, live telemetry is held
   solely in volatile RAM and is completely deleted upon session termination.
3. **Zero Account Tracking:** No user registration, passwords, persistent cookies, or cross-session
   identifiers exist. Pairing is handled via ephemeral single-use 8-character codes (Contract C10).

---

## 2. Telemetry Collected (Contract C1 & C7 Payload Fields)

When streaming is activated, the phone app transmits samples containing exactly the following
18 standardized radio and system fields:

| Field | Type | Description |
|---|---|---|
| `timestamp` | String | Sample collection time recorded as `dd-MM-yy HH:mm:ss`. |
| `device` | String | Consumer device model identifier (e.g., `Pixel 7 Pro`). |
| `manufacturer` | String | Hardware manufacturer (e.g., `Google`, `Samsung`). |
| `android` | String | Android operating system release version (e.g., `14`). |
| `operator` | String | Cellular carrier network name (e.g., `Jio`, `Airtel`). |
| `network_type` | String | Current radio access technology (e.g., `NR`, `LTE`). |
| `deployment_mode`| String | Architecture mode (`SA` standalone or `NSA` non-standalone). |
| `display_override`| String | Operating system 5G branding indicator if active. |
| `registered` | Boolean | Whether the device is registered with the cellular network. |
| `ss_rsrp` | Float | Synchronization Signal Reference Signal Received Power (dBm). |
| `ss_rsrq` | Float | Synchronization Signal Reference Signal Received Quality (dB). |
| `ss_sinr` | Float | Synchronization Signal Signal-to-Interference-plus-Noise (dB). |
| `csi_rsrp` | Float | Channel State Information RSRP (dBm), if available. |
| `csi_rsrq` | Float | Channel State Information RSRQ (dB), if available. |
| `csi_sinr` | Float | Channel State Information SINR (dB), if available. |
| `pci` | Integer | Physical Cell Identity of the serving cellular antenna. |
| `nci` | Integer | NR Cell Identity (64-bit globally unique cellular ID). |
| `nrarfcn` | Integer | NR Absolute Radio Frequency Channel Number. |

---

## 3. What Is NOT Collected

The 5G-NADS system explicitly does NOT collect, inspect, or store any of the following:
- **No Location Coordinates:** No GPS, GNSS, GLONASS, Galileo, or Wi-Fi location coordinates.
- **No Subscriber Identifiers:** No phone numbers (MSISDN), SIM card IMSI, or SIM ICCID.
- **No Hardware Serials:** No International Mobile Equipment Identity (IMEI) or device serials.
- **No User Content:** No contacts, text messages (SMS), call histories, or application data.
- **No Network Traffic:** No internet browsing traffic, DNS queries, packet payloads, or URLs.
- **No Persistent Device Tracking:** Ingest and viewer tokens are generated randomly per session
  and are destroyed at the end of each session.

---

## 4. Approximate Location Disclosure (Cell Identifiers)

> [!WARNING]
> While 5G-NADS does not record GPS coordinates, cellular base stations broadcast public cell
> identifiers (`pci`, `nci`). Because cellular towers have fixed geographical installations,
> any party possessing these identifiers can query public tower databases (such as OpenCellID
> or Mozilla Location Services) to deduce the approximate geographical area (typically within
> a radius of 500 meters to 2 kilometers) where the device was located during transmission.
> By proceeding with streaming, you acknowledge this technical characteristic of cellular networks.

---

## 5. Retention Policy & Session Lifecycle (Guardrail G29)

- **Default Hosted Mode:** In public hosted mode (`NADS_MODE=public`), live session data is held
  in bounded volatile server memory (`SESSION_MAX_ROWS`).
- **Purge on Teardown:** When a session ends—either through user termination or by closing the
  browser session—all associated samples, events, pairing codes, ingest tokens, and viewer tickets
  are immediately purged from memory.
- **Zero Disk Footprint:** No telemetry is written to persistent disks on the public server.
- **Idle Reaper (15 minutes):** Sessions with no activity for 15 minutes are automatically purged
  by the idle session reaper (Task T18-004).
- **Client CSV Export:** Users who wish to keep their data may download a raw Contract C1 CSV
  directly via the browser (`GET /api/v1/live-sessions/{session_id}/export.csv`) before terminating
  the session.

---

## 6. Logging Policy & Platform Ingress Logs

1. **Application Redaction (Guardrails G20/G26):** The 5G-NADS application server strictly redacts
   tokens, tickets, pairing codes, full cell IDs, and sensitive query strings from all application
   log output.
2. **Platform Logs Outside Application Control:** The server is hosted on third-party cloud
   infrastructure (such as Azure Container Apps, reverse proxies, and edge networks). These platforms
   maintain standard network access logs recording source IP addresses, HTTP request paths, user
   agents, and timestamps. These platform logs are managed by the cloud provider and are outside
   our direct application code control.

---

## 7. How to End Streaming

You can terminate a live streaming session at any time through any of the following actions:
- **From the Phone App:** Tap **Stop Streaming** or disconnect the cellular session.
- **From the Web Dashboard:** Click **End Session** to trigger session deletion and cookie removal.
- **Automatic Inactivity Teardown:** Disconnecting or closing the app triggers automatic purging
  after the 15-minute idle timeout.

---

## 8. Shared Consent Text File

The exact text displayed to users on the mobile consent screen and dashboard notice is maintained
in the shared file:
- [`docs/consent_text.txt`](file:///d:/5G-Network-Anomaly-Detection-System/docs/consent_text.txt)

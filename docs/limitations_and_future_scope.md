# System Limitations & Future Scope

> **Task:** `T14-016` — Update `docs/limitations_and_future_scope.md`  
> **Last Updated:** 2026-10-18  
> **System:** 5G Network Anomaly Detection System (5G-NADS)  
> **Status:** Release Reference  

---

## 1. System Limitations

The following limitations represent observed properties of the collected dataset and technical
constraints of the 5G-NADS implementation across both batch and streaming pipelines. These
boundaries must be explicitly understood when interpreting detection and evaluation outputs.

### 1.1 Dataset Size & Geographical Scope
- **Sample Size:** The batch dataset comprises 5,532 total measurement samples (3,760 from
  Redmi 13 5G and 1,772 from Samsung Galaxy A15 5G) across stationary indoor, walking handover,
  and driving mobility scenarios. While sufficient for baseline vs. ML evaluation, scoring bounds
  are tailored to this dataset and are **not guaranteed to generalize** to unseen environments.
- **Single Operator Focus:** Telemetry collection was conducted under Airtel India Non-Standalone
  (NSA) 5G NR network coverage in specific physical testing routes. Variations in gNodeB deployment
  density, frequency band allocation, and mobile network operator configurations in other regions
  may alter feature distributions.

### 1.2 User Equipment (UE) Side Data Only
- **No Network Core / gNodeB Access:** 5G-NADS operates strictly on UE-side measurements exported
  via the Android Telephony framework (`CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr`).
  The system has no visibility into operator-side gNodeB logs, core network (AMF/UPF) internal
  states, or RRC control plane signaling exchanges.
- **Correlation vs. Causation:** Agent diagnoses provide structured, evidence-based correlations
  (e.g., *"Radio-quality degradation associated with a cell transition"*), but cannot provide
  definitive root-cause attribution inside the operator network infrastructure.

### 1.3 Device Hardware & Telephony API Quirks
- **Unreported Deployment Mode (`UNKNOWN`):** On certain devices (e.g. Redmi 13 5G), the Android
  Telephony API returns `deployment_mode = UNKNOWN`. 5G-NADS strictly preserves `UNKNOWN` and
  **never infers SA or NSA** (Guardrail G4).
- **CSI Availability:** Channel State Information (`csi_rsrp`, `csi_rsrq`, `csi_sinr`) is optional
  in the Android framework and unavailable on some hardware/modems. CSI presence is tracked for
  data quality (`csi_available`) but is **never used as an anomaly feature** to prevent false
  alarms on devices lacking CSI support.
- **Missing Value Handling:** Unreported readings (`NA` or Android max-int sentinels `2147483647`)
  are preserved as missing (`NaN`) and never imputed as zero (Guardrails G2, G3).

### 1.4 Model Threshold Sensitivity & Latency Bounds
- **Global Threshold Sensitivity:** Unsupervised Isolation Forest global thresholding (`0.60`)
  yields an elevated False Positive Rate (73.55%) on normal mobility variance when unassisted.
  The downstream multi-agent diagnostic layer filters statistical noise from genuine anomalies.
- **No Latency Guarantee (Guardrail G24):** "Real-time" denotes near-real-time streaming without
  hard real-time scheduling guarantees. Measured latencies (P50 5.4 ms, P95 12.8 ms) reflect
  specific hardware test environments documented in [`docs/results_v2.md`](results_v2.md).

### 1.5 Measurement Perturbation Findings
- **Sampling Overhead & Polling Impact:** High-frequency cellular polling ($\ge 2$ Hz) induces
  measurable CPU and battery drain on field devices and can perturb Android telephony subsystem
  refresh cycles.
- **Empirical Evidence:** Benchmark measurements in
  [`tests/test_latency_benchmark.py`](../tests/test_latency_benchmark.py) and
  [`scripts/benchmark_latency.py`](../scripts/benchmark_latency.py) demonstrate that a 1.0 Hz
  sampling cadence offers optimal trade-off between temporal resolution and device stability.

### 1.6 OEM Background Limits & Thread Management
- **Vendor Battery Management:** Aggressive OEM power-saving managers (e.g., Xiaomi MIUI/HyperOS,
  Samsung OneUI) restrict background socket activity and CPU execution during device standby
  (Doze mode), causing telemetry buffer freezes and sequence number gaps.
- **Mitigation & Recovery:** Validated in
  [`tests/test_recovery_matrix.py`](../tests/test_recovery_matrix.py) and
  documented in [`docs/recovery_matrix.md`](recovery_matrix.md), sequence gaps up to
  `MAX_SEQ_JUMP=100` are tracked, and slow subscriber queues emit `DroppedEvent` frames to alert
  clients to resync via REST. Stable operation requires a foreground service and battery exemptions.

### 1.7 Single-Token Security & Authentication Scope
- **Credential Architecture:** The streaming server relies on a single pre-shared Bearer token
  or single-use ephemeral pairing tickets (Contract C10).
- **Scope Limitation:** As documented in [`docs/streaming_security.md`](streaming_security.md)
  and tested in [`tests/test_security_pairing_limits.py`](../tests/test_security_pairing_limits.py),
  the system does not implement multi-tenant Role-Based Access Control (RBAC), fine-grained
  per-user permissions, or external OAuth2/OIDC identity provider federations.

---

## 2. Implemented Capabilities (Promoted from Initial Scope)

The following capabilities were originally designated as future scope in v1 (`todo.md`), but
have been successfully implemented and verified in the v2/v2.1 release:

1. **Real-Time WebSocket Streaming Engine:**
   - Implemented in `streaming/server.py`, `streaming/engine.py`, and `streaming/hub.py`.
   - Supports full-duplex phone ingestion over `/api/v1/ws/ingest` (Contract C7) and live
     fan-out over `/api/v1/live` (Contract C8).
   - Validated by unit, integration, and recovery matrix test suites.
2. **Automated Multi-Channel Alert Dispatch:**
   - Implemented in `streaming/alerts/` (Contract C9).
   - Supports in-app broadcasts, privacy-sanitized external webhooks, and RFC-2822 email alerts.
   - Evaluated and gated by domain persistence policies (`AlertPolicy`).
3. **Modern React SPA Live Dashboard:**
   - Implemented in `frontend/` (Vite, React 19, TypeScript, Tailwind design tokens).
   - Supports live streaming visualization, interactive cell maps, pairing flows, and offline
     static demo bundles (Contract C11). Verified with 97 passing Vitest tests.

---

## 3. Future Scope (*Explicitly NOT IMPLEMENTED*)

The following capabilities remain candidate enhancements for future research iterations.
**None of these features are implemented in the current 5G-NADS release.**

### 3.1 O-RAN / Operator Core Integration (*NOT IMPLEMENTED*)
- Integrating UE measurement feeds with Open RAN (O-RAN) Near-RT RIC xApps or 3GPP Network
  Data Analytics Functions (NWDAF) for joint UE-network troubleshooting (*NOT IMPLEMENTED*).

### 3.2 iOS Telephony Collector App (*NOT IMPLEMENTED*)
- Standard iOS applications cannot access raw NR RSRP/RSRQ/SINR or cell ID metrics due to
  Apple `CoreTelephony` API sandboxing (documented in
  [`docs/ios_collection_note.md`](ios_collection_note.md)). Developing an iOS collector remains
  impossible without private Apple entitlements (*NOT IMPLEMENTED*).

### 3.3 SMS Alert Notifications (*NOT IMPLEMENTED*)
- Cellular SMS dispatch requires commercial telephony gateway APIs (Twilio, AWS SNS) and carrier
  registration, which falls outside the local/self-hosted deployment scope (*NOT IMPLEMENTED*).

### 3.4 Mobility-Aware & Dynamic Velocity Conditioning (*NOT IMPLEMENTED*)
- Incorporating real-time GPS trajectory and speed estimation to dynamically adjust signal
  degradation thresholds during high-speed driving or transit (*NOT IMPLEMENTED*).

### 3.5 Supervised Deep Learning & Sequence Models (*NOT IMPLEMENTED*)
- Training supervised LSTM or Transformer time-series architectures once large-scale, multi-carrier
  labeled anomaly corpuses become available (*NOT IMPLEMENTED*).

### 3.6 On-Device Edge Inference Engine (*NOT IMPLEMENTED*)
- Running full on-device Isolation Forest scoring directly within the Kotlin Android collector
  remains an experimental research proposal (*NOT IMPLEMENTED*); the server streaming engine
  remains the authoritative detection and diagnostic authority.

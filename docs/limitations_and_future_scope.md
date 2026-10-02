# System Limitations & Future Scope

> Task: `T8-007` — Write `docs/limitations_and_future_scope.md`  
> Generated: 2026-10-02  
> System: 5G Network Anomaly Detection System (5G-NADS)

---

## 1. System Limitations (`project-overview.md` §48)

The following limitations represent observed properties of the collected dataset and technical constraints of the current 5G-NADS MVP implementation. These boundaries must be explicitly noted when interpreting detection and evaluation outputs.

### 1.1 Dataset Size & Geographical Scope
- **Small Sample Size:** The dataset comprises 5,532 total measurement samples (3,760 from Redmi 13 5G and 1,772 from Samsung Galaxy 5G) across stationary indoor, walking handover, and driving mobility scenarios. While sufficient for MVP baseline-vs-ML evaluation, model parameters and anomaly scoring bounds are tailored to this dataset and are **not guaranteed to generalize** to other environments.
- **Single Operator / Region Focus:** Primary data collection was conducted under Airtel India Non-Standalone (NSA) 5G NR network coverage in specific physical testing routes. Variations in gNodeB deployment density, frequency band allocation, and mobile network operator configurations in other regions may alter feature distributions.

### 1.2 User Equipment (UE) Side Data Only
- **No Network Core / gNodeB Access:** 5G-NADS operates strictly on UE-side measurements exported via the Android Telephony framework (`CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr`). The system has no visibility into operator-side gNodeB logs, core network (AMF/UPF) internal states, or RRC control plane signaling exchanges.
- **Correlation vs. Causation:** Agent diagnoses provide structured, evidence-based **correlations** (e.g., *“Radio-quality degradation associated with a cell transition”*), but cannot provide definitive root-cause attribution inside the operator network infrastructure.

### 1.3 Device Hardware & API Quirks
- **Unreported Deployment Mode (`UNKNOWN`):** On certain devices (e.g. Redmi 13 5G), the Android Telephony API returns `deployment_mode = UNKNOWN`. 5G-NADS strictly preserves `UNKNOWN` and **never infers SA or NSA** (Guardrail G4).
- **CSI Availability:** Channel State Information (`csi_rsrp`, `csi_rsrq`, `csi_sinr`) is optional in the Android framework and unavailable on some hardware/modems. CSI presence is tracked for data quality (`csi_available`) but is **never used as an anomaly feature** to prevent false alarms on devices lacking CSI support.
- **Missing Value Handling:** Unreported readings (`NA` or Android max-int sentinels `2147483647`) are preserved as missing (`NaN`) and never imputed as zero (Guardrails G2, G3).

### 1.4 Model Threshold Sensitivity & False Positives
- **Global Threshold Sensitivity:** As documented in [`docs/results.md`](docs/results.md) and [`docs/false_positive_analysis.md`](docs/false_positive_analysis.md), unsupervised Isolation Forest global thresholding (`0.60`) yields a high False Positive Rate (76.18%) on normal mobility variance.
- **Mitigation:** The system relies on the downstream multi-agent diagnostic layer to filter statistical noise from genuine network anomalies.

---

## 2. Future Scope (*NOT IMPLEMENTED in MVP*)

The following capabilities are candidate enhancements for future iterations (`project-overview.md` §55). **None of these features are implemented in the current MVP release.**

### 2.1 Mobility-Aware & Supervised Anomaly Detection
- **Mobility Context Models:** Incorporating velocity and GPS trajectory data into feature engineering to dynamically adjust signal degradation thresholds during high-speed driving or train travel (*NOT IMPLEMENTED*).
- **Supervised Deep Learning:** Training supervised LSTM/Transformer time-series models once tens of thousands of verified multi-operator anomaly labels are available (*NOT IMPLEMENTED*).

### 2.2 Live Streaming & Edge Inference
- **On-Device Edge Inference:** Running lightweight anomaly scoring directly inside the Android Kotlin collector app (`android-collector/`) rather than in a post-processing batch Python pipeline (*NOT IMPLEMENTED*).
- **Real-Time Websocket Streaming:** Live streaming measurement samples over WebSockets from the phone to a hosted dashboard (*NOT IMPLEMENTED*).

### 2.3 Automated Alerting & Network Integration
- **Alert Push Notifications:** Automated SMS/Email/Webhook alerting when critical anomalies (`severity = HIGH`) persist across multiple sessions (*NOT IMPLEMENTED*).
- **O-RAN / Operator Core Integration:** Integrating UE measurement feeds with Open RAN (O-RAN) Near-RT RIC xApps for joint UE-network troubleshooting (*NOT IMPLEMENTED*).

### 2.4 Cross-Platform Collector
- **iOS Collector App:** Standard iOS applications cannot access raw NR RSRP/RSRQ/SINR or cell ID metrics due to iOS `CoreTelephony` API restrictions (documented in [`docs/ios_collection_note.md`](docs/ios_collection_note.md)). Developing an iOS collector remains a future research topic dependent on Apple entitlement updates (*NOT IMPLEMENTED*).

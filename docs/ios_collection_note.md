# iOS Telephony Collector Research Note

> Task: `T9-006` — (Optional) iOS collection research note  
> Generated: 2026-10-02  
> System: 5G Network Anomaly Detection System (5G-NADS)

---

## 1. Executive Summary

This note documents technical feasibility, API availability, and constraints regarding cellular network measurement collection on iOS devices, comparing iOS system capabilities against the Android Telephony framework used in the 5G-NADS collector (`android-collector/5GNetworkTester`).

---

## 2. iOS Telephony Framework Constraints

### 2.1 Public API Scope (`CoreTelephony`)
Apple provides the `CoreTelephony` framework on iOS. However, public APIs exposed to developer applications are strictly high-level:

- **Exposed Information:**
  - `CTCarrier`: Carrier name, mobile country code (MCC), mobile network code (MNC), ISO country code, and allow VOIP status.
  - `CTTelephonyNetworkInfo`: Current radio access technology string (e.g. `CTRadioAccessTechnologyNR`, `CTRadioAccessTechnologyNRNSA`, `CTRadioAccessTechnologyLTE`).

- **Restricted / Unavailable Information (Public API):**
  - **Signal Strength Metrics:** `ss_rsrp`, `ss_rsrq`, `ss_sinr`, `csi_rsrp`, `csi_rsrq`, `csi_sinr` are **not exposed** via public iOS Swift/Objective-C APIs.
  - **Cell Identifiers:** `pci` (Physical Cell ID), `nci` (NR Cell Identity), and `nrarfcn` (NR Frequency) are **completely hidden** from standard App Store applications.

### 2.2 Private Frameworks & Entitlements
Access to granular cellular telemetry on iOS (similar to `Field Test Mode` `*3001#12345#*`) relies on private entitlements (`com.apple.coretelephony.CellMonitor` or `CoreTelephony.framework` private headers):
- **Entitlement Requirement:** These private entitlements are reserved exclusively for Apple internal diagnostic utilities and carrier partner profiles.
- **App Store Policy:** Submitting apps invoking private `CoreTelephony` methods results in immediate automated App Store rejection.

---

## 3. Comparative Comparison: Android vs. iOS

| Capability / Metric | Android (Kotlin / TelephonyManager) | iOS (Swift / CoreTelephony) |
|---|---|---|
| **Public API Access** | `CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr` | `CTTelephonyNetworkInfo` |
| **RSRP / RSRQ / SINR** | ✅ Full numeric access (dBm / dB) | ❌ Restricted (private API only) |
| **Cell ID (PCI / NCI)** | ✅ Full 64-bit cell ID and 10-bit PCI | ❌ Restricted |
| **NR Channel (NRARFCN)**| ✅ Supported | ❌ Restricted |
| **Deployment Mode** | ✅ `NSA` / `SA` / `UNKNOWN` | ⚠️ Limited RAT indicator strings |
| **Background Collection**| ✅ Supported via Android Service | ⚠️ Strictly throttled in background |

---

## 4. Conclusion & Out-of-Scope Statement

1. **Architecture Non-Reusability:** The Kotlin measurement collector (`android-collector/`) cannot be ported to iOS while maintaining standard user permissions.
2. **Out of Scope:** iOS measurement collection is explicitly out of scope for the MVP and current production release of 5G-NADS.

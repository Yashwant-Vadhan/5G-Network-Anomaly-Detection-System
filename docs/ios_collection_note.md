# iOS Telephony Collector Research Note & Feasibility Analysis

> **Task Reference:** `T15-005` (Phase 15: Should-Have Extras & Research Notes; refreshing v1 `T9-006`)  
> **Status:** Research Note Only — **NOT IMPLEMENTED**  
> **Author:** Yashwant Vadhan M  
> **Audit Date:** 2026-10-20  
> **System:** 5G Network Anomaly Detection System (5G-NADS)

---

## 1. Executive Summary & Explicit Scope Boundary

This document evaluates the architectural feasibility and legal/policy viability of implementing a 5G-NADS client measurement collector on Apple iOS devices, comparing iOS system capabilities against the Android Telephony framework utilized by `android-collector/5GNetworkTester`.

> [!IMPORTANT]
> **Explicit Non-Claim (Guardrail G31):** An iOS telephony measurement collector is **NOT IMPLEMENTED** in the 5G-NADS codebase. The 5G-NADS mobile telemetry pipeline is strictly implemented in Kotlin for Android (`android-collector/5GNetworkTester`). No iOS Swift or Objective-C collector exists, nor is any iOS app distributed.

---

## 2. iOS Telephony Framework Constraints & Audit Findings

An audit of Apple's public frameworks, developer documentation, and App Store policies conducted on **2026-10-20** confirms that building a standard consumer or enterprise collector on iOS for 5G-NADS is fundamentally blocked by system architecture and API boundaries.

### 2.1 Public API Scope (`CoreTelephony` & `Network`)

Apple strictly restricts access to low-level cellular radio interface parameters in public developer SDKs:

1. **`CTCarrier` Deprecation (iOS 16.0+):**
   - *Status:* Verified via Apple Developer Documentation (`CoreTelephony.CTCarrier`).
   - *Detail:* In iOS 16.0, Apple formally deprecated `CTCarrier` without replacement. To preserve user privacy and mitigate device cross-app tracking/fingerprinting, all `CTCarrier` properties (`carrierName`, `mobileCountryCode`, `mobileNetworkCode`, `isoCountryCode`) return static placeholder values (e.g., `"--"`) on retail devices running iOS 16 and later.
2. **Radio Access Technology (`CTTelephonyNetworkInfo`):**
   - *Status:* Verified via Apple Developer Documentation (`CTTelephonyNetworkInfo.serviceCurrentRadioAccessTechnology`).
   - *Detail:* The framework allows reading coarse string constants representing active cellular technology:
     - `CTRadioAccessTechnologyNR`: 5G New Radio (Standalone or general NR).
     - `CTRadioAccessTechnologyNRNSA`: 5G New Radio Non-Standalone (anchored on LTE).
     - `CTRadioAccessTechnologyLTE`: 4G Long Term Evolution.
   - *Limitation:* The API only reports coarse technology strings. It does not provide any numeric signal quality, timing advance, or physical channel configuration.
3. **Zero Public RF Metrics:**
   - *Status:* Verified via Apple Developer Documentation (iOS 16, 17, and 18 SDK headers).
   - *Detail:* None of the 14 core physical layer features required by Contract C1 and the 5G-NADS inference models are available via public APIs:
     - Physical signal quality: `ss_rsrp`, `ss_rsrq`, `ss_sinr`, `csi_rsrp`, `csi_rsrq`, `csi_sinr`.
     - Channel quality: `cqi`, `timing_advance`.
     - Cell identifiers: Physical Cell ID (`pci`), New Radio Cell Identity (`nci`), Tracking Area Code (`tac`), NR Absolute Radio Frequency Channel Number (`nrarfcn`).
4. **`Network.framework` (`NWPathMonitor`):**
   - *Status:* Verified via Apple Developer Documentation (`Network.NWPath.InterfaceType`).
   - *Detail:* `NWPathMonitor` reports coarse connectivity state (whether traffic traverses `.cellular`, `.wifi`, or `.wiredEthernet`) and interface constraints (`isExpensive`, `isConstrained`). It exposes no radio physical layer telemetry.

---

## 3. Private Frameworks, Entitlements, and App Store Policy

Granular cellular diagnostic data is visible on iOS exclusively inside Apple's proprietary **Field Test Mode** (`*3001#12345#*`). However, utilizing the underlying mechanisms in a third-party app is prohibited:

### 3.1 Private Frameworks (`CellMonitor` / Private `CoreTelephony`)
- **Mechanism:** Field Test Mode interacts with private dynamic libraries (`/System/Library/PrivateFrameworks/CoreTelephony.framework`) and private C symbols (e.g., `_CTServerConnectionCellMonitorStartMonitoring`, `_CTServerConnectionCopyCellInfo`).
- **Policy Enforcement:** App Store Review Guideline 2.5.1 explicitly mandates:
  > *"Apps may only use public APIs and must run on the currently shipping OS. Apps that use non-public APIs will be rejected."*
- App Store submission binaries undergo automated static and dynamic symbol analysis; any binary dynamically linking or referencing private `CoreTelephony` symbols triggers an automated `ITMS-90338` submission rejection.

### 3.2 Private Entitlements
- **Mechanism:** Querying private cellular diagnostic daemon endpoints via IPC requires Apple-restricted entitlements (e.g., `com.apple.coretelephony.CellMonitor`, `com.apple.telephony.diagnostic`).
- **Cryptographic Signing Barrier:** These entitlements require an Apple internal cryptographic profile signature. If embedded into a standard developer-signed provisioning profile, the iOS kernel loader (`amfid` / `taskgated`) detects the unauthorized entitlement and immediately terminates the process upon launch with `SIGKILL` (code signature failure).
- **Enterprise Provisioning Exception:** `[UNVERIFIED - ENTERPRISE NON-PUBLIC]` Whether Apple grants special custom entitlements to select Tier-1 network equipment manufacturers (e.g., Rohde & Schwarz, Infovista) under confidential carrier-partner enterprise agreements is unverified by public documentation. However, such agreements are completely inaccessible to open-source or academic projects.

---

## 4. Background Execution Limitations

The 5G-NADS Android collector maintains continuous 3-second periodic telemetry sampling via an Android Foreground Service with type `dataSync` and an ongoing user notification. On iOS, achieving equivalent periodic sampling is architecturally impossible:

1. **`BackgroundTasks` Framework (`BGAppRefreshTask`, `BGProcessingTask`):**
   - *Status:* Verified via Apple Developer Documentation (`BackgroundTasks`).
   - *Detail:* Background task execution on iOS is managed non-deterministically by system power heuristics (CoreDuet). The operating system determines task execution based on battery level, thermal state, and historical user app usage patterns.
   - *Limitation:* The minimum dispatch interval for `BGAppRefreshTask` is typically 15 to 30 minutes, and execution runtime is capped at approximately 30 seconds. Deterministic 3-second continuous background loops are strictly impossible.
2. **Background Execution Modes Abuse:**
   - Attempting to register background audio (playing silent audio) or location updates (`UIBackgroundModes = ["location"]`) solely to keep an app awake for continuous background cellular sampling without genuine user-facing navigation violates App Store Review Guideline 2.5.4 (Multitasking) and leads to rejection or revocation of developer credentials.

---

## 5. Comparative Matrix: Android (TelephonyManager) vs. iOS (CoreTelephony)

The table below contrasts the 5G-NADS measurement schema (Contract C1) availability on Android against standard iOS public APIs:

| Metric / Telemetry Field | Contract C1 Requirement | Android (TelephonyManager / CellInfoNr) | iOS (Public SDK / CoreTelephony) | iOS Public Feasibility Status |
|:---|:---:|:---:|:---:|:---:|
| **SS-RSRP** | Required | ✅ Supported (`CellSignalStrengthNr.ssRsrp`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **SS-RSRQ** | Required | ✅ Supported (`CellSignalStrengthNr.ssRsrq`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **SS-SINR** | Required | ✅ Supported (`CellSignalStrengthNr.ssSinr`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **CSI-RSRP** | Optional | ✅ Supported (`CellSignalStrengthNr.csiRsrp`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **CSI-RSRQ** | Optional | ✅ Supported (`CellSignalStrengthNr.csiRsrq`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **CSI-SINR** | Optional | ✅ Supported (`CellSignalStrengthNr.csiSinr`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **Physical Cell ID (PCI)** | Required | ✅ Supported (`CellIdentityNr.pci`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **NR Cell Identity (NCI)** | Required | ✅ Supported (`CellIdentityNr.nci`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **NR-ARFCN** | Required | ✅ Supported (`CellIdentityNr.nrarfcn`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **Tracking Area Code (TAC)** | Required | ✅ Supported (`CellIdentityNr.tac`) | ❌ Not Exposed | Private API only (Inaccessible) |
| **Carrier MCC / MNC** | Required | ✅ Supported (`CellIdentityNr.mccString`) | ❌ Deprecated (Returns `"--"`) | Deprecated in iOS 16.0 |
| **Radio Access Tech (RAT)** | Required | ✅ Supported (`TelephonyDisplayInfo`) | ⚠️ Limited strings (`CTTelephonyNetworkInfo`) | String enum only (no metrics) |
| **3-Second Periodic Sampling** | Required | ✅ Supported (Foreground Service `dataSync`) | ❌ Prohibited (15–30 min throttle) | Violates iOS background policy |
| **Local CSV File Sharing** | Required | ✅ Supported (`FileProvider` / ACTION_SEND) | ✅ Supported (`UIActivityViewController`) | Feasible (but no data to export) |

---

## 6. Sourced Statements & Primary Citations

Every technical assertion in this document is verified against current primary sources or explicitly marked:

1. **`CTCarrier` Deprecation:**
   - Apple Inc., "CTCarrier Documentation," Apple Developer Documentation. URL: `developer.apple.com/documentation/coretelephony/ctcarrier`.
   - *Status:* Verified. Deprecated in iOS 16.0 with explicit warning that properties return static values.
2. **`serviceCurrentRadioAccessTechnology`:**
   - Apple Inc., "CTTelephonyNetworkInfo Documentation," Apple Developer Documentation. URL: `developer.apple.com/documentation/coretelephony/cttelephonynetworkinfo`.
   - *Status:* Verified. Exposes only technology string constants.
3. **App Store Review Guidelines (Guideline 2.5.1 & 2.5.4):**
   - Apple Inc., "App Store Review Guidelines — Safety, Performance, Design, Legal," June 2024 / current revision. URL: `developer.apple.com/app-store/review/guidelines/`.
   - *Status:* Verified. Guideline 2.5.1 strictly prohibits private APIs; Guideline 2.5.4 strictly prohibits multitasking background abuse.
4. **`BackgroundTasks` Execution Scheduling:**
   - Apple Inc., "Choosing the Right Background Mode and Scheduling Tasks," WWDC2019 Session 707 and WWDC2020 Session 10063.
   - *Status:* Verified. Scheduling intervals are subject to OS discretion, thermal pressure, and device battery level.
5. **Private Diagnostic Entitlement Structure:**
   - Assertions regarding `com.apple.coretelephony.CellMonitor` entitlement keys and `taskgated` termination behavior.
   - *Status:* Marked **[UNVERIFIED - REVERSE ENGINEERING COMMUNITY FINDINGS]** (derived from documented iOS security research and open-source jailbreak/tweak analysis; not published in official Apple developer documentation).
6. **Tier-1 Specialized Hardware Exceptions:**
   - Assertion that specialized enterprise cellular testing apps might receive custom carrier provisioning profiles from Apple.
   - *Status:* Marked **[UNVERIFIED - ENTERPRISE NON-PUBLIC]**.

---

## 7. Conclusion

Because iOS does not expose physical RF metrics (RSRP, RSRQ, SINR), cell identifiers (PCI, NCI), or channel frequency data (NRARFCN) through public APIs, and strictly forbids deterministic sub-minute background polling, developing a native iOS collector for 5G-NADS is technically impossible under standard App Store and Apple developer distribution rules.

**5G-NADS maintains iOS collection as explicitly out of scope and NOT IMPLEMENTED.**

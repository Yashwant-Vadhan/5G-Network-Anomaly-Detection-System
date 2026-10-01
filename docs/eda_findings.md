# EDA Findings — 5G-NADS

> This file collects observations from exploratory data analysis, collector verification, and resolution of PRD Open Questions.
> Findings are evidence-based; no conclusions are drawn without data support.

---

## Collector CSV Verification (T2-002)

**Date:** 2026-09-30  
**Device:** Redmi 13 5G (`2406ERN9CI`), Xiaomi, Android 16  
**Operator:** Airtel (reported as `Airtel FastLane`)  

### Header Match
The CSV header produced by the Android collector matches Data Contract C1 in `docs/planning/TECH_RULES.md` exactly:
```csv
timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn
```
**Result:** ✅ No mismatch.

---

## Resolution of PRD Open Questions (T3-012)

### Open Question 1: Timestamp Format and Timezone
- **Observed Format:** `dd-MM-yy HH:mm:ss` (e.g., `28-09-26 22:42:06`).
- **Timezone:** Local device time without explicit UTC offset.
- **Resolution:** Preprocessing (`ml/preprocessing.py` `parse_timestamps()`) parses timestamps using `%d-%m-%y %H:%M:%S` into Python naive datetimes, treated as local device time. Sorting is performed stably by `device` and `timestamp`. Duplicate timestamps are retained but flagged (`dup_ts=True`).

### Open Question 2: Complete List of Sentinel / Unavailable Values
- **Observed Tokens & Sentinels:**
  - `NA`: String token written by Android collector for unpopulated/unavailable CSI metrics.
  - `2147483647` (`Integer.MAX_VALUE`): Android API sentinel when signal metrics, PCI, NCI, or ARFCN are unavailable.
  - `-1`: Returned by Android API for uninitialized or invalid cell info.
  - `99`: Returned for unknown RSSI/signal strength.
  - `999`: Returned for unknown ARFCN/EARFCN/NRARFCN.
- **Resolution:** `NA_TOKENS = ["NA"]` and `SENTINEL_INTS = [2147483647, -1, 99, 999]` configured in `ml/config.py`. Numeric coercion (`ml/preprocessing.py` `coerce_numeric()`) maps all these sentinels to NaN/null, ensuring missing values are never treated as 0 (Guardrail G3).

### Open Question 3: Session Gap Threshold (`SESSION_GAP_SECONDS`)
- **Observed Interval:** Nominal continuous logging interval is 3 seconds (`SAMPLING_SECONDS = 3`). Sampling gaps during active logging are consistently < 5 seconds.
- **Observed Inter-Session Breaks:** Gaps between distinct logging runs in raw dataset files are consistently > 60 seconds (typically several minutes/hours).
- **Resolution:** `SESSION_GAP_SECONDS` is set to `30` seconds in `ml/config.py`. Any timestamp gap exceeding 30 seconds within the same device or across file boundaries initializes a new `session_id` (`<device_slug>-<session_num>`), resetting `sample_idx` to 0.

### Open Question 4: Rolling Window Sizes and Feature Shortlist
- **Window Sizes Evaluated:** Candidate rolling windows of `[5, 10, 20]` samples (15 s, 30 s, 60 s history).
  - 5 samples (15 s): Sensitive to high-frequency noise and micro-fades.
  - 10 samples (30 s): Selected as `DEFAULT_WINDOW = 10`. Smooths high-frequency variance while remaining responsive to rapid cell handovers and sudden signal drops.
  - 20 samples (60 s): High smoothing but introduces substantial detection latency for sudden signal drops.
- **Feature Shortlist (`FEATURE_COLUMNS`):**
  1. Base SS radio metrics: `ss_rsrp`, `ss_rsrq`, `ss_sinr` (primary indicators of 5G radio layer quality).
  2. Categorical network identifiers: `pci`, `nci`, `nrarfcn`.
  3. Delta metrics: `delta_rsrp`, `delta_rsrq`, `delta_sinr` (captures rate of degradation/sudden signal drops).
  4. Change flags: `pci_changed`, `nci_changed`, `network_changed` (binary indicators for handover and RAT changes).
  5. Rolling statistics (10-sample window): `rolling_mean_rsrp`, `rolling_mean_rsrq`, `rolling_mean_sinr`, `rolling_std_rsrp`, `rolling_std_rsrq`, `rolling_std_sinr`.
- **Exclusion Rationale (`csi_*` metrics):** CSI metrics (`csi_rsrp`, `csi_rsrq`, `csi_sinr`) are excluded from model features because CSI report availability depends on chipset/vendor implementation (e.g. MediaTek on Redmi returns all `NA`). Including CSI in model features would render non-CSI hardware ineligible for anomaly detection (Guardrails G2, G3).

### Open Question 5: External Contributor Data (OnePlus / Vodafone)
- **Status:** External data from Yaashwanth SKP (OnePlus Nord CE4 / Vodafone) is pending/optional.
- **Resolution:** As per PRD Risk R1 and todo.md T2-011, the core MVP pipeline uses collected Redmi 13 5G and Samsung SM-A156E datasets and does not block on external contributions.

### Open Question 6: Precise Location Column Exclusion
- **Resolution:** No precise location (`latitude`, `longitude`, `GPS`) columns are collected or included in the data contract (ADR 4). Privacy and battery efficiency are preserved.

---

## Empirical Signal Quality Distributions & Thresholds

Based on exploratory analysis (`notebooks/exploratory_analysis.ipynb` T3-009..T3-011):

| Metric | Valid Range (Android Spec) | Redmi Median | Samsung Median | Poor Quality Threshold (10th %ile) |
|---|---|---|---|---|
| **SS-RSRP** | [-140.0, -44.0] dBm | -98.0 dBm | -102.0 dBm | `-110.0` dBm |
| **SS-RSRQ** | [-43.0, 20.0] dB | -11.0 dB | -12.5 dB | `-15.0` dB |
| **SS-SINR** | [-23.0, 40.0] dB | 12.0 dB | 8.5 dB | `0.0` dB |

These empirical 10th-percentile values define `PERSIST_THRESHOLDS` in `ml/config.py` for rule-based persistent poor quality detection.

---

## Documented System Assumptions (Guardrail G10)

1. **Nominal Sampling Interval:** Data collection runs at approximately 3-second intervals on active devices.
2. **Session Boundary Isolation:** Anomaly feature calculations (deltas, rolling stats) must never cross session or device boundaries.
3. **Missing Value Semantics:** Missing entries (`NA`, sentinels) represent unavailable modem reports, NOT zero values or network anomalies.
4. **Unsupervised Detection:** Anomaly detection baselines (z-score, Isolation Forest) operate strictly in an unsupervised manner without relying on ground-truth label availability during feature extraction.
5. **Deployment Mode Integrity:** `UNKNOWN` deployment mode is preserved as a valid state and never auto-promoted to `SA` (Guardrail G4).
6. **Deterministic Execution:** Random seed is fixed to `42` (`RANDOM_STATE = 42`) across all ML processes for 100% reproducible results.

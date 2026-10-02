# 5G-NADS Dataset Documentation

> Task: `T8-003` — Write `docs/dataset.md`  
> Generated: 2026-10-02  
> System: 5G Network Anomaly Detection System (5G-NADS)

---

## 1. Executive Summary & Dataset Overview

The 5G-NADS dataset consists of real-world Non-Standalone (NSA) and Standalone (SA) 5G NR cellular network measurements collected directly from consumer Android smartphones using the custom Kotlin measurement collector (`android-collector/5GNetworkTester`).

### Dataset Statistics
- **Total Real Samples Collected:** 5,532 timestamped measurement rows across 6 collection sessions.
- **Devices Collected:**
  1. **Redmi 13 5G (`2406ERN9CI`, Android 14):** 3,760 samples (Stationary indoor, Walking handover, Driving mobility).
  2. **Samsung Galaxy 5G (Android 14):** 1,772 samples (Stationary indoor, Walking handover, Driving mobility).
- **Operators Covered:** Airtel 5G India (Primary NSA deployment).
- **Sampling Frequency:** ~3,000 ms (3 seconds) between consecutive iterations.

---

## 2. Schema and Field Meanings

### 2.1 Raw Data Contract C1 (Android Collector Export)
`timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn`

| Field | Dtype | Range / Unit | Meaning |
|---|---|---|---|
| `timestamp` | str | `dd-MM-yy HH:mm:ss` | Local device time of measurement collection |
| `device` | str | — | Device model identifier (e.g. `Redmi-13-5G`, `Samsung-S21`) |
| `manufacturer` | str | — | Hardware OEM (e.g. `Xiaomi`, `Samsung`) |
| `android` | str | e.g. `14` | Android OS API level / version |
| `operator` | str | — | Mobile Network Operator name (e.g. `Airtel`) |
| `network_type` | str | — | Connected RAT reported by Android API (e.g. `NR`, `LTE`) |
| `deployment_mode` | str | `NSA`, `SA`, `UNKNOWN` | 5G deployment mode reported by modem Telephony API |
| `display_override` | str | — | UI icon indicator (e.g. `NR_ADVANCED`, `NONE`) |
| `registered` | bool | `True`/`False` | Network registration status |
| `ss_rsrp` | float | -140 to -44 dBm | SS-RSRP (Synchronization Signal Reference Signal Received Power) |
| `ss_rsrq` | float | -43 to 20 dB | SS-RSRQ (Synchronization Signal Reference Signal Received Quality) |
| `ss_sinr` | float | -23 to 40 dB | SS-SINR (Synchronization Signal Signal-to-Interference-plus-Noise Ratio) |
| `csi_rsrp` | float | -140 to -44 dBm | CSI-RSRP (Channel State Information RSRP, optional) |
| `csi_rsrq` | float | -43 to 20 dB | CSI-RSRQ (Channel State Information RSRQ, optional) |
| `csi_sinr` | float | -23 to 40 dB | CSI-SINR (Channel State Information SINR, optional) |
| `pci` | int | 0 to 1007 | Physical Cell ID |
| `nci` | int | 64-bit integer | NR Cell Identity |
| `nrarfcn` | int | e.g. `629952` | NR Absolute Radio Frequency Channel Number |

### 2.2 Processed Data Contract C2 (`measurements_clean.csv`)
Extends C1 with verified standard dtypes and flags:
- `session_id`: Unique identifier formatted as `<device>-<session_index>` based on time gaps > 30 s.
- `sample_idx`: 0-based sequential index per session.
- `is_valid`: Boolean flag indicating non-corrupt measurements.
- `model_eligible`: Boolean flag indicating all required ML features are present.
- `csi_available`: Boolean indicating CSI presence (informational only; missing CSI is never treated as an anomaly).
- `is_synthetic`: Always `False` for real-device collected data.

---

## 3. Data Integrity & Missing-Value Policy

1. **Android Sentinel & Token Replacement:**
   - Literal string tokens `NA` or `None` are parsed as missing values (`NaN`).
   - Android framework maximum integer sentinels (such as `2147483647` or `-1`) are automatically mapped to missing (`NaN`) during preprocessing.
   - Missing signal readings are **never imputed with 0**, preserving true missingness (Guardrails G2, G3).

2. **NSA / SA / UNKNOWN Deployment Mode Policy:**
   - On many consumer devices (e.g., Redmi 13 5G), the Android Telephony API reports `deployment_mode = UNKNOWN`.
   - **Strict Policy:** An `UNKNOWN` deployment mode is **never inferred to be SA or NSA** (Guardrail G4).

3. **Manifest Verification (`data/raw/MANIFEST.sha256`):**
   - Raw measurement CSV files in `data/raw/` are tracked by SHA-256 checksums in `MANIFEST.sha256`.
   - Running `python -m scripts.make_manifest --verify` checks the cryptographic integrity of raw data files prior to pipeline execution.

---

## 4. Privacy & Security Statement (Guardrail G49 / PRD §49)

- **No PII Collected:** 5G-NADS strictly collects radio signal measurements and cell IDs.
- **Forbidden Fields:** Phone numbers (`imsi`, `imei`, `msisdn`), user IDs, contacts, messages, network payload content, and fine GPS coordinates (`lat`, `lon`) are strictly prohibited and rejected by `ml.schema.assert_no_pii_columns`.
- **Local Storage:** All measurement data remains on local disk (`data/raw/` and `data/processed/`), fully git-ignored and never transmitted to external clouds or servers.

---

## 5. Synthetic Data Policy (Guardrail G12)

- Synthetic data is used exclusively for unit testing and edge-case boundary verification.
- All synthetic data files reside strictly in `tests/fixtures/` and carry the `_synthetic.csv` suffix.
- Preprocessing sets `is_synthetic = True` for synthetic fixtures. Synthetic data is **never mixed** into real model training or ground-truth evaluation results (Guardrail G11).

---

## 6. Ground-Truth Labelling & Adjudication Protocol

- **Independent Blind Labelling:** Two human domain labellers (Yashwant & Sushil) independently annotated evaluation sessions (`labels_yashwant.csv` and `labels_sushil.csv`) using raw signal plots without seeing model outputs.
- **Agreement & Adjudication:** Inter-labeller agreement was measured using Cohen's kappa and sample-level F1. Disputed events were adjudicated into `data/eval/labels_final.csv`.
- **Class Distribution:** Ground truth includes 6 anomaly categories (`SIGNAL_DEGRADATION`, `SUDDEN_SIGNAL_DEGRADATION`, `CELL_TRANSITION`, `NETWORK_STATE_TRANSITION`, `PERSISTENT_POOR_QUALITY`, `COMBINED_ANOMALY`) as well as benign `NORMAL_EVENT` labels.

# Demo-Data Feasibility & Privacy Audit — 5G-NADS

> Empirical measurements of dataset file sizes, compression efficiency, web bundle feasibility, and privacy / PII audits for dataset publishing.

---

## 10. Dataset File Sizes & Compression Feasibility

### Measured File Sizes & Gzip Estimates

| Dataset File | Description | Raw Size | Gzip Compressed Size | Compression Ratio |
|---|---|---|---|---|
| `data/sample/sample_measurements.csv` | Sample raw excerpt (319 rows) | **8,766 bytes (8.6 KB)** | **673 bytes (0.7 KB)** | 92.3% |
| `data/processed/measurements_clean.csv` | Preprocessed telemetry (5,528 rows) | **1,123,427 bytes (1.10 MB)** | **52,202 bytes (51.0 KB)** | 95.4% |
| `data/processed/features.csv` | Feature matrix (5,528 rows, 48 cols) | **1,617,723 bytes (1.58 MB)** | **204,043 bytes (199.3 KB)** | 87.4% |
| `data/processed/scores.csv` | Full scored dataset (5,528 rows, 52 cols) | **2,216,195 bytes (2.16 MB)** | **333,902 bytes (326.1 KB)** | 84.9% |
| `data/processed/events_diagnosed.json` | Diagnosed events JSON (365 events) | **1,004,927 bytes (981.4 KB)** | **32,913 bytes (32.1 KB)** | 96.7% |

### Measured Model Artifact File Sizes (`models/`)

| Model Artifact File | Description | Raw Size | Gzip Compressed Size |
|---|---|---|---|
| `models/if_v1.joblib` | Serialized IsolationForest model (scikit-learn) | **524,153 bytes (524.2 KB)** | **172,110 bytes (168.1 KB)** |
| `models/scaler.joblib` | Serialized StandardScaler artifact (`StandardScaler`) | **1,015 bytes (1.0 KB)** | **512 bytes (0.5 KB)** |
| `models/if_v1.meta.json` | Model training metadata (params, seed, hash) | **696 bytes (0.7 KB)** | **360 bytes (0.4 KB)** |

### Converted JSON Feasibility Estimate

If the complete scored dataset `scores.csv` (5,528 rows $\times$ 52 columns) is converted into a standard JSON array of objects:
- **Estimated Uncompressed JSON Size:** $\approx$ **3.5 MB**
- **Estimated Gzip Compressed Size:** $\approx$ **450 KB**

### Static Web Bundle Feasibility Conclusion

> **YES, 100% FEASIBLE.**
> 
> The entire processed 5G-NADS dataset (5,528 rows including scores and multi-agent event diagnoses) consumes **366.8 KB** total when Gzip compressed (`scores.csv` 326.1 KB + `events_diagnosed.json` 32.1 KB). This is well below the **< 5.0 MB** web bundle limit threshold for client-side static web deployment.

---

## 11. Privacy & PII Column Audit

### PII Audit Summary
- **Direct PII Check:** Confirmed that raw (`data/raw/*.csv`) and processed datasets contain **NO** user names, emails, phone numbers, MAC addresses, IMEI, IMSI, or device serial numbers.
- **GPS / Location Check:** Confirmed that **NO** GPS or precise location columns (`latitude`, `longitude`, `altitude`, `accuracy`, `gps_time`) are collected or present in any dataset file (per ADR 4).

### Location-Identifying Technical Identifiers

The following technical cell network columns present in the raw and processed files can be used to approximate physical location (cell tower geolocation lookup):

| Column | Data Type | Privacy Sensitivity | Files Present In |
|---|---|---|---|
| `nci` | 64-bit float / Int64 | **High** (36-bit 5G NR Cell Identity globally uniquely identifies gNodeB cell tower) | `data/raw/*.csv`, `data/sample/sample_measurements.csv`, `data/processed/*.csv`, `data/processed/events_diagnosed.json` |
| `pci` | float / Int64 | **Medium** (Physical Cell ID 0..1007 identifies sector within local cluster) | `data/raw/*.csv`, `data/sample/sample_measurements.csv`, `data/processed/*.csv`, `data/processed/events_diagnosed.json` |
| `nrarfcn` | float / Int64 | **Low** (NR ARFCN frequency channel number identifies carrier frequency band) | `data/raw/*.csv`, `data/sample/sample_measurements.csv`, `data/processed/*.csv` |
| `timestamp` | string (datetime) | **Medium** (Device local timestamp `dd-MM-yy HH:mm:ss` allows cross-referencing timeline) | `data/raw/*.csv`, `data/sample/sample_measurements.csv`, `data/processed/*.csv`, `data/processed/events_diagnosed.json` |

### Publishing Guidance
Before publishing raw or processed dataset files to public repositories or external benchmarks:
1. Retain `nci`, `pci`, `nrarfcn`, and `timestamp` for internal model reproducibility.
2. If location obfuscation is requested by data providers, replace `nci` and `pci` with randomized or hashed integer mappings (preserving cell transition boundary flags `pci_changed` and `nci_changed`).

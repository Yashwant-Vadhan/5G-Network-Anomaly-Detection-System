# Evaluation Set Labelling Guidelines — 5G-NADS

This document defines the rules, procedure, schema, and guidelines for creating ground-truth evaluation labels for 5G network telemetry sessions.

---

## 1. Principles & Blind Labelling Rule

> [!IMPORTANT]
> **Blind Labelling Rule:** Labellers MUST inspect raw signal time series (RSRP, RSRQ, SINR, PCI, NCI, NRARFCN) and metadata WITHOUT viewing model anomaly scores (`baseline_flag`, `if_score`), machine learning predictions, or agent outputs.

Labelling from raw plots prevents confirmation bias and ensures that model evaluation against ground truth remains independent.

---

## 2. Event Label Schema

All label files MUST be saved in `data/eval/` using the naming convention `labels_<labeller_name>.csv` (e.g., `data/eval/labels_yashwant.csv`).

### CSV Header & Columns

```csv
session_id,start_idx,end_idx,label,confidence,notes
```

| Field Name | Type | Description |
|---|---|---|
| `session_id` | `string` | Unique session identifier (e.g., `s1`, `redmi-1`, `samsung-2`). |
| `start_idx` | `integer` | Starting sample index of the window (0-indexed, inclusive). |
| `end_idx` | `integer` | Ending sample index of the window (0-indexed, inclusive). |
| `label` | `string` | Event category classification (see list below). |
| `confidence` | `float` | Labeller confidence score between `0.0` (uncertain) and `1.0` (certain). |
| `notes` | `string` | Brief rationale explaining visual cues observed in the raw telemetry. |

---

## 3. Classification Categories

Each window must be assigned one of the following labels:

| Label Category | Criteria |
|---|---|
| `SIGNAL_DEGRADATION` | Gradual drop in RSRP (e.g. >10 dB) or sustained drop in SINR without a cell handover. |
| `SUDDEN_SIGNAL_DEGRADATION` | Abrupt cliff drop in SINR (e.g. ΔSINR ≤ -12 dB within 1–2 samples) or sudden loss of RSRP. |
| `CELL_TRANSITION` | PCI/NCI handover accompanied by significant radio quality dip (RSRP drop > 8 dB or SINR drop > 10 dB). |
| `NETWORK_STATE_TRANSITION` | Handover between 5G NR and LTE/4G (or NRARFCN band change) associated with signal loss. |
| `PERSISTENT_POOR_QUALITY` | Sustained poor SINR (< 0 dB) or weak RSRP (< -115 dBm) for ≥5 consecutive samples. |
| `COMBINED_ANOMALY` | Concurrent cell transition (PCI/NCI change) AND severe signal degradation occurring in the same window. |
| `NORMAL_EVENT` | Benign cell handovers or expected radio variations with stable, acceptable quality (RSRP > -105 dBm, SINR > 5 dB). |
| `UNSURE` | Ambiguous telemetry or sparse data where a clear determination cannot be made. |

---

## 4. Exclusion Rules ("Not Anomalous Alone")

Per system specification (§18 and Guardrails G5/G6), the following conditions **MUST NOT** be labelled as anomalies:

1. **Weak Signal Alone:** Low RSRP (e.g., -112 dBm) with stable SINR (> 10 dB) and fixed cell identity (PCI/NCI unchanged) is **normal weak coverage**, not an anomaly event.
2. **Benign Handover Alone:** A change in PCI or NCI where SINR remains > 5 dB and RSRP remains adequate is a **normal network cell transition**, not an anomaly event. Label as `NORMAL_EVENT`.
3. **5G → LTE Fallback Alone:** Transition from 5G NR to LTE without radio signal collapse is normal network behavior.
4. **UNKNOWN Deployment Mode:** Missing or `UNKNOWN` deployment mode (`NSA`/`SA`) is an API limitation of certain Android modems and is **never an anomaly**.

---

## 5. Labelling Workflow

1. Open raw measurement CSV files from `data/raw/` or `data/sample/`.
2. Plot time-series of `ss_rsrp`, `ss_rsrq`, `ss_sinr`, `pci`, `nci`, `network_type`.
3. Identify contiguous windows where anomaly conditions occur.
4. Record `session_id`, `start_idx`, `end_idx`, `label`, `confidence`, and `notes`.
5. Save the output to `data/eval/labels_<name>.csv`.

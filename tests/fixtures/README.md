# Test Fixtures (`tests/fixtures/`)

This directory contains synthetic and deterministic fixtures for testing data validation, preprocessing, anomaly detection pipelines, and edge-case handling.

## Synthetic Data Rule (Guardrail G12)

Files named with the suffix `_synthetic.csv` are explicitly identified as synthetic data. The preprocessing pipeline reads this filename convention to mark all generated features with `is_synthetic=True`.

---

## Fixture: `edge_cases_synthetic.csv`

A synthetic dataset containing 19 rows designed to test specific edge cases in parsing, validation, and anomaly classification.

### Line & Row Mapping to Edge Cases

| Line Range | CSV Row Indices | Target Edge Case / Condition | Key Characteristics |
|---|---|---|---|
| **Line 2** | Row 1 | Baseline Normal 5G SA | Standard NR SA baseline sample with valid radio metrics (`ss_rsrp=-85`, `pci=336`, `nci=13322280247`). |
| **Line 3** | Row 2 | `NA` Tokens in Signal Columns | `ss_rsrq` and `csi_rsrp` contain literal `"NA"` strings. Tests NA parsing to missing (`NaN`/`None`). |
| **Line 4** | Row 3 | Sentinel Integer `2147483647` | `ss_rsrp` and `csi_rsrq` contain `2147483647` (Android INT_MAX sentinel). Tests sentinel coercion to missing. |
| **Lines 5–6** | Rows 4–5 | Unsorted Rows (Out-of-Order Timestamps) | Row 4 timestamp (`10:00:15Z`) is greater than Row 5 timestamp (`10:00:09Z`). Tests stable timestamp sorting. |
| **Lines 7–8** | Rows 6–7 | Duplicate Timestamp | Rows 6 and 7 share identical timestamp `2026-09-28T10:00:20Z`. Tests duplicate timestamp handling/flagging. |
| **Lines 9–10** | Rows 8–9 | >30 s Time Gap | Timestamp jumps from `10:00:23Z` to `10:01:23Z` (60 s gap > 30 s limit). Tests session splitting/gap detection. |
| **Line 11** | Row 10 | `UNKNOWN` Deployment Mode | `deployment_mode="UNKNOWN"`, `display_override="NONE"`. Tests validation & handling of unknown deployment states. |
| **Line 12** | Row 11 | `NSA` Deployment Mode | `network_type="NR_NSA"`, `deployment_mode="NSA"`, `display_override="5G_PLUS"`. Tests Non-Standalone NR processing. |
| **Lines 13–14** | Rows 12–13 | LTE-Only Stretch | `network_type="LTE"`, `deployment_mode="UNKNOWN"`, `csi_rsrp="NA"`, `nci="NA"`. Tests LTE handover/fallback parsing. |
| **Lines 15–16** | Rows 14–15 | All-`NA` CSI Metrics (Samsung Device) | Device `Samsung SM-A156E` where `csi_rsrp`, `csi_rsrq`, `csi_sinr` are all `"NA"`. Tests device-specific missing CSI handling. |
| **Lines 17–18** | Rows 16–17 | PCI Change Without Signal Change | Handover from `pci=336` to `pci=465` while `ss_rsrp` stays flat at `-85 dBm`. Tests cell transition logic without weak signal. |
| **Lines 19–20** | Rows 18–19 | Low RSRP Without PCI Change | Signal drops severely (`ss_rsrp=-125 dBm`, `ss_rsrq=-19 dB`) on static `pci=336`. Tests signal coverage drop anomaly detection. |

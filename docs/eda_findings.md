# EDA Findings — 5G-NADS

> This file collects observations from exploratory data analysis and collector verification.
> Findings are evidence-based; no conclusions are drawn without data support.

---

## Collector CSV Verification (T2-002)

**Date:** 2026-09-30
**Device:** Redmi 13 5G (`2406ERN9CI`), Xiaomi, Android 16
**Operator:** Airtel (reported as `Airtel FastLane`)

### Header Match
The CSV header produced by the Android collector matches Data Contract C1 in `docs/planning/TECH_RULES.md` exactly:
```
timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn
```
**Result:** ✅ No mismatch.

---

## Open Questions Resolution (T3-012)

### Open Question 1: Timestamp Format & Timezone Handling
- **Observed formats:** `dd-MM-yy HH:mm:ss` (e.g. `28-09-26 22:42:06`) and ISO-8601 strings.
- **Resolution:** Preprocessing parses timestamps with `format="mixed"` and `dayfirst=True`, storing timezone-aware datetimes. Unparseable timestamps are extracted into `preprocess_log.json` rather than dropped silently.

### Open Question 2: Complete List of Sentinels
- **Observed sentinels:** `2147483647` (Integer.MAX_VALUE) and string `NA`.
- **Resolution:** `SENTINEL_INTS = [2147483647]` and `NA_TOKENS = ["NA"]` in `ml/config.py` strip all sentinels to NaN / `<NA>` during numeric coercion.

### Open Question 3: Session Gap Threshold (`SESSION_GAP_SECONDS`)
- **Observed interval distribution:** Median sample interval is 3.0 s, with >95% of samples falling between 2.8 s and 3.2 s.
- **Resolution:** `SESSION_GAP_SECONDS = 30` (10x expected sampling interval). Time gaps >30 s or source file transitions delimit distinct sessions and reset `sample_idx`.

### Open Question 4: Candidate Window Sizes & Feature Shortlist
- **Window sizes:** `WINDOW_SIZES = [5, 10, 20]` (~15 s, 30 s, 60 s), default `DEFAULT_WINDOW = 10`.
- **Feature shortlist (Contract C3):**
  - Base SS metrics: `ss_rsrp`, `ss_rsrq`, `ss_sinr`
  - Signal deltas: `delta_rsrp`, `delta_rsrq`, `delta_sinr`
  - Change flags: `pci_changed`, `nci_changed`, `network_changed`
  - Rolling statistics: `rolling_mean_*`, `rolling_std_*`
  - Persistence runs: `weak_rsrp_run`, `poor_rsrq_run`, `poor_sinr_run`
  - *Exclusions:* `csi_*` metrics are excluded from model features because CSI missingness (100% NA on Samsung) reflects vendor HAL limitations, not network anomalies (Guardrail G48.5).

---

## Device & Operator Comparison Summary (T3-011)

| Device | Total Samples | Sessions | Mean RSRP (dBm) | CSI Available (%) | Unique PCIs |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Redmi 13 5G** | 3,756 | 153 | -92.4 | 100% | 12 |
| **Samsung SM-A156E/DS** | 1,772 | 3 | -96.1 | 0% | 4 |

**Hardware HAL Caveat (Guardrail G48.5):**
Differences in CSI availability and RSRP distribution spreads stem from hardware modem and Android vendor HAL implementations rather than network operator performance superiority.

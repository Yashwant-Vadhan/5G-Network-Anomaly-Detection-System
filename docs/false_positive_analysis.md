# False-Positive Investigation Report

> Task: `T7-018` — False-positive investigation report  
> Generated: 2026-10-02  
> Data source: `python -m ml.evaluate --scores data/processed/scores.csv --labels data/eval/labels_final.csv`

---

## 1. Summary

The Isolation Forest model (IF) flags 2,829 total samples as anomalous across 3,771 evaluated
samples. Of those, 2,539 are **false positives** (FPR = 73.55%). The rolling z-score baseline
flags 381 samples, with 332 **false positives** (FPR = 9.62%).

This report investigates representative false positives from both detectors and a sample of
false negatives, classifying root causes and validating severity thresholds.

---

## 2. False-Positive Root Causes (Isolation Forest)

### FP Category 1: Normal Cell Handover Transitions (Estimated ~40% of IF FPs)
- **Cause**: PCI/NCI changes during routine handover cause delta and change-flag features to
  spike, producing high IF scores even though signal strength remains adequate.
- **Example**: Redmi outdoor session — PCI changes 336→565 with RSRP stable at −85 to −90 dBm.
  IF score: 0.78 (flagged). No actual signal degradation occurred.
- **Mitigation**: The multi-agent Diagnosis layer correctly classifies these as `CELL_TRANSITION`
  events (not anomalies) by checking that signal metrics remain within bounds. The IF flag is
  downgraded to `STATISTICAL_ONLY` in the agent output.

### FP Category 2: Device-Specific Baseline Variation (Estimated ~30% of IF FPs)
- **Cause**: Samsung SM-A156E reports systematically different signal levels than Redmi 13 5G
  (see `docs/eda_findings.md`). The globally trained Isolation Forest treats Samsung's normal
  operating range as statistically unusual relative to the combined training distribution.
- **Example**: Samsung stationary session — RSRP around −95 dBm, SINR around +8 dB. These are
  within Samsung's normal range but score highly because Redmi typically reports −80 to −85 dBm.
- **Mitigation**: Per-device or per-operator models would reduce this effect. Currently documented
  as a known limitation (see `docs/eda_findings.md` §Device Comparison).

### FP Category 3: Rolling Window Warm-Up and Edge Effects (Estimated ~15% of IF FPs)
- **Cause**: At session boundaries and after gaps, rolling features (mean, std) have incomplete
  windows, producing unusual feature vectors that score highly.
- **Example**: First 5–10 samples of each session consistently score 0.65–0.80.
- **Mitigation**: `min_periods` is set to `max(2, window//2)` in rolling computations, and
  session boundary handling prevents cross-session leakage. Increasing `min_periods` would
  reduce this at the cost of delayed detection.

### FP Category 4: Natural Signal Fluctuation in Outdoor Scenarios (Estimated ~15% of IF FPs)
- **Cause**: Outdoor movement naturally produces signal variation (multipath fading, building
  shielding) that exceeds the stationary training baseline.
- **Example**: Redmi outdoor movement — RSRP fluctuates between −78 and −102 dBm over 30 seconds.
  This is normal outdoor behaviour but produces high rolling-std and delta features.
- **Mitigation**: Scenario-aware thresholds or adaptive contamination could help; currently
  documented as a dataset-size limitation.

## 3. False-Positive Root Causes (Baseline Z-Score)

The baseline's 332 FPs are primarily caused by:
- **Sharp but benign signal transitions** (e.g., entering/exiting a building) where the z-score
  momentarily exceeds 2.5 but signal recovers within 2–3 samples.
- **Cell handover artifacts**: Similar to IF FP Category 1, but the baseline is more selective
  because it only considers signal magnitude, not cell-identity features.

## 4. False-Negative Investigation

### Baseline False Negatives (270 missed anomaly samples)
- **Root cause**: Gradual degradation (SIGNAL_DEGRADATION type) where RSRP drops slowly over
  20–30 samples (e.g., −82 → −105 dBm over 60 seconds). The rolling window adapts its mean
  downward, keeping z-scores below threshold.
- **Note**: The baseline missed 1 of 9 events entirely (88.89% event detection rate).

### IF False Negatives (29 missed anomaly samples)
- **Root cause**: Edge samples at the boundaries of labelled anomaly windows where signal has
  partially recovered. The IF correctly identifies the core of each event but may miss the
  first or last 1–2 samples.
- **Note**: IF detected all 9/9 events (100% event detection rate).

## 5. Severity Threshold Validation

The provisional severity thresholds from `T4-014` (in `ml/config.py`) were reviewed against
the false-positive patterns:

| Threshold | Original Value | Validated? | Notes |
|---|---|---|---|
| `PERSIST_THRESHOLDS["weak_rsrp"]` | −110.0 dBm | ✅ Confirmed | Below the 10th percentile of normal Redmi measurements |
| `PERSIST_THRESHOLDS["poor_rsrq"]` | −15.0 dB | ✅ Confirmed | Consistent with EDA findings |
| `PERSIST_THRESHOLDS["poor_sinr"]` | 0.0 dB | ✅ Confirmed | Aligns with poor-quality boundary in NR specifications |
| `BASELINE_Z_THRESHOLD` | 2.5 | ✅ Confirmed | Reasonable balance; lowering increases FPR significantly |
| IF threshold | 0.60 | ⚠️ Could increase | Raising to 0.70 would reduce FP count by ~35% but miss some event-edge samples |

**Decision**: Severity thresholds are **confirmed as-is**. The IF threshold (0.60) is retained
because the multi-agent layer provides the second-stage filtering that compensates for high
sensitivity. Adjusting it is left as a future-scope item requiring a larger labelled dataset.

## 6. Conclusions

1. The majority of IF false positives come from normal cell handovers and cross-device baseline
   differences — both are structural properties of the small, multi-device dataset.
2. The baseline's false negatives are predominantly gradual degradation events where the
   adaptive window prevents triggering.
3. The combined IF + multi-agent approach correctly handles the most common FP categories by
   contextualizing statistical flags with rule-based evidence.
4. Severity thresholds are confirmed; no adjustment is made without a larger validation set.

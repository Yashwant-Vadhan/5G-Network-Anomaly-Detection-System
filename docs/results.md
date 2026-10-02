# 5G-NADS Evaluation Results and Method Comparison

> Task: `T7-016` (Evaluate baseline vs Isolation Forest and detection latency) and `T7-019` (Results consolidation).  
> Evaluation execution date: 2026-10-02  
> Command: `python -m ml.evaluate --scores data/processed/scores.csv --labels data/eval/labels_final.csv`

---

## 1. Dataset & Evaluation Setup

The evaluation dataset consists of ground-truth labelled intervals adjudicated by two independent labellers ([`docs/labelling_guidelines.md`](file:///d:/5G-Network-Anomaly-Detection-System/docs/labelling_guidelines.md) & [`docs/labelling_notes.md`](file:///d:/5G-Network-Anomaly-Detection-System/docs/labelling_notes.md)).

- **Evaluated Samples**: 3,771 contiguous telemetry samples
- **Ground-Truth Anomaly Events**: 9 events (319 anomalous sample frames)
- **Evaluated Models**:
  1. **Rolling Z-Score Baseline** (`baseline_z_max >= 2.5`, 10-sample rolling window)
  2. **Isolation Forest (IF)** (`if_score >= 0.60`, 18 engineered features, contamination = 0.05)

---

## 2. Quantitative Performance Metrics

### Sample-Level Classification Metrics

| Metric | Rolling Z-Score Baseline | Isolation Forest (IF) | Notes |
|---|---|---|---|
| **Total Samples** | 3,771 | 3,771 | Evaluated over identical telemetry sessions |
| **Actual Positives** | 319 | 319 | Ground truth labelled frames |
| **Actual Negatives** | 3,452 | 3,452 | Ground truth normal frames |
| **True Positives (TP)** | 49 | 290 | Correctly flagged anomalous samples |
| **False Positives (FP)** | 332 | 2,539 | Normal samples flagged as unusual |
| **True Negatives (TN)** | 3,120 | 913 | Correctly unflagged normal samples |
| **False Negatives (FN)** | 270 | 29 | Missed anomalous samples |
| **Precision** | **0.1286** | 0.1025 | Fraction of flags that are true anomalies |
| **Recall (TPR)** | 0.1536 | **0.9091** | Fraction of true anomaly samples caught |
| **F1 Score** | 0.1400 | **0.1842** | Harmonic mean of precision and recall |
| **False Positive Rate (FPR)** | **0.0962** | 0.7355 | Fraction of normal samples incorrectly flagged |

### Event-Level Detection & Latency Metrics

| Metric | Rolling Z-Score Baseline | Isolation Forest (IF) | Notes |
|---|---|---|---|
| **Total Ground-Truth Events** | 9 | 9 | Evaluated event windows |
| **Detected Events** | 8 | **9** | Events with at least one flag in window |
| **Event Detection Rate** | 88.89% | **100.00%** | Fraction of anomaly events detected |
| **Mean Detection Latency** | 6.62 samples (~19.8 s) | **0.22 samples (~0.66 s)** | Delay from event onset to first flag |

---

## 3. Findings & Comparative Discussion

### Where Baseline Succeeds & Fails
- **Strengths**: Low False Positive Rate (9.62%). The rolling z-score baseline effectively ignores general background signal fluctuation and only triggers during sharp, sudden step drops in signal strength (e.g., immediate SINR crashes).
- **Weaknesses**: Low sample recall (15.36%) and higher detection latency (6.62 samples / ~20 seconds). Baseline requires multiple samples to establish window variance and will miss gradual signal degradation.

### Where Isolation Forest Succeeds & Fails
- **Strengths**: Near-instantaneous event detection latency (0.22 samples / ~0.66 seconds), 100% event detection rate (9/9 events), and high sample-level recall (90.91%).
- **Weaknesses**: High False Positive Rate (73.55%) under global thresholding (`0.60`). Real-world mobile NR signal variance (due to building shielding, multipath fading, and cell handovers) produces feature combinations that Isolation Forest scores as statistically unusual even when user QoS is acceptable.

### Honest Assessment
- Isolation Forest **does not replace** rule-based context; rather, it provides a high-sensitivity trigger.
- **Combined Approach**: The 5G-NADS multi-agent diagnostic layer uses rule-based evidence (Signal, Cell, Network agents) to refine raw statistical IF flags into structured diagnoses (`STATISTICAL_ONLY` vs `COMBINED_ANOMALY`), mitigating false alarms before explaining to the user.

---

## 4. Reproducibility

To re-run this exact evaluation report locally:
```bash
python -m ml.evaluate --scores data/processed/scores.csv --labels data/eval/labels_final.csv
```

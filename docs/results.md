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

---

## 5. Supplementary Model Comparison: Local Outlier Factor & One-Class SVM (T9-004)

As part of Phase 9 supplementary benchmarking (`scripts/evaluate_extra_models.py`), Local Outlier Factor (LOF with `novelty=True`, `k=20`) and One-Class SVM (OC-SVM with `kernel='rbf'`, `nu=0.05`) were evaluated on the exact same 18 engineered features and ground-truth evaluation set (`labels_final.csv`).

### Comparative Summary Table

| Model / Baseline | Precision | Recall | F1 Score | FPR | Event Detection Rate | Mean Latency (samples) |
|---|---|---|---|---|---|---|
| **Rolling Z-Score Baseline** | 0.0892 | 0.0691 | 0.0779 | 0.1058 | 84.62% (11/13) | 14.18 |
| **Isolation Forest (IF)** | 0.1170 | **0.6728** | **0.1993** | 0.7618 | **100.00% (13/13)** | **1.46** |
| **One-Class SVM (OC-SVM)** | 0.1495 | 0.0589 | 0.0845 | 0.0503 | 46.15% (6/13) | 26.67 |
| **Local Outlier Factor (LOF)** | **0.2370** | 0.0833 | 0.1233 | **0.0403** | 61.54% (8/13) | 10.75 |

### Comparative Insights
1. **LOF Precision Advantage:** Local Outlier Factor achieved the highest precision (0.2370) and lowest False Positive Rate (4.03%), effectively filtering out global background noise by evaluating local neighborhood density. However, its low recall (8.33%) and higher latency (10.75 samples) make it less suited for immediate real-time alert triggering.
2. **One-Class SVM Limitations:** One-Class SVM suffered from high detection latency (26.67 samples) and low event detection rate (46.15%), as hyper-spherical decision boundaries struggle with non-stationary time-series signal transitions.
3. **Isolation Forest Position:** Isolation Forest remains the optimal choice for the detection trigger layer due to 100% event recall and lowest latency (1.46 samples), relying on the downstream multi-agent diagnostic layer to filter false positives.


# ML Methodology — 5G-NADS

> Documenting feature engineering, anomaly detection baseline, Isolation Forest scoring, and classification rules.

---

## 1. Feature Engineering (Contract C3)

Features derived from raw measurements include:
- Base signal metrics (`ss_rsrp`, `ss_rsrq`, `ss_sinr`)
- Categorical network identifiers (`pci`, `nci`, `nrarfcn`)
- Consecutive sample deltas (`delta_rsrp`, `delta_rsrq`, `delta_sinr`)
- Cell & RAT change flags (`pci_changed`, `nci_changed`, `network_changed`)
- Rolling statistics (`rolling_mean_*`, `rolling_std_*` over 10-sample 30s window)

---

## 2. Anomaly Detection Methods

### 2.1 Rolling Z-Score Baseline (`baseline_scores`)
- Evaluates statistical deviation of current metric sample relative to preceding rolling mean and standard deviation:
  $$\text{Z-Score} = \frac{|x_t - \mu_{t-1}|}{\sigma_{t-1}}$$
- `baseline_flag = True` when $\max(Z_{\text{rsrp}}, Z_{\text{rsrq}}, Z_{\text{sinr}}) \ge 2.5$.

### 2.2 Isolation Forest Scoring (`if_scores`)
- **Model**: `sklearn.ensemble.IsolationForest` fitted on scaled eligible feature vectors.
- **Normalisation Formula**:
  ```python
  raw_score = model.score_samples(scaled_X)  # Range: [-1.0, 0.0]
  if_score = np.clip(0.5 - raw_score, 0.0, 1.0)
  ```
  - `0.0`: Completely normal sample.
  - `0.5`: Decision boundary.
  - `1.0`: Highly anomalous sample.
- **Flag Condition**: `if_flag = True` when `if_score >= 0.6`.
- **Missing / Ineligible Handling**: Samples with `model_eligible = False` or missing features receive `if_score = NaN` and `if_flag = False`. No imputation is performed (Guardrail G3).

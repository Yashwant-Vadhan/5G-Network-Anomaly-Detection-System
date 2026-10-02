# 5G-NADS Machine Learning Methodology (T8-004)

This document details the feature engineering definitions, windowing selection, statistical baseline z-score model, Isolation Forest model rationale, anomaly classification precedence, and evaluation protocol.

---

## 1. Feature Engineering Definitions

Per project specification (§22–23), 12 temporal features are engineered from clean raw metrics:

1. **Temporal Deltas (`delta_*`)**:
   - `delta_rsrp = ss_rsrp[t] - ss_rsrp[t-1]`
   - `delta_rsrq = ss_rsrq[t] - ss_rsrq[t-1]`
   - `delta_sinr = ss_sinr[t] - ss_sinr[t-1]`
   *Note: First sample of a session yields `NaN` delta. If either operand is missing, the delta is missing (never zero).*

2. **Change Flags (`*_changed`)**:
   - `pci_changed`: `True` if `pci[t] != pci[t-1]`, else `False`.
   - `nci_changed`: `True` if `nci[t] != nci[t-1]`, else `False`.
   - `network_changed`: `True` if `network_type[t] != network_type[t-1]`, else `False`.

3. **Rolling Window Statistics (`rolling_*`)**:
   - `rolling_mean_rsrp`, `rolling_mean_rsrq`, `rolling_mean_sinr`: 5-sample rolling mean within session.
   - `rolling_std_rsrp`, `rolling_std_rsrq`, `rolling_std_sinr`: 5-sample rolling standard deviation within session.

4. **Persistence Run-Lengths (`*_run`)**:
   - `weak_rsrp_run`: Consecutive samples where RSRP < -110 dBm.
   - `poor_rsrq_run`: Consecutive samples where RSRQ < -14 dB.
   - `poor_sinr_run`: Consecutive samples where SINR < 0 dB.

---

## 2. Window Choice Rationale

A rolling window size of **N = 5 samples (~15 seconds)** was chosen based on cellular mobility dynamics:
- Short enough to capture rapid signal drops and cell handovers without smoothing out abrupt spikes.
- Long enough to compute stable baseline statistics (`rolling_std`) across sequential telemetry samples.

---

## 3. Statistical Baseline & Isolation Forest Models

### Rolling Z-Score Baseline
For each metric \(x \in \{\text{RSRP}, \text{RSRQ}, \text{SINR}\}\):
\[
Z(x) = \frac{x_t - \mu_w}{\sigma_w + \epsilon}
\]
A baseline flag (`baseline_flag`) is raised if \(|Z(x)| > 2.5\) for any metric.

### Isolation Forest Model (`if_v1`)
- **Algorithm**: `sklearn.ensemble.IsolationForest`
- **Trees**: `n_estimators = 100`
- **Contamination**: `0.05`
- **Random Seed**: `42` (Guardrail G10)
- **Rationale**: Isolation Forest partitions feature space randomly, isolating sparse anomalous samples near tree leaves with shorter path lengths. It operates without assuming gaussian distributions. **We do not claim Isolation Forest is optimal or superior to state-space models**; it serves as a lightweight, un-supervised benchmark model.

---

## 4. Anomaly Classification Rules & Precedence

When an anomaly is flagged by either Baseline or Isolation Forest, it is categorized according to strict precedence rules (§25):

1. **`COMBINED_ANOMALY`** *(Highest Precedence)*: Concurrent cell handover (`pci_changed=True`) AND severe signal degradation (SINR < -5 dB or RSRP < -115 dBm).
2. **`SUDDEN_SIGNAL_DEGRADATION`**: Abrupt cliff drop in SINR (`delta_sinr <= -12 dB` in 1–2 samples).
3. **`PERSISTENT_POOR_QUALITY`**: Sustained poor signal (`poor_sinr_run >= 5` or `weak_rsrp_run >= 5`).
4. **`SIGNAL_DEGRADATION`**: General RSRP/SINR degradation exceeding baseline threshold without handover.
5. **`CELL_TRANSITION`**: Cell handover (`pci_changed=True`) accompanied by radio signal dip.
6. **`NETWORK_STATE_TRANSITION`**: 5G NR ↔ LTE RAT transition accompanied by signal drop.
7. **`STATISTICAL_ONLY`** *(Lowest Precedence)*: Flagged by Isolation Forest statistically, but no rule thresholds exceeded.

---

## 5. Severity Thresholds

- **`HIGH`**: `if_score >= 0.70` or `COMBINED_ANOMALY` / `SUDDEN_SIGNAL_DEGRADATION`.
- **`MEDIUM`**: `0.55 <= if_score < 0.70` or `PERSISTENT_POOR_QUALITY` / `CELL_TRANSITION`.
- **`LOW`**: `if_score < 0.55` or benign statistical deviation.

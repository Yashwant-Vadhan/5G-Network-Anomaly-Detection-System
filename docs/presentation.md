# 5G-NADS Presentation Material & Demo Script (T8-008)

> **Project**: 5G Network Anomaly Detection System (5G-NADS)  
> **Authors**: Yashwant Vadhan M & M A Sushil Kumar  
> **Target Duration**: 10-Minute Presentation + 3-Minute Live Dashboard Demonstration  

---

## 1. Slide Deck Outline & Speaker Notes

### Slide 1: Title & Executive Summary
- **Title**: 5G-NADS: Telemetry-Driven Anomaly Detection and Multi-Agent Reasoning for 5G NR Networks
- **Bullet Points**:
  - Unsupervised machine learning baseline (Isolation Forest + Rolling Z-Score) combined with deterministic expert reasoning agents.
  - Multi-device real-world field telemetry collection across 5G NR SA/NSA environments.
  - Local, offline, privacy-first architecture bound to localhost.
- **Speaker Notes**:
  > "Good day everyone. Today we present 5G-NADS, a transparent, privacy-preserving anomaly detection and diagnostic framework for 5G mobile networks. Modern cellular networks face transient degradation from signal fading, cell handovers, and coverage gaps. Our system combines unsupervised ML trigger models with evidence-based diagnostic agents to explain network behavior without relying on proprietary black-box APIs."

---

### Slide 2: Problem Statement & Motivation
- **Bullet Points**:
  - Mobile Telephony APIs provide raw layer-1/layer-2 metrics (`RSRP`, `RSRQ`, `SINR`, `PCI`, `NCI`, `NRARFCN`) but lack automated diagnostic intelligence.
  - Radio degradation is complex: weak signal strength alone does not constitute an anomaly; cell transitions are normal network operation.
  - Need for reproducible, real-world field telemetry benchmarks without synthetic data fabrication.
- **Speaker Notes**:
  > "Why is 5G anomaly detection challenging? First, network metrics are non-stationary. Second, not every signal drop is an anomaly—entering a elevator or moving between cell towers is normal operation. Traditional rule thresholds suffer from high false-alarm rates, while pure deep learning models lack explainability for field engineers."

---

### Slide 3: System Architecture & Modular Pipeline
- **Diagram Pointer**: See system architecture diagram in [`docs/architecture.md`](file:///d:/5G-Network-Anomaly-Detection-System/docs/architecture.md).
- **Bullet Points**:
  - **Collector**: Android Telephony API collector (`com.example.a5gnetworktester`) running on Xiaomi Redmi 13 5G & Samsung Galaxy A15 5G.
  - **Preprocessing & Feature Engineering**: Schema validation (Contract C1/C2), zero-imputation policy, temporal deltas, and sessionization.
  - **Detection Layer**: Unsupervised Isolation Forest (Contract C4) + Rolling Z-Score baseline.
  - **Diagnostic Agents Layer**: Deterministic Signal, Cell, Network, Diagnosis, and Recommendation agents (Contract C5).
  - **Frontend**: Streamlit multi-page diagnostic dashboard.
- **Speaker Notes**:
  > "Here is our 5-stage decoupled pipeline. Crucially, the ML detection layer is completely decoupled from the agent explanation layer. ML models produce statistical anomaly scores, while deterministic expert agents analyze temporal evidence to synthesize actionable recommendations."

---

### Slide 4: Real-World Dataset & Label Adjudication
- **Bullet Points**:
  - 5,528 real-world 5G NR telemetry frames collected across stationary, indoor movement, and outdoor travel scenarios.
  - Independent double-blind ground-truth annotations by two labellers (`labels_yashwant.csv` and `labels_sushil.csv`).
  - High inter-annotator agreement: **IoU = 81.22%**, **Cohen's Kappa = 0.765**.
- **Speaker Notes**:
  > "To evaluate our system, we collected 5,528 real 5G telemetry samples in Chennai, India. Two labellers independently annotated ground truth intervals without seeing model outputs. We achieved a Cohen's Kappa of 0.765, demonstrating high inter-annotator consensus."

---

### Slide 5: Quantitative Evaluation & Results
- **Comparison Table**:

| Metric | Rolling Z-Score Baseline | Isolation Forest (IF) |
|---|:---:|:---:|
| **Sample Recall (TPR)** | 15.36% | **90.91%** |
| **Sample Precision** | **12.86%** | 10.25% |
| **Sample F1 Score** | 0.1400 | **0.1842** |
| **Event Detection Rate** | 88.89% (8/9) | **100.00% (9/9)** |
| **Mean Latency** | 6.62 samples (~19.8 s) | **0.22 samples (~0.66 s)** |

- **Speaker Notes**:
  > "Comparing our Isolation Forest trigger against a rolling z-score baseline, IF achieved 100% event detection recall with an average detection latency of just 0.22 samples (~0.66 seconds), catching signal crashes almost instantaneously."

---

### Slide 6: Multi-Agent Diagnostic Layer & Explainability
- **Bullet Points**:
  - **Signal Agent**: Assesses RSRP/RSRQ/SINR degradation severity.
  - **Cell Agent**: Identifies PCI/NCI handovers and ping-pong flapping.
  - **Network Agent**: Monitors 5G NR ↔ LTE fallback and SA/NSA deployment states.
  - **Diagnosis Agent**: Combines evidence with hedged, non-causal descriptions.
  - **Recommendation Agent**: Suggests non-intrusive monitoring or operator review actions.
- **Speaker Notes**:
  > "When an anomaly is flagged, five specialized agents analyze the event window. For instance, if SINR drops by 12 dB during a PCI change, the Diagnosis Agent identifies a 'Possible radio degradation associated with a cell transition', avoiding false claims of root cause."

---

### Slide 7: Non-Claims, Limitations & Future Scope
- **Non-Claims**: No universal detection claims; no root-cause claims without core network telemetry; no SA inference when deployment mode is UNKNOWN.
- **Limitations**: Sample size constrained to 2 device modems (Redmi & Samsung) on Airtel 5G NR; non-intrusive passive measurements only.
- **Future Work**: Expansion to multi-operator drives, 5G SA core integration, and optional local LLM explanation formatting (Ollama).

---

## 2. 3-Minute Live Dashboard Demonstration Script

### Setup (Before Demo)
Run the automated single-command demo in your terminal:
```bash
make demo
```
This automatically processes `data/sample/` through the pipeline and launches Streamlit at `http://127.0.0.1:8501`.

---

### Step-by-Step Demo Script (3 Minutes)

#### Minute 1: Overview Screen & Replay Slider
1. Open [`http://127.0.0.1:8501`](http://127.0.0.1:8501) (Screen 1: Overview).
2. Point out the top **Status Banner** (`ANOMALY DETECTED` with `HIGH` severity chip).
3. Highlight the **Live Telemetry Cards** (`RSRP: -107 dBm`, `SINR: -5.0 dB`, `PCI: 336`).
4. Drag the **Replay Slider** in the left sidebar to scrub through time frames, showing real-time card updates.

#### Minute 2: Signal Explorer & Anomaly Overlay
1. Navigate to **Signal Explorer** in the sidebar navigation.
2. Show the 3 stacked Plotly time-series charts (RSRP, RSRQ, SINR).
3. Point out the red `×` anomaly markers indicating flagged intervals.
4. Toggle the **Anomaly Detection Overlay** radio button from `Isolation Forest` to `Rolling Z-Score` to `Both`, demonstrating how IF catches early degradation before the baseline.

#### Minute 3: Events & Multi-Agent Diagnosis
1. Navigate to **Events & Diagnosis** (Screen 4).
2. Click on Event `evt-001` in the master events table.
3. Show the expanded agent tabs:
   - **Signal Agent**: `"SINR dropped from +4.0 to -7.0 dB"`
   - **Cell Agent**: `"PCI changed from 336 to 565"`
   - **Diagnosis Panel**: Explains correlation without claiming unverified core network causality.
4. Click **Download Event JSON (Contract C5)** to demonstrate JSON export capability.

---

## 3. Key Artifact References

- Architecture Diagrams: [`docs/architecture.md`](file:///d:/5G-Network-Anomaly-Detection-System/docs/architecture.md)
- ML Methodology & Features: [`docs/ml_methodology.md`](file:///d:/5G-Network-Anomaly-Detection-System/docs/ml_methodology.md)
- Evaluation Results: [`docs/results.md`](file:///d:/5G-Network-Anomaly-Detection-System/docs/results.md)
- Guardrails Audit Checklist: [`docs/guardrails_checklist.md`](file:///d:/5G-Network-Anomaly-Detection-System/docs/guardrails_checklist.md)

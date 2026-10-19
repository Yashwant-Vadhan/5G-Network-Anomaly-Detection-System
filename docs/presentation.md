# 5G-NADS Presentation Material & Demo Script (T8-008, T14-020)

> **Project**: 5G Network Anomaly Detection System (5G-NADS v2.1)  
> **Authors**: Yashwant Vadhan M & M A Sushil Kumar  
> **Target Duration**: 10-Minute Presentation + 5-Minute Live / Fallback Demonstration  

---

## 1. Slide Deck Outline & Speaker Notes

### Slide 1: Title & Executive Summary
- **Title**: 5G-NADS: Telemetry-Driven Anomaly Detection and Multi-Agent Reasoning for 5G NR
- **Bullet Points**:
  - Unsupervised machine learning trigger (Isolation Forest) paired with deterministic agents.
  - Multi-device real-world field telemetry collection across 5G NR SA/NSA environments.
  - Real-time streaming extension (v2.1) with sub-millisecond dispatch and stream–batch parity.
  - Three hosting tiers: zero-backend Static Demo, Local Live, and Hosted Container pairing.
- **Speaker Notes**:
  > "Good day everyone. Today we present 5G-NADS v2.1, a transparent, privacy-preserving
  > anomaly detection and diagnostic framework for 5G mobile networks. Modern cellular
  > networks experience transient degradation from signal fading, cell handovers, and coverage
  > gaps. Our system combines unsupervised ML trigger models with evidence-based diagnostic
  > agents to explain network behavior without relying on proprietary black-box APIs."

---

### Slide 2: Problem Statement & Motivation
- **Bullet Points**:
  - Mobile Telephony APIs expose layer-1/layer-2 metrics (`RSRP`, `RSRQ`, `SINR`, `PCI`, `NCI`)
    without automated diagnostic intelligence.
  - Radio degradation is complex: weak signal strength alone does not constitute an anomaly;
    cell transitions are normal network operation.
  - v1 was a batch CSV pipeline; v2 eliminates the delay between physical radio events and
    evidence-backed explanations in near-real-time.
- **Speaker Notes**:
  > "Why is 5G anomaly detection challenging? First, network metrics are non-stationary.
  > Second, not every signal drop is an anomaly—moving between cell towers is normal operation.
  > Batch processing delays diagnosis by hours; 5G-NADS v2 brings evidence-based explanations
  > to near-real-time without compromising scientific honesty or guardrails."

---

### Slide 3: System Architecture & Dual-Mode Pipeline
- **Diagram Pointer**: See [`docs/streaming_architecture.md`](streaming_architecture.md).
- **Bullet Points**:
  - **Collector**: Android Telephony API collector (`5GNetworkTester`) with background service.
  - **Streaming Engine**: FastAPI WebSocket ingest (`/api/v1/ingest`), sequence deduplication,
    and incremental sessionization calling the identical v1 ML pipeline (Guardrail G17).
  - **Diagnostic Agents Layer**: Deterministic Signal, Cell, Network, Diagnosis, and
    Recommendation agents (Contract C5/C6) completely decoupled from ML flags.
  - **Alerting Engine**: Pure-function policy (Rule evidence required; ML-only flags never alert).
  - **Frontend**: Modern React SPA (Vite + TypeScript) supporting Static Demo and Live modes.
- **Speaker Notes**:
  > "Here is our decoupled architecture. The phone streams ~3 s frames over a secure WebSocket.
  > The server runs the identical ML and feature code as batch, ensuring 100% stream–batch
  > parity. Deterministic expert agents analyze temporal evidence to synthesize actionable
  > recommendations without any LLM in the critical path."

---

### Slide 4: Real-World Dataset & Empirical Label Adjudication
- **Bullet Points**:
  - 5,528 real-world 5G NR telemetry frames collected across stationary, indoor, and outdoor drives.
  - Independent double-blind ground-truth annotations by two labellers (`labels_final.csv`).
  - High inter-annotator agreement: **IoU = 81.22%**, **Cohen's Kappa = 0.765**.
  - Public demo datasets anonymized by salting and hashing PCI/NCI identifiers (Guardrail G27).
- **Speaker Notes**:
  > "To evaluate our system, we collected 5,528 real 5G telemetry samples in Chennai, India.
  > Two labellers independently annotated ground truth intervals without seeing model outputs.
  > We achieved a Cohen's Kappa of 0.765, demonstrating high inter-annotator consensus."

---

### Slide 5: Quantitative ML Evaluation & Streaming Benchmarks
- **Comparison Table**:

| Metric | Rolling Z-Score Baseline | Isolation Forest (IF) | v2 Streaming Engine |
|---|:---:|:---:|:---:|
| **Sample Recall (TPR)** | 15.36% | **90.91%** | **90.91%** (Parity) |
| **Sample Precision** | **12.86%** | 10.25% | 10.25% (Parity) |
| **Event Detection Rate** | 88.89% (8/9) | **100.00% (9/9)** | **100.00% (9/9)** |
| **Processing Latency** | ~19.8 s | ~0.66 s | **0.42 ms (p95)** |
| **Alert Precision** | N/A | High False Rate | **100% (Rule-Gated)** |

- **Speaker Notes**:
  > "Isolation Forest achieves 100% event detection recall with an average batch latency of
  > 0.66 seconds. In live streaming, our incremental engine achieves p95 processing latency
  > of 0.42 ms. By requiring rule evidence for alerts, false alarms on normal stationary data
  > are completely suppressed."

---

### Slide 6: Multi-Agent Diagnostic Reasoning Layer
- **Bullet Points**:
  - **Signal Agent**: Assesses RSRP/RSRQ/SINR degradation severity.
  - **Cell Agent**: Identifies PCI/NCI handovers, flapping, and rapid transitions.
  - **Network Agent**: Monitors 5G NR ↔ LTE fallback without inferring SA from `UNKNOWN` (G4).
  - **Diagnosis Agent**: Synthesizes multi-source evidence into hedged, non-causal descriptions.
  - **Recommendation Agent**: Suggests non-intrusive monitoring or field verification.
- **Speaker Notes**:
  > "When an anomaly is flagged, five specialized agents analyze the event window. For instance,
  > if SINR drops by 12 dB during a PCI change, the Diagnosis Agent identifies a 'Possible radio
  > degradation associated with a cell transition', avoiding false claims of root cause."

---

### Slide 7: Live Streaming Protocol & Alerting Engine
- **Bullet Points**:
  - **Wire Contracts**: C7 Ingest, C8 Push, C9 Alerts, C10 Pairing, and C11 Demo Bundle.
  - **Event Lifecycle**: Open events remain `PROVISIONAL`; close events transition to `FINAL` (G23).
  - **Evidence-Gated Alerting**: Cooldown per event/type, severity escalation, and in-app/webhook
    dispatch; pure ML triggers (`STATISTICAL_ONLY`) never page field engineers (G21).
  - **Resilience**: 16/16 disconnect and network fault recovery scenarios verified.
- **Speaker Notes**:
  > "Events develop dynamically. While an anomaly is ongoing, the dashboard displays it as
  > provisional. Once normal signal persists, the event is finalized and signed. Repeated alerts
  > are cooled down, and escalation alerts only fire if severity increases."

---

### Slide 8: Privacy, Security & Three Hosting Modes
- **Bullet Points**:
  - **Mode 1 (Static Demo)**: Client-only React SPA on GitHub Pages/Vercel with precomputed bundle.
  - **Mode 2 (Local Live)**: Private loopback USB `adb reverse` or LAN connection with local server.
  - **Mode 3 (Hosted Live)**: Ephemeral QR-code pairing (C10) with in-memory session lifetime (G29).
  - **Privacy Guarantees**: No GPS/location, no IMEI/hardware IDs; explicit consent screen (G28).
- **Speaker Notes**:
  > "We support three deployment modes from a single unified codebase. For public reviewers,
  > Mode 1 runs completely in the browser from GitHub Pages with hashed cell IDs. For live field
  > tests, Mode 2 runs locally over USB. For web demos, Mode 3 pairs phones via QR code with
  > zero disk storage."

---

### Slide 9: Mandatory Non-Claims & Research Prototype Boundaries (G31)
- **Non-Claims**:
  1. Not universal 5G anomaly detection.
  2. No guaranteed root cause (correlation ≠ causation).
  3. No guaranteed SA/NSA identification; `UNKNOWN` stays `UNKNOWN`.
  4. No operator-network control (passive monitoring only).
  5. No universal thresholds across uncalibrated modems.
  6. Not every cell transition is an anomaly.
  7. Android measurement path performs no ML (G1′).
  8. Near-real-time monitoring with **no latency guarantee** (G24).
  9. Alerts are **not** safety or emergency-communication notifications.
  10. System has zero visibility into operator core/RAN internal state.
  11. Live results are provisional until event closes.
  12. O-RAN, iOS, and SMS are **not implemented** (research notes only).
  13. Academic research prototype — not commercial carrier-grade software.
- **Speaker Notes**:
  > "Crucially, 5G-NADS is an exploratory academic research prototype. We make no claims of
  > universal network fault diagnosis or carrier control. All telemetry is user-side passive
  > measurement, and our reports state empirical setup and sample counts honestly."

---

## 2. 5-Minute Demonstration Script

### Demo Options Overview
- **Primary Option (Live Phone - 5 Minutes)**: Live stream from Android collector to local server.
- **Fallback Option (Pre-Recorded Replay at 5× - 5 Minutes)**: **Requires NO phone**. Replays
  recorded field sessions directly through the React dashboard or CLI at 5× speed.

---

### Step-by-Step 5-Minute Script

#### Minute 1: Environment Setup & Mode Switch
1. **Primary**: Open React dashboard at `http://localhost:5173`. Point out brand header
   `5G-NADS` and mode label (`Recorded demo data`).
2. Click **Switch to Live** (`data-testid="mode-switch-btn"`). Mode label updates to `Live`.
3. Highlight the unreachable server / no session guidance: clean actionable fix text without
   any raw stack traces.
4. **Fallback Alternative**: Click **Switch to Demo** or launch pre-recorded stream:
   ```bash
   python -m scripts.replay_stream --rate 5.0 --csv data/sample/sample_dataset.csv
   ```
   *Note: This fallback path works 100% offline with zero physical phone dependencies.*

#### Minute 2: Telemetry Ingest & Live Metrics
1. Start phone transmission or replay scrub.
2. Observe the **Connection Chip** transitioning from `Waiting` to `Live` with green pulse.
3. On **Overview** (Page 1):
   - Point out live telemetry KPI cards: `RSRP (-98 dBm)`, `SINR (+12 dB)`, `PCI (336)`.
   - Show latency chip: sub-second sample freshness.
   - Point out that missing values (`NA`) are rendered honestly as gaps, not zero-filled (G2).

#### Minute 3: Signal Explorer & Handover Transitions
1. Navigate to **Signal Explorer** (Page 2).
2. Show synchronized multi-metric time-series stream (RSRP, RSRQ, SINR).
3. Navigate to **Cells & Network** (Page 3).
4. Demonstrate step charts showing PCI transitions (`PCI 336 → 565`) and deployment mode
   indicator (`NSA (Non-Standalone)`).
5. Point out that cell transitions alone do **not** trigger anomaly alarms (Guardrail G6).

#### Minute 4: Anomaly Trigger & Provisional Event Tracking
1. Advance replay to the injected/recorded radio degradation window.
2. Watch the top **Status Banner** switch to `ANOMALY DETECTED` with `MEDIUM` severity.
3. Open **Events & Diagnosis** (Page 4):
   - Show the active event marked with `PROVISIONAL` badge.
   - Explain that live anomalies remain provisional while ongoing and finalize once stable (G23).
   - Show expanded multi-agent tabs:
     - **Signal Agent**: identifies drop in radio quality metrics.
     - **Cell Agent**: confirms whether a handover occurred in the temporal window.
     - **Diagnosis Agent**: outputs hedged description without false root-cause claims.

#### Minute 5: Alert Dispatch, Stream Health & Export
1. Show in-app alert banner and alert counter badge.
2. Navigate to **Stream Health** (Page 5):
   - Review processing latency percentiles (`p50 < 1 ms`, `p95 < 2 ms`).
   - Review queue depth, zero dropped frames, and clock skew monitor.
3. Navigate to **Data Quality** (Page 6):
   - Show total raw samples vs clean samples and sanitization log.
4. Click **Download C1 CSV** or **Download Event JSON** to demonstrate standardized data export.
5. Wrap up: point to footer notice affirming academic research prototype boundaries (G31).

---

## 3. Key Artifact References

- System & Stream Architecture: [`docs/streaming_architecture.md`](streaming_architecture.md)
- Wire Protocols & Contracts: [`docs/streaming_protocol.md`](streaming_protocol.md)
- Definition of Done v2 Audit: [`docs/definition_of_done_v2.md`](definition_of_done_v2.md)
- Results & Latency Benchmarks: [`docs/results_v2.md`](results_v2.md)
- Deployment Runbook: [`docs/deployment.md`](deployment.md)

# 5G-NADS System Architecture & Data Flow (T8-002)

This document describes the high-level system architecture, module boundaries, data contracts (C1–C6), and the strict separation of concerns between machine learning detection and multi-agent reasoning.

---

## 1. System Architecture Diagram

```mermaid
flowchart TD
    subgraph Layer 1: Android Measurement Collector
        A[Android Telephony Framework] -->|CellInfoNr / CellSignalStrengthNr| B[5G Network Tester App]
        B -->|Export CSV| C[(Raw Measurement CSVs)]
    end

    subgraph Layer 2: Pipeline & ML Detection
        C --> D[ml.preprocessing]
        D -->|Contract C2: Clean Measurements| E[ml.feature_engineering]
        E -->|Contract C3: Features| F[ml.anomaly_detection]
        F -->|Contract C4: Anomaly Scores| G[ml.anomaly_analysis]
    end

    subgraph Layer 3: Diagnostic Multi-Agent Layer
        G -->|Contract C4 & Event Windows| H[agents.orchestrator]
        H --> I[agents.signal_agent]
        H --> J[agents.cell_agent]
        H --> K[agents.network_agent]
        I & J & K --> L[agents.diagnosis_agent]
        L --> M[agents.recommendation_agent]
        M --> N[agents.text_renderer]
        N -->|Contract C5: events_diagnosed.json| O[(Streamlit Dashboard & JSON Artifacts)]
    end
```

---

## 2. Data Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Raw as Raw CSV (Contract C1)
    participant Prep as Preprocessing (Contract C2)
    participant Feat as Feature Engineering (Contract C3)
    participant ML as Anomaly Scoring & Classification (Contract C4)
    participant Orch as Agent Orchestrator
    participant Agents as Reasoning Agents (Signal, Cell, Network)
    participant Diag as Diagnosis & Recommendation Agents
    participant Out as Output (Contract C5 & Dashboard)

    Raw->>Prep: Validate headers, sentinels, and timestamp parsing
    Prep->>Feat: Clean measurements DataFrame
    Feat->>ML: Deltas, rolling stats, and persistence counters
    ML->>Orch: Baseline Z-scores, Isolation Forest scores & event windows
    Orch->>Agents: Pass EventWindow dataclasses
    Agents-->>Diag: SignalReport, CellReport, NetworkReport dataclasses
    Diag-->>Out: Unified Diagnosis & Recommendation JSON contract C5
```

---

## 3. Data Contracts Overview (C1–C6)

| Contract ID | Name | Format / Location | Key Content |
|---|---|---|---|
| **C1** | Raw Telephony CSV | CSV (`data/raw/`) | 18 Android Telephony framework raw signal columns. |
| **C2** | Clean Measurements | CSV (`data/processed/measurements_clean.csv`) | Coerced numeric metrics, timestamps, valid flags, and session IDs. |
| **C3** | Engineered Features | DataFrame | Deltas (`delta_rsrp`), rolling metrics, and run-length persistence flags. |
| **C4** | Anomaly Scores | CSV (`data/processed/scores.csv`) | Baseline z-scores, Isolation Forest anomaly probabilities, and anomaly classifications. |
| **C5** | Diagnosed Events | JSON (`data/processed/events_diagnosed.json`) | Complete multi-agent structured reports, evidence lists, and recommendations. |
| **C6** | Agent Dataclasses | Python Frozen Dataclasses (`agents/contracts.py`) | `EventWindow`, `SignalReport`, `CellReport`, `NetworkReport`, `Diagnosis`, `Recommendation`. |

---

## 4. Separation Statement: ML Detection vs. Agent Reasoning

Per project specification (§30) and Guardrails G9/G14:

1. **Detection Layer (`ml/`)**: Responsible solely for numerical processing, feature extraction, statistical baseline scoring, Isolation Forest inference, and categorical classification. It does not generate text explanations or actionable recommendations.
2. **Diagnostic Layer (`agents/`)**: Responsible solely for qualitative domain reasoning, evidence aggregation, hedged diagnosis attribution, and recommendation formatting. Reasoning agents **NEVER** import `sklearn` or load ML model binary files directly (Guardrail G9).

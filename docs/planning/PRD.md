# PRD — 5G-NADS (5G Network Anomaly Detection System)

> **Source of truth:** `project-overview.md`. If this PRD and the overview ever disagree, the overview wins — fix the PRD.
> **Team:** Yashwant Vadhan M · M A Sushil Kumar (work split equally — see `todo.md`)
> **Status legend:** ✅ implemented · 🔄 in progress · ⬜ not started · ⚠️ UNCLEAR = needs a decision

---

## Executive Summary

| Item | Value |
|---|---|
| **Project name** | 5G Network Anomaly Detection and Intelligent Diagnosis Using Real-Time NR Measurements and Multi-Agent Analysis (short: **5G-NADS**) |
| **Problem statement** | 5G connectivity degrades dynamically (weak signal, interference, congestion, cell transitions, loss of 5G). A single weak reading is not necessarily a problem, and a cell change is not necessarily a fault. There is no simple, interpretable tool that looks at *temporal combinations* of real UE-side NR measurements and explains what looks unusual. |
| **Solution overview** | Android app collects real 5G NR measurements (SS-RSRP/RSRQ/SINR, PCI, NCI, NRARFCN, network state) into CSV → Python pipeline preprocesses and engineers time-series features → **Isolation Forest** (compared against a rolling z-score baseline) scores anomalies → rule/evidence-based classifier labels the event → five deterministic agents (Signal, Cell, Network, Diagnosis, Recommendation) explain it → Streamlit dashboard presents it. |
| **Target audience** | Student researchers (the two authors), course evaluators/faculty, and technically curious network testers. This is a prototype/research system, **not** an operator-grade product. |
| **Platform** | Android (data collection, ✅ done) + Python/Streamlit (analysis and dashboard, runs locally) |

**Core objective (from overview §3):** detect unusual *temporal* patterns in real 5G NR measurements and give an *interpretable* diagnosis and recommendation.

**Hard boundary:** the Android app is only the measurement/collection layer. It does **not** run ML. ML and agents operate separately on the collected dataset.

---

## Goals & Objectives

### Business / Project Goals
1. Deliver a complete, tested, documented end-to-end pipeline that demonstrates the three-layer design: **device/radio → ML → multi-agent analysis** (overview §59).
2. Build a real multi-device, multi-operator NR dataset (primary dataset = real phone data).
3. Produce an honest evaluation: baseline vs Isolation Forest, false positives investigated, limitations stated.
4. Publish a clean GitHub repository that both humans and AI coding agents can navigate (`README.md`, `todo.md`, planning docs).

### User Goals
- **Researcher:** run one command and get scores, event types, diagnoses, and plots from a CSV.
- **Reviewer:** understand *why* something was flagged (evidence list) and what the system does **not** claim.
- **Tester:** see current radio metrics, anomaly status, and a plain-language recommendation.

### Success Metrics (KPIs)

> Numeric targets below are **proposals** chosen by the authors of this plan, not values from the overview. They are marked *(proposed)* and can be revised after EDA. The overview forbids universal thresholds and universal claims.

| KPI | Target |
|---|---|
| Data volume | ≥150–200 samples per device (overview §40) on ≥3 Android devices and ≥2 operators (Airtel, Vodafone) |
| Reproducibility | Re-running the pipeline on identical raw input yields identical processed CSV and identical anomaly scores (fixed random seed) — 100% |
| Test coverage *(proposed)* | ≥80% line coverage on `ml/` and `agents/` |
| Detection quality | Report precision, recall, F1, false-positive rate, detection rate, score distribution, detection latency for baseline **and** Isolation Forest on a manually labelled evaluation set. No pre-committed "IF must win" target — report honestly. |
| Alert volume *(proposed)* | Flagged fraction of samples on normal-condition data stays near the configured contamination (default to be tuned in EDA) |
| Dashboard load time *(proposed)* | p95 < 3 s to render Overview for a processed dataset ≤ 50,000 rows on a student laptop |
| Guardrail compliance | 100% of the 16 implementation rules (overview §56) covered by at least one automated test or documented check |

---

## User Personas

### P1 — Student Researcher (Yashwant / Sushil)
- **Description:** B.Tech AI & DS students building a portfolio-grade AI/ML + systems project.
- **Pain points:** unlabeled data, tiny initial dataset, risk of over-claiming, coordination between two people.
- **Goals:** reproducible pipeline, clear ownership split, results they can defend in a viva.

### P2 — Faculty / Course Evaluator
- **Description:** Evaluates technical soundness and honesty of claims.
- **Pain points:** projects that claim "universal 5G anomaly detection" or hide limitations.
- **Goals:** clear architecture, baseline comparison, documented limitations, working demo.

### P3 — Field Tester / Network-Curious Engineer
- **Description:** Wants to see what their phone's NR radio is doing.
- **Pain points:** raw dBm numbers without context; cannot tell normal cell handover from a real problem.
- **Goals:** readable dashboard, evidence-based explanation, sensible next step.

### P4 — AI Coding Agent (implementation persona)
- **Description:** Cursor / Claude Code / Codex / Gemini CLI executing `todo.md` tasks one at a time.
- **Pain points:** ambiguity, hidden assumptions, tasks that are too broad, temptation to fabricate data or add an LLM where none is needed.
- **Goals:** atomic tasks, explicit file paths, explicit guardrails, testable acceptance criteria.

---

## User Stories

### Data Collection & Management
- As a researcher, I want the Android app to log NR measurements every ~3 s to CSV so that I can build a real dataset. *(✅ implemented)*
- As a researcher, I want raw CSVs preserved untouched so that every result is reproducible.
- As a researcher, I want each collection run tagged with scenario/operator/device metadata (no precise location) so that I can compare conditions.

### Preprocessing & Features
- As a researcher, I want `NA` and Android sentinel values converted to missing values so that they are never treated as real measurements.
- As a researcher, I want delta, rolling, change-indicator and persistence features so that temporal behaviour is visible to the model.

### Detection & Classification
- As a researcher, I want a rolling z-score baseline and an Isolation Forest so that I can compare a simple and an ML method.
- As a researcher, I want anomalies classified (signal degradation, sudden degradation, cell transition, network-state transition, persistent poor quality, combined) so that events are interpretable.
- As a reviewer, I want a PCI/NCI change alone, low RSRP alone, low SINR alone, or `UNKNOWN` deployment mode to **not** be flagged so that the system avoids simplistic rules.

### Multi-Agent Diagnosis
- As a tester, I want each agent to report structured evidence so that the diagnosis is explainable.
- As a tester, I want a recommendation that only suggests monitoring/investigation actions the system can honestly support.

### Dashboard
- As a tester, I want to see current network state, radio metrics, anomaly status, score, event type, diagnosis, and recommendation on one screen.
- As a researcher, I want time-series charts with anomaly markers and cell/network transitions.

### Evaluation & Documentation
- As a reviewer, I want precision/recall/F1/FPR/latency reported for baseline vs Isolation Forest, with false positives investigated.
- As a reviewer, I want limitations and non-claims documented.

---

## Functional Requirements

### FR-1 — Android NR Collector (✅ implemented — verification and maintenance only)
- **Description:** App **5G Network Tester** (`com.example.a5gnetworktester`) reads `CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr` via Android Telephony APIs and writes CSV.
- **Inputs:** Android telephony state; runtime permissions.
- **Outputs:** CSV with header `timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn`.
- **User actions:** grant permissions, start/stop logging, export CSV.
- **Validation rules:** `deployment_mode ∈ {NSA, SA, UNKNOWN}`; **never guess SA**; unavailable values written as `NA`.
- **Edge cases:** sentinel `2147483647`; device exposes no CSI values; no NR cell visible (LTE only); permission denied; no PII (no phone number, contacts, messages, precise location — overview §49).

### FR-2 — Dataset Management
- **Description:** Organise raw CSVs, metadata, checksums and a small committed sample.
- **Inputs:** CSV files from devices.
- **Outputs:** `data/raw/` (immutable, git-ignored), `data/processed/` (generated, git-ignored), `data/sample/` (small, committed, real data excerpt), `data/raw/MANIFEST.sha256`, per-file `.meta.json`.
- **User actions:** drop new CSV into `data/raw/`, run manifest script.
- **Validation rules:** file naming `<device>_<operator>_<scenario>_<YYYYMMDD>_<HHMM>.csv`; header must match exactly; no file in `data/raw/` may be modified after manifest creation.
- **Edge cases:** duplicate files; header with different column order; empty file; CSV from an iPhone (**out of MVP** — Android API collector cannot be reused on iOS).

### FR-3 — Preprocessing (`ml/preprocessing.py`)
- **Description:** Pipeline from overview §25: load → validate columns → parse timestamp → sort by device + timestamp → numeric conversion → `NA`→missing → remove invalid measurements → handle missing values → sessionize.
- **Inputs:** raw CSV(s).
- **Outputs:** `data/processed/measurements_clean.csv` + processing log (row counts per step).
- **User actions:** CLI `python -m ml.preprocessing`.
- **Validation rules:** raw never overwritten; `NA` ≠ 0; missing CSI is **not** an anomaly; plausible-range checks per metric (⚠️ UNCLEAR: exact ranges — the plan proposes 3GPP/Android documented ranges, *verify against current Android `CellSignalStrengthNr` docs before hard-coding*).
- **Edge cases:** unsorted timestamps; duplicated timestamps; gaps >> 3 s (new session); mixed devices in one file; all-NA columns; timestamp format unknown (⚠️ UNCLEAR: overview does not state the timestamp format — detect and document in EDA).

### FR-4 — Feature Engineering (`ml/feature_engineering.py`)
- **Description:** Per (device, session): `delta_rsrp/rsrq/sinr`, `pci_changed`, `nci_changed`, `network_changed`, rolling mean/std for RSRP/RSRQ/SINR, persistence (run-length) features.
- **Inputs:** `measurements_clean.csv`; window size ∈ {5, 10, 20} samples (≈15/30/60 s at 3 s sampling) — final window chosen experimentally.
- **Outputs:** `data/processed/features.csv`, `FEATURE_COLUMNS` list.
- **Validation rules:** features never computed across device or session boundaries; first sample of a session has delta = missing and change flags = 0.
- **Edge cases:** missing previous sample; NA in RSRP but not SINR; window larger than session.

### FR-5 — Statistical Baseline (`ml/anomaly_detection.py`)
- **Description:** Rolling mean/std z-score; sample is unusual when it deviates strongly from its local baseline.
- **Outputs:** `baseline_z_*`, `baseline_flag`.
- **Edge cases:** std = 0 (flat signal) → z defined as 0, not infinity; warm-up period shorter than window.

### FR-6 — Isolation Forest (`ml/train.py`, `ml/anomaly_detection.py`)
- **Description:** Unsupervised Isolation Forest on engineered features. Initial baseline model chosen because data is tabular, unlabeled, small (overview §20). Not claimed universally best.
- **Inputs:** `features.csv`.
- **Outputs:** `models/if_v1.joblib`, `models/if_v1.meta.json` (features, params, seed, data hash), `if_score` (normalised 0–1), `if_flag`.
- **Validation rules:** fixed `random_state`; scaler fitted on training partition only; rows with missing model features excluded from scoring and marked `model_eligible=False` (never imputed with invented values).
- **Edge cases:** very small training set; single-device data; all rows ineligible.

### FR-7 — Anomaly Classification & Severity (`ml/anomaly_analysis.py`)
- **Description:** Rule/evidence-based labels: `SIGNAL_DEGRADATION`, `SUDDEN_SIGNAL_DEGRADATION`, `CELL_TRANSITION`, `NETWORK_STATE_TRANSITION`, `PERSISTENT_POOR_QUALITY`, `COMBINED_ANOMALY`, `NONE`. Optional severity LOW/MEDIUM/HIGH from score, persistence, magnitude, affected metrics, network-state changes.
- **Validation rules:** `CELL_TRANSITION` and `NETWORK_STATE_TRANSITION` are *events*; they become anomalies only in combination with degradation/persistence/repetition. Severity thresholds documented and validated, not arbitrary.
- **Edge cases:** overlapping event types → precedence rule (Combined > Persistent > Sudden > Degradation > Network > Cell); events split by a single missing sample; ML flag without rule evidence (report as "statistically unusual, no rule evidence").

### FR-8 — Multi-Agent Analysis (`agents/`)
- **Description:** Five deterministic Python components, each with one responsibility (overview §28):
  1. **Signal Agent** — RSRP/RSRQ/SINR, deltas, rolling stats → `signal_condition` + evidence.
  2. **Cell Agent** — PCI/NCI/NRARFCN/timestamps → `cell_event` (`NONE`, `CELL_CHANGE`, `REPEATED_CELL_CHANGE`, …) + evidence; distinguishes normal change from suspicious sequences.
  3. **Network Agent** — `network_type`, `deployment_mode`, `display_override`, `registered` → state/transition evidence; **preserves `UNKNOWN`, never infers SA**.
  4. **Diagnosis Agent** — combines the three outputs + ML score → most plausible category + explanation (hedged language, correlation ≠ causation).
  5. **Recommendation Agent** — diagnosis + severity + evidence → recommendation; separates *monitoring* actions from *network-operator* actions; never claims actions the system cannot perform.
- **Validation rules:** the ML flag is decided **before** agents run; agents cannot change it. No LLM is required for any agent.
- **Edge cases:** conflicting agent evidence; no evidence for an ML-flagged sample; missing CSI; window at start of session.

### FR-9 — Dashboard (`dashboard/`)
- **Description:** Streamlit + Plotly, technical and un-decorated (overview §32). Shows current network state, radio metrics, anomaly status (`NORMAL` / `ANOMALY DETECTED`), score, event type, diagnosis, recommendation, and the 8 recommended visualisations (RSRP/RSRQ/SINR over time, PCI/NCI changes, network-type transitions, score over time, anomaly markers, current status card).
- **Inputs:** `scores.csv` + `events_diagnosed.json` (replay mode over collected data). ⚠️ UNCLEAR: overview says "current measurements" — MVP interprets this as *replay of the latest processed session*; true live streaming from the phone is a future enhancement.
- **Validation rules:** any uploaded CSV validated (columns, size, types) before use; no external network calls.
- **Edge cases:** empty dataset; single-sample session; dataset with all `csi_* = NA`; `UNKNOWN` deployment mode shown as "Unknown (not exposed by device)" — never as SA.

### FR-10 — Evaluation (`ml/evaluate.py`)
- **Description:** Compare baseline vs Isolation Forest: precision, recall, F1, FPR, detection rate, score distribution, detection latency; device generalisation; operator variation; false-positive investigation.
- **Inputs:** scored data + small manually labelled evaluation set (two labellers, agreement recorded) + optional controlled-event ground truth.
- **Outputs:** `docs/results.md`, figures.
- **Edge cases:** very few positive labels → report counts and wide uncertainty instead of overclaiming.

### FR-11 — Cross-Cutting Guardrails (from overview §56)
Every task and every PR must respect these. They are testable and listed in `TECH_RULES.md` §Guardrails.
1. Keep Android collector separate from ML pipeline. 2. Never fabricate unavailable measurements. 3. `NA` = missing. 4. Never infer SA from `UNKNOWN`. 5. Never label every weak signal an anomaly. 6. Never label every PCI/NCI change an anomaly. 7. Preserve raw data. 8. Reproducible preprocessing. 9. ML detection separate from agent explanation. 10. Document assumptions. 11. Use real data wherever available. 12. Label synthetic data clearly. 13. Avoid unnecessary LLM dependence. 14. Clear agent responsibilities. 15. Tests for every major component. 16. Don't claim a component is implemented until tested.

---

## Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Preprocessing + features + scoring for 50,000 rows completes in < 60 s on a laptop *(proposed)*. Dashboard interactions < 1 s after initial load *(proposed)*. |
| **Scalability** | Prototype scale (hundreds to tens of thousands of rows). No distributed infrastructure. Growth plan: chunked processing only if data exceeds memory. |
| **Security & Privacy** | No PII collected or stored; no precise location unless justified; raw data stays local during development; no hard-coded credentials; `.env` for any future API key; uploaded CSVs validated; dashboard binds to localhost by default. Authentication, rate limiting and HTTPS are **not applicable** to a local single-user tool — recorded as *N/A by design*, revisit if ever hosted. |
| **Accessibility** | WCAG 2.1 AA target for colour contrast; anomalies marked by shape/text as well as colour; charts have text summaries. Streamlit's built-in accessibility limits acknowledged. |
| **Reliability** | Deterministic pipeline; explicit errors for schema violations; CI runs lint + tests on every PR. |
| **Maintainability** | Type hints, docstrings on public functions, `ruff` lint/format, Conventional Commits, one responsibility per module/agent. |
| **Reproducibility** | Pinned dependencies, fixed seeds, versioned model metadata, data checksums. |
| **Honesty** | Docs and dashboard must include the non-claims from overview §53. |

---

## Assumptions & Constraints
- Team of two; prototype-scale; local execution; no paid infrastructure.
- Initial sampling ≈ 1 sample / 3 s; ~150–200 samples per device to start.
- Real data has **no verified anomaly labels** initially → unsupervised first.
- Devices: Redmi 13 5G (Airtel), Samsung SM-A156E/DS (Airtel, Sushil), OnePlus Nord CE4 (Vodafone, Yaashwanth SKP — external contributor), iPhone 17 Pro (Vishal — **separate track, out of MVP**).
- Android may not expose CSI metrics or SA/NSA on every device; `UNKNOWN` and `NA` are valid, expected values.
- Python-based ML/agents; agents deterministic; LLM optional later, never in the core anomaly decision.
- Public datasets (Kaggle LTE/4G) are supplementary benchmarks only and are never presented as 5G.
- Synthetic data is allowed only for testing specific scenarios, always labelled `is_synthetic=True` and never mixed into real-data results.

## Open Questions (⚠️ UNCLEAR — resolve early, record answer in `docs/eda_findings.md`)
1. CSV `timestamp` format and timezone.
2. Complete list of sentinel/"equivalent unavailable" values beyond `2147483647`.
3. Session gap threshold (seconds) for splitting sessions.
4. Final window size (5 / 10 / 20 samples) and final feature set (decided after EDA).
5. Whether OnePlus/Vodafone data from Yaashwanth SKP will arrive in time.
6. Whether a precise-location column is needed (default: **no**).

---

## MVP Scope

### Must Have (overview §54 minimum system)
1. Android NR collector ✅ 2. CSV dataset (multi-device) 3. Python preprocessing 4. Feature engineering 5. Isolation Forest 6. Anomaly classification 7–11. Signal, Cell, Network, Diagnosis, Recommendation agents 12. Basic dashboard 13. Evaluation (baseline vs IF).

### Should Have
- Rolling z-score baseline comparison (needed for the evaluation claim, so effectively Must for evaluation).
- Severity estimation (LOW/MEDIUM/HIGH) with documented thresholds.
- Second independent labeller + agreement score.
- Data Quality page in dashboard.
- Controlled-experiment data (strong→weak coverage, indoor/outdoor).
- Presentation material and architecture diagrams.

### Nice To Have
- Optional local LLM explainer (Ollama) that only rephrases structured diagnosis — off by default.
- Supplementary public LTE benchmark.
- One-Class SVM / Local Outlier Factor comparison.

## Future Enhancements (must **not** be claimed as implemented — overview §55)
Larger multi-device/operator/location dataset · mobility-aware detection · supervised classification after labelling · LSTM/Transformer models · edge inference · federated learning · O-RAN integration · network-side KPIs and 5G core metrics · automated alerting · richer visualisation · operator NMS integration · iOS collection track.

## Explicit Non-Claims (must appear in README and dashboard "About")
Not universal 5G anomaly detection · no guaranteed root cause · no guaranteed SA/NSA identification · no operator-network control · no universal thresholds · not every cell transition is an anomaly · the Android app does not perform ML.

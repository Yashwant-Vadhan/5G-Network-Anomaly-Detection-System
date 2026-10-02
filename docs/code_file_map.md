# 📁 5G-NADS — Complete Code File Map

> **Purpose:** This document maps every code file, configuration, data asset, and document in the
> repository to its purpose. Reading this file top-to-bottom gives a full technical understanding of
> the **5G Network Anomaly Detection System (5G-NADS)**.

---

## Table of Contents

- [System Architecture at a Glance](#system-architecture-at-a-glance)
- [Data Flow Pipeline](#data-flow-pipeline)
- [Repository Root](#repository-root)
- [ml/ — Machine Learning Pipeline](#ml--machine-learning-pipeline)
- [agents/ — Multi-Agent Diagnostic Layer](#agents--multi-agent-diagnostic-layer)
- [pipelines/ — End-to-End Orchestration](#pipelines--end-to-end-orchestration)
- [dashboard/ — Streamlit Visualization UI](#dashboard--streamlit-visualization-ui)
- [android-collector/ — Mobile Telemetry App](#android-collector--mobile-telemetry-app)
- [scripts/ — Utility & Evaluation Scripts](#scripts--utility--evaluation-scripts)
- [tests/ — Test Suite](#tests--test-suite)
- [data/ — Dataset Storage](#data--dataset-storage)
- [models/ — Trained Model Artifacts](#models--trained-model-artifacts)
- [notebooks/ — Exploratory Analysis](#notebooks--exploratory-analysis)
- [docs/ — Project Documentation](#docs--project-documentation)
- [.github/ — CI/CD & Collaboration](#github--cicd--collaboration)
- [Configuration Files](#configuration-files)

---

## System Architecture at a Glance

```
┌──────────────────────┐
│  Android Collector   │  Kotlin app → raw CSV telemetry
│  (5GNetworkTester)   │
└─────────┬────────────┘
          │ CSV files (data/raw/)
          ▼
┌──────────────────────┐
│   ML Pipeline (ml/)  │  Preprocess → Features → Train → Detect → Classify
│                      │
└─────────┬────────────┘
          │ scores.csv + events.json
          ▼
┌──────────────────────┐
│  Agent Layer         │  Signal → Cell → Network → Diagnosis → Recommendation
│  (agents/)           │
└─────────┬────────────┘
          │ events_diagnosed.json
          ▼
┌──────────────────────┐
│  Dashboard           │  Streamlit multipage UI (6 pages)
│  (dashboard/)        │
└──────────────────────┘
```

---

## Data Flow Pipeline

The system transforms raw 5G signal measurements through a strict contract-based pipeline:

| Stage | Contract | Input | Output |
|-------|----------|-------|--------|
| **1. Collect** | C1 (raw CSV columns) | Android sensor APIs | `data/raw/*.csv` |
| **2. Preprocess** | C1 → C2 (clean DataFrame) | Raw CSVs | `measurements_clean.csv` |
| **3. Features** | C2 → C3 (feature matrix) | Clean measurements | `features.csv` |
| **4. Scale + Train** | C3 → model artifact | Feature matrix | `models/if_v1.joblib` |
| **5. Detect + Classify** | C3 → C4 (scored data) | Features + model | `scores.csv` + `events.json` |
| **6. Diagnose** | C4 → C5 (diagnosed events) | Events + scored data | `events_diagnosed.json` |
| **7. Visualize** | C5 → UI | Diagnosed events | Streamlit dashboard |

---

## Repository Root

| File | Purpose |
|------|---------|
| `README.md` | Project introduction, quickstart guide, status table, and documentation index |
| `project-overview.md` | **Source of truth** — full PRD with 58 numbered sections covering requirements, constraints, guardrails, dataset schema, and success metrics |
| `todo.md` | Task tracker with ~100 phased tasks (T1-xxx through T9-xxx), dependencies, and status |
| `pyproject.toml` | Ruff linter config (line-length=100, py312 target, lint rules E/F/I/B/UP/N), pytest paths, coverage settings (80% minimum) |
| `requirements.txt` | Runtime dependencies: pandas, numpy, scikit-learn, joblib, streamlit, plotly (exact pins) |
| `requirements-dev.txt` | Dev dependencies: pytest, pytest-cov, ruff, pre-commit, jupyter |
| `Makefile` | Developer entry points — `make setup`, `make lint`, `make test`, `make pipeline`, `make dashboard`, `make demo` |
| `CONTRIBUTING.md` | Contribution guidelines, branch strategy, commit format, and PR template reference |
| `.gitignore` | Ignores `.env`, `__pycache__`, `.venv`, processed data, model artifacts, etc. |
| `.env.example` | Environment template — `NADS_USE_LLM=false`, `OLLAMA_URL` for optional LLM explainer |

---

## ml/ — Machine Learning Pipeline

The `ml/` package implements the complete data processing and anomaly detection pipeline. Every module is a pure Python function library with no side effects on import.

### Core Pipeline Modules

| File | Purpose | Key Functions / Classes |
|------|---------|------------------------|
| **`__init__.py`** | Package marker (empty) | — |
| **`config.py`** | **Central constants registry.** All magic numbers, thresholds, column lists, and paths are declared here with origin comments tracing each value to a PRD section or EDA finding. Importing has zero side effects. | `RAW_COLUMNS`, `FEATURE_COLUMNS`, `VALID_RANGES`, `ANOMALY_TYPES`, `SEVERITY_LEVELS`, `IF_CONTAMINATION`, `RANDOM_STATE`, `REPO_ROOT`, path constants |
| **`schema.py`** | Schema validation and custom exceptions. Enforces Contract C1 (raw CSV columns) and privacy rules (PII column blacklist per §49). | `validate_raw_columns()`, `assert_no_pii_columns()`, `NADSError`, `SchemaError`, `DataQualityError`, `ConfigError`, `C2_DTYPES`, `FORBIDDEN_PII_COLUMNS` |
| **`preprocessing.py`** | **Stage 2 — Data Cleaning.** Loads raw CSVs, validates schema (C1), parses timestamps, coerces numerics, replaces Android sentinel values with NaN, validates signal ranges, assigns session IDs (30s gap rule), adds validity flags (`is_valid`, `model_eligible`, `csi_available`, `is_synthetic`). Outputs Contract C2 DataFrame. Also runnable as CLI. | `load_and_validate()`, `preprocess()`, `run_preprocessing_pipeline()`, `main()` |
| **`feature_engineering.py`** | **Stage 3 — Feature Extraction.** Computes per-session temporal features: delta values (sample-to-sample changes in RSRP/RSRQ/SINR), binary cell/network change indicators (`pci_changed`, `nci_changed`, `network_changed`), and rolling window statistics (mean/std over configurable window). Outputs Contract C3 feature matrix. | `compute_deltas()`, `compute_change_flags()`, `compute_rolling_stats()`, `build_features()` |
| **`scaler.py`** | **Feature Scaling.** Fits `StandardScaler` on model-eligible rows, transforms features, and persists scaler as joblib artifact. Handles NaN-safe scaling. | `fit_scaler()`, `transform_features()`, `save_scaler()`, `load_scaler()` |
| **`train.py`** | **Stage 4 — Model Training.** Trains `IsolationForest` with configured contamination rate and random state. Saves model with provenance metadata (SHA-256 hash of training data, timestamp, feature list, hyperparameters). | `train_model()`, `save_model()` |
| **`anomaly_detection.py`** | **Stage 5a — Anomaly Scoring.** Applies rolling z-score baseline detection and Isolation Forest scoring. Produces anomaly scores and binary flags per sample. | `baseline_z_score()`, `if_scores()`, `detect_anomalies()` |
| **`anomaly_analysis.py`** | **Stage 5b — Rule-Based Classification & Event Aggregation.** Classifies flagged samples into typed anomalies (SIGNAL_DEGRADATION, SUDDEN_SIGNAL_DEGRADATION, PERSISTENT_POOR_QUALITY, CELL_TRANSITION, NETWORK_STATE_TRANSITION, COMBINED_ANOMALY) using deterministic rules. Groups consecutive anomalous samples into events with precedence logic. Outputs Contract C4 `events.json`. | `classify_anomalies()`, `aggregate_events()`, `detect()` |
| **`evaluate.py`** | **Model Evaluation.** Computes sample-level and event-level metrics: precision, recall, F1, false-positive rate, detection rate, detection latency. Compares model predictions against ground-truth labels. | `compute_metrics()`, `event_level_metrics()`, `evaluate_pipeline()` |
| **`label_agreement.py`** | **Inter-Annotator Agreement.** Computes overlap and Cohen's kappa between two human labellers, adjudicates final ground-truth labels via majority vote, and outputs `data/eval/labels_final.csv`. | `compute_agreement()`, `adjudicate_labels()` |

### How the ML modules connect

```
config.py ──────────────────────────────────────────────────────────┐
  (constants referenced by all modules)                             │
                                                                    │
schema.py ──► preprocessing.py ──► feature_engineering.py           │
  (validate)    (clean C1→C2)       (engineer C2→C3)                │
                                         │                          │
                                    scaler.py                       │
                                    (scale C3)                      │
                                         │                          │
                                    train.py ──► anomaly_detection.py
                                    (fit IF)      (score C3→C4)     │
                                                       │            │
                                              anomaly_analysis.py   │
                                              (classify → events)   │
                                                       │            │
                                              evaluate.py           │
                                              (vs ground truth)     │
```

---

## agents/ — Multi-Agent Diagnostic Layer

The `agents/` package implements a deterministic multi-agent pipeline that interprets ML detection results into human-readable diagnostics. **Guardrail G9:** No agent imports sklearn or loads ML models directly — they receive only structured data contracts.

| File | Purpose | Key Functions / Classes |
|------|---------|------------------------|
| **`__init__.py`** | Package marker (empty) | — |
| **`contracts.py`** | **Frozen dataclass contracts (C6).** Defines the structured input/output types exchanged between agents. Each dataclass is `@dataclass(frozen=True)` for immutability. | `EventWindow`, `SignalReport`, `CellReport`, `NetworkReport`, `Diagnosis`, `Recommendation` |
| **`signal_agent.py`** | **Signal Agent (T5-002).** Analyzes RSRP, RSRQ, SINR values, deltas, and rolling statistics within an event window. Produces a `SignalReport` with trend direction, quality assessment, and hedged observations. **G14:** Only signal reasoning — no cell or network logic. | `analyze(event: EventWindow) → SignalReport` |
| **`cell_agent.py`** | **Cell Agent (T5-003).** Analyzes PCI and NCI cell identifiers within an event window to detect handover transitions. | `analyze(event: EventWindow) → CellReport` |
| **`network_agent.py`** | **Network-State Agent (T5-004).** Analyzes network_type, deployment_mode, display_override, and registration status. **G4:** Never infers SA when deployment_mode is UNKNOWN. | `analyze(event: EventWindow) → NetworkReport` |
| **`diagnosis_agent.py`** | **Diagnosis Agent (T5-005).** Synthesizes signal, cell, network, and ML anomaly evidence into a cohesive `Diagnosis` object with anomaly type, severity, and hedged summary. | `diagnose(signal, cell, network, anomaly_info) → Diagnosis` |
| **`recommendation_agent.py`** | **Recommendation Agent (T5-006).** Generates practical, actionable recommendations (MONITORING or OPERATOR_ACTION) based on diagnosis severity and evidence. | `recommend(diagnosis: Diagnosis) → Recommendation` |
| **`orchestrator.py`** | **Pipeline Orchestrator (T5-001).** Constructs `EventWindow` objects from detection results and drives the agent pipeline: Signal → Cell → Network → Diagnosis → Recommendation. **G9:** Must not import sklearn. Outputs Contract C5 `events_diagnosed.json`. | `build_event_window()`, `run_event()`, `run_all_events()`, `write_events_diagnosed()` |
| **`text_renderer.py`** | **Deterministic Text Renderer (T5-007).** Renders Diagnosis and Recommendation objects into structured, hedged explanation text using fixed templates. Enforces Copy Rules (no causal claims like "caused", "proven"). No LLM dependency. | `render_diagnosis()`, `render_recommendation()`, `FORBIDDEN_WORDS` |
| **`llm_explainer.py`** | **Optional LLM Explainer (T9-001).** Calls a local Ollama endpoint to generate natural-language explanations. Disabled by default (`NADS_USE_LLM=false`). Falls back gracefully to template text on any failure. **G13:** Core pipeline never depends on this. | `explain()`, `is_enabled()` |

### Agent Pipeline Flow

```
EventWindow ──► signal_agent.analyze() ──► SignalReport
             ├► cell_agent.analyze()   ──► CellReport
             ├► network_agent.analyze()──► NetworkReport
             │
             └► diagnosis_agent.diagnose(signal, cell, network) ──► Diagnosis
                                                                       │
                          recommendation_agent.recommend(diagnosis) ◄──┘
                                         │
                                    Recommendation
                                         │
                              text_renderer.render() ──► hedged explanation text
```

---

## pipelines/ — End-to-End Orchestration

| File | Purpose | Key Functions |
|------|---------|---------------|
| **`__init__.py`** | Package marker (empty) | — |
| **`run_pipeline.py`** | **Master CLI (T7-001).** Runs the full automated pipeline end-to-end: verify manifest → preprocess → features → train (if needed) → detect + classify → agent diagnostics. Accepts `--input`, `--output`, `--retrain`, `--sample` flags. This is the single command to reproduce all results. | `main()`, `run()` |

**Usage:** `python -m pipelines.run_pipeline --input data/raw --output data/processed`

---

## dashboard/ — Streamlit Visualization UI

A multipage Streamlit application providing interactive exploration of pipeline results.

### Core Dashboard Modules

| File | Purpose |
|------|---------|
| **`__init__.py`** | Package marker (empty) |
| **`app.py`** | **Main entry point (T6-001).** Configures Streamlit page settings, sidebar branding, and multipage navigation. Launch via `streamlit run dashboard/app.py`. |
| **`data_loader.py`** | **Cached data loaders (T6-001, T6-009).** Loads processed CSVs, events JSON, and metadata with `@st.cache_data`. Handles user-uploaded CSVs with ≤20 MB size limit and column validation. Graceful empty-state defaults. |
| **`sidebar.py`** | **Global sidebar filters (T6-010).** Device, operator, session, and time-range filters with state persistence in `st.session_state` across all pages. |
| **`theme.py`** | **Design system tokens (T6-002).** Color palette, font stacks, and Plotly theme defaults matching DESIGN.md. Ensures visual consistency across all charts. |

### Dashboard Pages

| File | Page | What It Shows |
|------|------|---------------|
| **`pages/1_Overview.py`** | 📊 Overview (T6-003) | Network health KPIs, current-sample metrics, anomaly score gauge, agent diagnosis summary, evidence cards, and recommendations |
| **`pages/2_Signal_Explorer.py`** | 📈 Signal Explorer (T6-004) | Stacked Plotly time-series (RSRP, RSRQ, SINR) with red anomaly markers, flag filter toggles, text summaries, and interactive data table |
| **`pages/3_Cells_And_Network.py`** | 🗼 Cells & Network (T6-005) | Cell transition visualization (PCI, NCI, NRARFCN), network-type changes (5G NR vs LTE), transition event tables with neutral copy framing |
| **`pages/4_Events_And_Diagnosis.py`** | 🔍 Events & Diagnosis (T6-007) | Anomaly event list with type/severity filters, multi-agent structured reports (Signal, Cell, Network, Diagnosis, Recommendation), event-window charts, JSON export |
| **`pages/5_Data_Quality.py`** | 🛡️ Data Quality (T6-008) | Missing value analysis, CSI availability, deployment mode distribution, preprocessing logs, synthetic data indicators |
| **`pages/6_About_And_Limitations.py`** | ℹ️ About & Limitations (T6-011) | Architecture summary, PRD non-claims, dataset docs, model metadata, documentation links |

---

## android-collector/ — Mobile Telemetry App

Kotlin/Android application that collects 5G NR signal measurements from the device modem.

| Path | Purpose |
|------|---------|
| `5GNetworkTester/` | Android Studio project root |
| `app/build.gradle.kts` | App module build config, dependencies, SDK versions |
| `build.gradle.kts` | Project-level Gradle config |
| `settings.gradle.kts` | Gradle settings and plugin management |
| `gradle.properties` | JVM args, AndroidX flags |
| `gradlew` / `gradlew.bat` | Gradle wrapper scripts (Linux/Windows) |
| `app/src/main/.../MainActivity.kt` | **Main activity.** Uses `TelephonyManager` APIs to read `CellSignalStrengthNr` (SS-RSRP, SS-RSRQ, SS-SINR, CSI-RSRP, CSI-RSRQ, CSI-SINR), cell identity (PCI, NCI, NRARFCN), network type, and deployment mode. Logs readings as CSV rows every ~3 seconds. |
| `app/src/main/.../ui/theme/` | Jetpack Compose theme files (Color.kt, Theme.kt, Type.kt) |
| `app/src/test/.../ExampleUnitTest.kt` | Placeholder unit test |
| `app/src/androidTest/.../ExampleInstrumentedTest.kt` | Placeholder instrumented test |

---

## scripts/ — Utility & Evaluation Scripts

| File | Purpose |
|------|---------|
| **`make_manifest.py`** | **(T2-004)** Generates and verifies SHA-256 checksum manifest (`MANIFEST.sha256`) for raw dataset files. Ensures data integrity and reproducibility. Usage: `python scripts/make_manifest.py data/raw [--verify]` |
| **`check_staged_files.py`** | **(T1-004)** Pre-commit hook guard. Blocks `data/raw/` files (except README/MANIFEST) and files >5 MB from being committed. Implements Guardrail G7 (preserve raw data). |
| **`eval_device_generalisation.py`** | **(T7-017)** Cross-device evaluation. Trains Isolation Forest on one device (e.g., Redmi) and evaluates on another (e.g., Samsung). Records cross-device transfer metrics and modem-specific caveats. |
| **`evaluate_extra_models.py`** | **(T9-004)** Benchmark script for LOF (Local Outlier Factor) and One-Class SVM. Trains alternative models on same features, evaluates against ground truth, and compares with IF baseline. |

---

## tests/ — Test Suite

136 tests, 84.31% branch coverage over `ml/` and `agents/`. Run via `make test` or `pytest`.

### Test Files

| File | What It Tests | Coverage Target |
|------|---------------|-----------------|
| **`test_preprocessing.py`** | CSV loading, schema validation, sentinel replacement, range validation, sessionization, CLI entry point | `ml/preprocessing.py` |
| **`test_schema.py`** | Column validation (C1), PII blacklist, custom exceptions | `ml/schema.py` |
| **`test_feature_engineering.py`** | Delta computation, change flags, rolling stats, NaN handling, session boundaries | `ml/feature_engineering.py` |
| **`test_features.py`** | Feature column contract (C3), feature list consistency | `ml/config.py` features |
| **`test_scaler.py`** | StandardScaler fit/transform, NaN safety, persistence round-trip | `ml/scaler.py` |
| **`test_train.py`** | IsolationForest training, metadata generation, model persistence | `ml/train.py` |
| **`test_anomaly_detection.py`** | Z-score baseline, IF scoring, combined detection, edge cases | `ml/anomaly_detection.py` |
| **`test_anomaly_analysis.py`** | Rule-based classification, event aggregation, precedence logic | `ml/anomaly_analysis.py` |
| **`test_classification.py`** | Extended anomaly type classification scenarios, severity assignment | `ml/anomaly_analysis.py` |
| **`test_evaluate.py`** | Metric computation (precision, recall, F1, FPR), edge cases | `ml/evaluate.py` |
| **`test_agents.py`** | All 5 specialist agents + orchestrator integration: signal analysis, cell transitions, network state, diagnosis synthesis, recommendation generation | `agents/*.py` |
| **`test_contracts.py`** | Dataclass immutability, field validation, serialization | `agents/contracts.py` |
| **`test_llm_explainer.py`** | LLM explainer enable/disable, Ollama fallback, error handling | `agents/llm_explainer.py` |
| **`test_pipeline_integration.py`** | Full end-to-end pipeline run on sample data, contract output validation | `pipelines/run_pipeline.py` |
| **`test_pipeline_cli.py`** | CLI argument parsing, help text, error paths | `pipelines/run_pipeline.py` |
| **`test_manifest.py`** | SHA-256 manifest generation and verification | `scripts/make_manifest.py` |
| **`test_dashboard_loader.py`** | Data loader caching, missing file handling, upload validation | `dashboard/data_loader.py` |
| **`test_dashboard_pages.py`** | Page module imports, function existence | `dashboard/pages/*.py` |
| **`test_dashboard_sidebar.py`** | Sidebar filter rendering, state persistence | `dashboard/sidebar.py` |
| **`test_dashboard_smoke.py`** | Dashboard smoke tests: all pages importable, no crash on empty data | `dashboard/*.py` |
| **`test_security_privacy.py`** | PII column rejection, XSRF config, file size limits, no-secrets audit | Security guardrails |

### Test Fixtures

| File | Purpose |
|------|---------|
| `fixtures/README.md` | Fixture documentation |
| `fixtures/edge_cases_synthetic.csv` | Synthetic edge-case CSV for boundary testing (extreme values, missing fields, sentinel integers) |

---

## data/ — Dataset Storage

| Path | Purpose | Git Tracked? |
|------|---------|-------------|
| `data/README.md` | Dataset documentation, schema description, collection protocol | ✅ Yes |
| **`data/raw/`** | Original collected CSVs from Android devices. **Never modified** (Guardrail G7). | ✅ Yes |
| `data/raw/5G_measurements_*.csv` | 6 CSV files: 2 devices (Redmi, Samsung) × 3 scenarios (Stable, Indoor-Movement, Travel) | ✅ Yes |
| `data/raw/*.meta.json` | Per-file metadata (device, scenario, collection date, row count) | ✅ Yes |
| `data/raw/MANIFEST.sha256` | SHA-256 checksums for all raw CSVs (integrity verification) | ✅ Yes |
| `data/raw/meta.template.json` | Template for new collection metadata files | ✅ Yes |
| `data/raw/README.md` | Raw data documentation and collection protocol | ✅ Yes |
| **`data/processed/`** | Pipeline outputs (regenerated by `make pipeline`) | ❌ .gitignored |
| `data/processed/measurements_clean.csv` | Contract C2: cleaned, validated, sessionized measurements | ❌ Generated |
| `data/processed/preprocess_log.json` | Preprocessing run metadata and statistics | ❌ Generated |
| `data/processed/features.csv` | Contract C3: engineered feature matrix | ❌ Generated |
| `data/processed/scores.csv` | Contract C4: anomaly scores and flags per sample | ❌ Generated |
| `data/processed/events.json` | Contract C4: aggregated anomaly events | ❌ Generated |
| `data/processed/events_diagnosed.json` | Contract C5: events with full agent diagnostic reports | ❌ Generated |
| **`data/sample/`** | Minimal sample data for `make demo` and CI smoke tests | ✅ Yes |
| `data/sample/sample_measurements.csv` | Small representative dataset for quick testing | ✅ Yes |
| **`data/eval/`** | Ground-truth labels for model evaluation | ✅ Yes |
| `data/eval/labels_yashwant.csv` | Annotator 1 labels (Yashwant) | ✅ Yes |
| `data/eval/labels_sushil.csv` | Annotator 2 labels (Sushil) | ✅ Yes |
| `data/eval/labels_final.csv` | Adjudicated consensus labels (majority vote) | ✅ Yes |

---

## models/ — Trained Model Artifacts

| File | Purpose |
|------|---------|
| `if_v1.joblib` | Serialized IsolationForest model (scikit-learn, joblib format) |
| `if_v1.meta.json` | Model provenance: training data hash, timestamp, feature list, hyperparameters, scikit-learn version |
| `scaler.joblib` | Fitted StandardScaler for feature normalization |

---

## notebooks/ — Exploratory Analysis

| File | Purpose |
|------|---------|
| `exploratory_analysis.ipynb` | **EDA notebook.** Statistical profiling, distribution analysis, missing value patterns, correlation heatmaps, temporal patterns. Findings documented in `docs/eda_findings.md`. |
| `model_selection.ipynb` | **Model selection study.** Compares IF contamination rates, evaluates alternative models, justifies final hyperparameter choices. |
| `supplementary_lte_benchmark.py` | LTE-vs-5G signal quality benchmark script for supplementary analysis |

---

## docs/ — Project Documentation

### Planning Documents

| File | Purpose |
|------|---------|
| `planning/PRD.md` | Product Requirements Document — features, success metrics, constraints |
| `planning/DESIGN.md` | UI/UX design specifications — color palette, layout, component specs |
| `planning/TECH_RULES.md` | **Engineering rules** — coding standards, contracts (C1–C6), guardrails (G1–G15), commit format, testing requirements |
| `planning/ROADMAP.md` | Phase-by-phase delivery roadmap with status tracking |

### Technical Documentation

| File | Purpose |
|------|---------|
| `architecture.md` | System architecture overview — layers, data flow, deployment model |
| `agent_architecture.md` | Agent pipeline design — contracts, orchestration, determinism guarantees |
| `ml_methodology.md` | ML approach — Isolation Forest rationale, feature engineering strategy, evaluation methodology |
| `dataset.md` | Dataset schema, integrity checks, collection protocol, device matrix |
| `eda_findings.md` | EDA results — distributions, missing patterns, sentinel values, session gaps |
| `decisions.md` | Architectural Decision Records (ADRs) — key technical choices and rationale |

### Evaluation & Results

| File | Purpose |
|------|---------|
| `results.md` | Evaluation results — precision, recall, F1, FPR, detection latency across scenarios |
| `controlled_experiments.md` | Controlled experiment design — contamination sweep, window size ablation |
| `false_positive_analysis.md` | Deep-dive into false positive patterns, root causes, and mitigation strategies |
| `device_generalisation_report.md` | Cross-device transfer evaluation — Redmi→Samsung and Samsung→Redmi |

### Guidelines & Process

| File | Purpose |
|------|---------|
| `labelling_guidelines.md` | Annotation protocol — anomaly type definitions, labelling rules, examples |
| `labelling_notes.md` | Inter-annotator agreement results and adjudication notes |
| `testing.md` | Test strategy — unit/integration/smoke test plan, coverage targets |
| `guardrails_checklist.md` | Guardrail compliance checklist (G1–G15) with verification status |

### Release & Presentation

| File | Purpose |
|------|---------|
| `definition_of_done.md` | 25-item DoD audit — verifies every MVP requirement is met |
| `limitations_and_future_scope.md` | Explicit system limitations, non-claims, and future development directions |
| `presentation.md` | Slide outline and demo script for project presentation |
| `ios_collection_note.md` | iOS data collection feasibility analysis and API limitations |

---

## .github/ — CI/CD & Collaboration

| File | Purpose |
|------|---------|
| `workflows/ci.yml` | **GitHub Actions CI pipeline.** Triggers on push to `main` and all PRs. Steps: checkout → Python 3.13 setup → install deps → `ruff check` → `ruff format --check` → `pytest --cov-fail-under=80`. |
| `pull_request_template.md` | PR template with checklist: tests, lint, docs, guardrails compliance |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | **Ruff config:** line-length=100, target=py312, rules=E/F/I/B/UP/N, excludes android-collector/data/notebooks. **Pytest config:** testpaths=tests, pythonpath=. **Coverage config:** source=ml+agents, branch=true, fail_under=80. |
| `.pre-commit-config.yaml` | Pre-commit hooks: (1) ruff-check with auto-fix, (2) ruff-format, (3) custom `check_staged_files.py` to block raw data and large files |
| `.streamlit/config.toml` | Streamlit server config: theme colors (Blue 600 primary, Slate 900 text), headless=true, localhost-only, XSRF protection enabled, 20 MB upload limit |
| `.env.example` | Environment variable template — LLM toggle and Ollama endpoint (both optional) |

---

## Key Design Principles

1. **Contract-Driven:** Every pipeline stage has a named contract (C1–C6) with defined columns, types, and invariants
2. **No Magic Numbers:** All thresholds in `ml/config.py` with origin comments
3. **Deterministic Core:** ML detection and agent reasoning use no LLM — results are reproducible given the same input
4. **Privacy by Design:** PII column blacklist enforced at schema validation; no location/identity data collected
5. **Guardrail System:** 15 guardrails (G1–G15) enforced through code, tests, and pre-commit hooks
6. **Hedged Language:** All explanations use "may indicate", "observed", "suggests" — never causal claims like "caused" or "proven"

---

*Generated for 5G-NADS v1.0.0 — MVP Complete*

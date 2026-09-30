# Architectural Decision Records (ADRs) — 5G-NADS

> Record of key architectural, design, and scope decisions for 5G-NADS.
> Source of truth for requirements: `project-overview.md` and `docs/planning/TECH_RULES.md`.

---

## ADR-001: Deterministic Modular Python Agents over LLM-First Core

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: The diagnostic layer must explain detected anomaly events by combining signal metrics, cell transitions, and network state changes.
- **Decision**: Multi-agent layer is built using **pure, deterministic Python classes/functions** using rule-based structured evidence reasoning (Signal, Cell, Network, Diagnosis, Recommendation). Core anomaly decisions and initial diagnoses **do not depend on an LLM**.
- **Rationale**: Ensures 100% reproducible execution, zero API costs, zero external network dependencies, lower compute latency, and testable evidence. An optional local LLM via Ollama may be added later (Phase 9, `NADS_USE_LLM=false` by default) solely to rephrase already-decided structured outputs. See [TECH_RULES Decision Record](planning/TECH_RULES.md#decision-record--agent-implementation-answers-ollama-or-something-better).

---

## ADR-002: Isolation Forest and Rolling Z-Score as Baseline Models

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Real UE-side 5G NR measurements are tabular, time-series, and unlabeled.
- **Decision**: Use scikit-learn `IsolationForest` combined with a rolling window z-score as the initial unsupervised detection baseline.
- **Rationale**: Isolation Forest handles multi-dimensional tabular data without requiring labeled anomaly datasets. Rolling z-score provides a simple, transparent temporal baseline. Neither model is claimed as universally optimal; complex neural architectures (e.g. LSTM autoencoders) are deferred until data scale justifies them (overview §44).

---

## ADR-003: iPhone / iOS Out of Scope for MVP

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Collector application requires accessing low-level raw 5G NR physical layer cell parameters (`CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr`).
- **Decision**: Focus exclusively on Android (Kotlin collector app). iOS support is out of scope for the MVP.
- **Rationale**: iOS CoreTelephony APIs do not provide equivalent public API access to raw NR metrics (e.g. SS-RSRP/SINR, PCI, NCI, NRARFCN) from non-entitled third-party applications.

---

## ADR-004: Privacy Protection and Coarse Location Labels Only

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Real-world cellular measurement collection must respect user privacy.
- **Decision**: Reject all precise location parameters (GPS coordinates, latitude, longitude, street addresses) and personal identifiers (phone numbers, IMSI, IMEI). Use coarse text tags for location metadata (e.g., `"campus_outdoor"`, `"hostel_indoor"`).
- **Rationale**: Guarantees user privacy compliance (overview §49) while providing sufficient environment context for anomaly diagnosis. Enforced by automated PII checks (`assert_no_pii_columns`).

---

## ADR-005: File-Based Dataset Storage over Database System

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Storage strategy needed for raw CSVs, cleaned measurements, engineered features, scores, and diagnosed events.
- **Decision**: Use organized directory storage (`data/raw/`, `data/processed/`, `data/sample/`, `models/`) with checksum manifests (`MANIFEST.sha256`) instead of a relational or NoSQL database.
- **Rationale**: At prototype scale (thousands to tens of thousands of batch rows), file storage keeps raw data preservation and reproducibility simple without database administration overhead.

---

## ADR-006: Local Single-User Execution Model (Auth / Rate Limiting / HTTPS N/A)

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: System runtime target and deployment architecture.
- **Decision**: 5G-NADS is designed as a local single-user research tool executed via CLI (`pipelines/run_pipeline.py`) and Streamlit dashboard (`dashboard/app.py` bound to `127.0.0.1`).
- **Rationale**: Authentication, user authorization, API rate limiting, and HTTPS encryption are **N/A by design** for local workstation execution. If the dashboard is ever deployed to cloud hosting, authentication must be added prior to enabling public access.

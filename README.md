# 5G-NADS — 5G Network Anomaly Detection and Diagnosis System

Android-based 5G NR measurement and anomaly detection system for analyzing real-world cellular network performance. 5G-NADS collects real Non-Standalone/Standalone (NSA/SA) NR measurements directly from Android devices, detects unusual *temporal* patterns using a statistical baseline and an Isolation Forest model, classifies them into interpretable categories, and explains each detected event through a deterministic, evidence-based multi-agent diagnostic layer — without relying on operator-network access or synthetic data.

This is a research/course project, not an operator-grade product. See [Non-Claims](#non-claims) below for what this system does not do.

## Status

| Component | Status |
|---|---|
| Android NR measurement collector | ✅ Implemented and verified against C1 |
| Real-device dataset collection | ✅ Completed (Redmi: 3760 samples; Samsung: 1772 samples across 3 scenarios each) |
| Data preprocessing pipeline | ✅ Implemented and verified against C2 (30 unit tests passing) |
| Feature engineering | ✅ Implemented and verified against C3 |
| Anomaly detection (baseline z-score + Isolation Forest) | ✅ Implemented and verified |
| Anomaly classification & severity | ✅ Implemented and verified |
| Multi-agent diagnostic layer (Signal / Cell / Network / Diagnosis / Recommendation) | ✅ Implemented and verified (Contract C5 & text renderer) |
| Interpretability dashboard (Streamlit) | ✅ Implemented and verified (Six screens, WCAG accessibility & responsive pass — T6-001 to T6-012) |
| End-to-end pipeline & tests | ✅ CLI (T7-001), integration tests (T7-007), and security/privacy test suite (T7-009) passing |
| Evaluation & Labelling Guidelines | ✅ Completed (Labelling guidelines T7-011, evaluation labels T7-012/T7-013, baseline vs IF benchmark T7-016, false-positive report T7-018) |

Status is updated only once a component has passing tests — see the guardrail in `docs/planning/TECH_RULES.md` (G16: no "implemented" claim before tested). Full task breakdown, ownership, and dependencies are in [`todo.md`](./todo.md).

## Architecture

Three separated layers, kept independently verifiable:

1. **Measurement Layer** — Android app reads live NR cell info, signal strength, and cell identity via the Android Telephony framework (`CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr`) and exports timestamped measurements to CSV. Performs no analysis.
2. **Detection Layer** — Python pipeline validates and cleans the data, engineers temporal features (deltas, rolling stats, persistence counters), and scores each sample with a rolling z-score baseline and an Isolation Forest model.
3. **Diagnostic Layer** — Five deterministic agents (Signal, Cell, Network, Diagnosis, Recommendation) turn a detected event into a structured, evidence-based, hedged explanation and a monitoring-oriented recommendation. No LLM is used in the core detection or diagnosis decision.

Full architecture, data contracts, and rationale: [`docs/planning/TECH_RULES.md`](docs/planning/TECH_RULES.md).

## Quick Start

```bash
git clone https://github.com/Yashwant-Vadhan/5G-Network-Anomaly-Detection-System.git
cd 5G-Network-Anomaly-Detection-System
python -m venv .venv
source .venv/bin/activate            # POSIX
.venv\Scripts\activate               # Windows (PowerShell / cmd)
pip install -r requirements-dev.txt  # Python 3.12+
make lint test          # verify setup and run full unit/integration test suite
make pipeline           # run preprocessing → features → detection → multi-agent diagnostic layer
make dashboard          # launch the Streamlit interpretability dashboard on 127.0.0.1
```

`make help` lists every target. On Windows without `make`, run the underlying
commands directly, e.g. `python -m ruff check .` and `python -m pytest`.

## Repository Map

```
5G-NADS/
├── android-collector/     # Android NR measurement collector (Kotlin)
├── data/
│   ├── raw/               # immutable, git-ignored; real device CSVs
│   ├── processed/         # generated, git-ignored
│   ├── sample/            # small committed real-data excerpt
│   └── eval/              # ground truth evaluation labels
├── ml/                    # preprocessing, feature engineering, detection models
├── agents/                # Signal / Cell / Network / Diagnosis / Recommendation agents
├── pipelines/             # end-to-end pipeline CLI
├── dashboard/             # Streamlit interpretability dashboard
├── models/                # trained model artifacts + metadata
├── notebooks/             # EDA and model-selection notebooks
├── tests/                 # unit / integration / e2e tests
├── docs/
│   └── planning/          # PRD.md, DESIGN.md, TECH_RULES.md, ROADMAP.md
├── todo.md                # full task breakdown, ownership, dependencies
└── project-overview.md    # original project specification (source of truth)
```

## Data Policy

- Raw measurement CSVs are **never committed** — they live in `data/raw/`, which is git-ignored except for a checksum manifest.
- No PII is collected: no phone number, contacts, messages, or precise location.
- Missing measurements (`NA`, Android sentinel values) are preserved as missing — never treated as zero.
- An unreported (`UNKNOWN`) deployment mode is never inferred to be SA.
- Synthetic data, where used for testing, is explicitly labelled and never mixed into real-data results.

Full policy: [`docs/planning/TECH_RULES.md`](docs/planning/TECH_RULES.md) (Security Rules) and [`docs/planning/PRD.md`](docs/planning/PRD.md) (Assumptions & Constraints).

## Documentation

| Document | Contents |
|---|---|
| [`project-overview.md`](./project-overview.md) | Original project specification — source of truth |
| [`docs/planning/PRD.md`](docs/planning/PRD.md) | Goals, personas, user stories, functional/non-functional requirements, MVP scope |
| [`docs/planning/DESIGN.md`](docs/planning/DESIGN.md) | Dashboard information architecture, screens, design system |
| [`docs/planning/TECH_RULES.md`](docs/planning/TECH_RULES.md) | Architecture, tech stack, data contracts, coding/security/testing standards, guardrails |
| [`docs/planning/ROADMAP.md`](docs/planning/ROADMAP.md) | Milestones, effort estimates, risk register |
| [`todo.md`](./todo.md) | Full task list with ownership, dependencies, and acceptance criteria |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Setup, branch/commit conventions, task claiming, guardrail checklist for contributors and AI agents |
| [`docs/eda_findings.md`](docs/eda_findings.md) | Collector verification results, EDA observations, and answers to open questions |
| [`docs/decisions.md`](docs/decisions.md) | Architectural Decision Records (ADRs) covering agents, ML baseline, privacy, and storage |
| [`docs/testing.md`](docs/testing.md) | Security and privacy checks, test suite structure, and non-applicable security items |
| [`docs/guardrails_checklist.md`](docs/guardrails_checklist.md) | Complete audit mapping of G1–G16 guardrails to test suites and enforcement mechanisms |
| [`docs/labelling_guidelines.md`](docs/labelling_guidelines.md) | Guidelines and blind labelling schema for human ground-truth evaluation |
| [`docs/dataset.md`](docs/dataset.md) | Dataset documentation, schema details, missing-value policies, and MANIFEST verification |
| [`docs/agent_architecture.md`](docs/agent_architecture.md) | Multi-agent diagnostic layer architecture, responsibilities, contracts, and execution flow |
| [`docs/results.md`](docs/results.md) | Baseline vs. Isolation Forest quantitative evaluation results & latency analysis |
| [`docs/false_positive_analysis.md`](docs/false_positive_analysis.md) | False positive & negative investigation report with severity validation |
| [`data/README.md`](data/README.md) | Data contract C1 verification, timestamp format, sentinel behaviour, and data directory structure |

## Non-Claims

5G-NADS does **not** claim to:
- Provide universal 5G anomaly detection generalizable beyond the collected dataset
- Guarantee identification of root cause for a detected anomaly
- Guarantee correct SA/NSA identification when the device itself reports it as unknown
- Control or modify the operator network in any way
- Treat every cell transition, or every weak-signal reading, as an anomaly on its own

## Team

Yashwant Vadhan M · M A Sushil Kumar
Dept. of Artificial Intelligence and Data Science, Madras Institute of Technology Campus, Anna University

# 5G-NADS — 5G Network Anomaly Detection and Diagnosis System

Android-based 5G NR measurement and anomaly detection system for analyzing real-world cellular network performance. 5G-NADS collects real Non-Standalone/Standalone (NSA/SA) NR measurements directly from Android devices, detects unusual *temporal* patterns using a statistical baseline and an Isolation Forest model, classifies them into interpretable categories, and explains each detected event through a deterministic, evidence-based multi-agent diagnostic layer — without relying on operator-network access or synthetic data.

This is a research/course project, not an operator-grade product. See [Non-Claims](#non-claims) below for what this system does not do.

## Status

| Component | Status |
|---|---|
| Android NR measurement collector | ✅ Implemented |
| Real-device dataset collection | 🔄 In progress |
| Data preprocessing pipeline | ⬜ Not started |
| Feature engineering | ⬜ Not started |
| Anomaly detection (baseline z-score + Isolation Forest) | ⬜ Not started |
| Anomaly classification & severity | ⬜ Not started |
| Multi-agent diagnostic layer (Signal / Cell / Network / Diagnosis / Recommendation) | ⬜ Not started |
| Interpretability dashboard (Streamlit) | ⬜ Not started |
| End-to-end pipeline & tests | ⬜ Not started |
| Evaluation (baseline vs. Isolation Forest) | ⬜ Not started |

Status is updated only once a component has passing tests — see the guardrail in `docs/planning/TECH_RULES.md` (G16: no "implemented" claim before tested). Full task breakdown, ownership, and dependencies are in [`todo.md`](./todo.md).

## Architecture

Three separated layers, kept independently verifiable:

1. **Measurement Layer** — Android app reads live NR cell info, signal strength, and cell identity via the Android Telephony framework (`CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr`) and exports timestamped measurements to CSV. Performs no analysis.
2. **Detection Layer** — Python pipeline validates and cleans the data, engineers temporal features (deltas, rolling stats, persistence counters), and scores each sample with a rolling z-score baseline and an Isolation Forest model.
3. **Diagnostic Layer** — Five deterministic agents (Signal, Cell, Network, Diagnosis, Recommendation) turn a detected event into a structured, evidence-based, hedged explanation and a monitoring-oriented recommendation. No LLM is used in the core detection or diagnosis decision.

Full architecture, data contracts, and rationale: [`docs/planning/TECH_RULES.md`](docs/planning/TECH_RULES.md).

## Quick Start

> Tooling (`make lint`, `make test`, `make help`) is in place; the analysis pipeline commands below are the target workflow and arrive with the later phases of `todo.md`.

```bash
git clone https://github.com/Yashwant-Vadhan/5G-Network-Anomaly-Detection-System.git
cd 5G-Network-Anomaly-Detection-System
python -m venv .venv
source .venv/bin/activate            # POSIX
.venv\Scripts\activate               # Windows (PowerShell / cmd)
pip install -r requirements-dev.txt  # Python 3.12+
make lint test          # verify setup
make pipeline           # run preprocessing → features → detection → agents
make dashboard          # launch the Streamlit dashboard on 127.0.0.1
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
│   └── sample/            # small committed real-data excerpt
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

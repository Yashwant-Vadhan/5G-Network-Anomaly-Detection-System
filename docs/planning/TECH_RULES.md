# TECH_RULES — 5G-NADS

> Binding rules for humans **and** AI coding agents. Source of truth for behaviour: `project-overview.md`.
> Version pins and third-party API details below are *design intent*; **verify exact versions and APIs at implementation time** (they change).

---

## Architecture Overview

### Frontend Architecture
- **Streamlit** multipage app (`dashboard/`) with **Plotly** charts. Read-only consumer of pipeline artifacts (`scores.csv`, `events_diagnosed.json`, `models/*.meta.json`). No business logic in the UI: the dashboard never recomputes scores or diagnoses.

### Backend Architecture
- There is no web backend. The "backend" is a **batch Python pipeline** (`pipelines/run_pipeline.py`) composed of pure, individually testable modules:
  `ml/preprocessing.py → ml/feature_engineering.py → ml/anomaly_detection.py → ml/anomaly_analysis.py → agents/* → artifacts`.
- **Agents are plain deterministic Python functions/classes**, not a framework. An `agents/orchestrator.py` calls them in the order Signal → Cell → Network → Diagnosis → Recommendation.

### Database Architecture
- No database. Storage is **files**:
  - `data/raw/*.csv` — immutable, git-ignored, checksummed.
  - `data/processed/*.csv|json` — generated, git-ignored, reproducible.
  - `data/sample/` — small committed excerpt of real data for tests/CI/demo.
  - `models/` — `joblib` model + JSON metadata.
- Rationale: prototype scale (hundreds to tens of thousands of rows); files keep raw data preservation and reproducibility simple. A DB adds no value here.

### Deployment Architecture
- Local execution (`make run` / `streamlit run dashboard/app.py`). CI on GitHub Actions for lint + tests. Optional later: Streamlit Community Cloud or Docker — **not in MVP** and would require revisiting security (auth, upload limits).

### Architecture Diagram

```
 5G network ─► Android NR Collector (Kotlin, 5G Network Tester) ─► CSV (device)
                                                                     │  copy
                                                                     ▼
                                                            data/raw/ (immutable)
                                                                     │
      ┌──────────────────────── Python pipeline (batch) ────────────┴───────────────┐
      │ preprocessing ► feature_engineering ► baseline z-score + Isolation Forest    │
      │                                   ► anomaly_analysis (classification+severity)│
      │                                   ► agents: Signal ┐                          │
      │                                                    ├► Diagnosis ► Recommend.  │
      │                                             Cell ──┤   (Network ┘)            │
      └──────────────────────────────────────────────┬───────────────────────────────┘
                                                     ▼
                           data/processed/{measurements_clean,features,scores}.csv
                           data/processed/events_diagnosed.json   models/if_v1.*
                                                     ▼
                                           Streamlit dashboard (read-only)
```

---

## Decision Record — Agent Implementation (answers "Ollama or something better?")

| Question | Decision |
|---|---|
| What does `project-overview.md` say? | §36–37: agents are **deterministic modular Python components**. LLMs "may be added later if needed for natural-language explanation", but **the core anomaly decision must not depend on an LLM**. Ollama is **not mentioned** in the file. |
| MVP agent implementation | **Deterministic Python** (rules over structured evidence) + template-based text. No LLM, no agent framework. |
| Optional explanation layer | *Nice-to-have (todo Phase 9).* If added, a **local** LLM through **Ollama** is a reasonable fit (no API keys, works offline, measurement data stays on the machine). It may only **rephrase** the already-decided structured diagnosis, must be **off by default** (`NADS_USE_LLM=false`), must time out gracefully to the template text, and must never alter `is_anomaly`, `anomaly_type`, `severity`, or agent evidence. |
| Why not LLM-first? | Reproducibility, measurable performance, deterministic behaviour, easier evaluation and debugging, lower compute cost, clean detection/explanation separation (overview §37). |
| Why not LangChain/CrewAI/AutoGen? | Five fixed, sequential steps do not need an orchestration framework; extra dependencies add non-determinism and failure modes. *(This is the plan's recommendation, not stated in the overview.)* |
| Hosted LLM APIs? | Not needed. If ever used, keys only via environment variables; never send raw data without a conscious decision. |

Hardware note: running a local LLM needs RAM/VRAM that I cannot assess from here — **check your machines before committing to Ollama**, and use a small model. This is optional work, so the MVP is unaffected.

---

## Tech Stack

| Layer | Technology | Purpose | Why Chosen | Alternatives Considered |
|---|---|---|---|---|
| Mobile collector | Android, Kotlin, Telephony APIs (`CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr`) | Real NR measurements → CSV | Only route to real UE-side NR values; already built | iOS (no equivalent public API path; separate track) |
| Language | Python 3.11+ *(verify team version)* | ML, agents, dashboard | Ecosystem, team skill | R, Julia |
| Data | pandas, NumPy | Time-series tables, features | Standard, sufficient at this scale | Polars (faster, unnecessary) |
| ML | scikit-learn `IsolationForest`, `StandardScaler` | Unsupervised anomaly detection | Tabular, unlabeled, light, gives scores (overview §20) | One-Class SVM, LOF (later comparison), Autoencoder/LSTM (only if data justifies — overview §44) |
| Persistence | joblib + JSON metadata | Model + provenance | Standard for sklearn | pickle (unsafe/opaque), ONNX (overkill) |
| Baseline | rolling z-score (pandas) | Simple comparison (overview §45) | Transparent, cheap | EWMA, CUSUM |
| Agents | Plain Python + `dataclasses` | Explainable analysis | Deterministic, testable (overview §36) | LLM agents, agent frameworks (see Decision Record) |
| Dashboard | Streamlit + Plotly | Interpretable UI | Fast to build, Python-only (overview §36) | Dash, Flask+React (more code), Grafana |
| Testing | pytest, pytest-cov | Unit/integration/e2e | Standard | unittest |
| Lint/format | ruff (+ optional mypy) | Consistency | Fast, one tool | black+flake8+isort |
| Hooks | pre-commit | Local quality gate | Catches issues before CI | none |
| CI | GitHub Actions | Lint + test on PR | Repo already on GitHub | none |
| Notebooks | Jupyter | EDA only | Overview §35 lists notebook | scripts (kept for anything reusable) |
| Optional LLM | Ollama (local HTTP API) | Rephrase diagnosis | Local/private (Phase 9 only) | hosted APIs |

---

## Folder Structure

Matches overview §35, with additions marked `+`.

```
5G-NADS/
├── android-collector/
│   └── 5GNetworkTester/          # Kotlin project (no keystores/local.properties committed)
├── data/
│   ├── raw/                      # immutable, git-ignored; README + MANIFEST.sha256 committed
│   ├── processed/                # generated, git-ignored
│   └── sample/                   # small committed real-data excerpt
├── ml/
│   ├── config.py                 # + constants: columns, sentinels, windows, thresholds
│   ├── schema.py                 # + column dtypes, validation helpers
│   ├── preprocessing.py
│   ├── feature_engineering.py
│   ├── anomaly_detection.py      # baseline + Isolation Forest scoring
│   ├── anomaly_analysis.py       # classification + severity + event grouping
│   ├── train.py
│   └── evaluate.py
├── agents/
│   ├── contracts.py              # + dataclasses: AgentInput/Output schemas
│   ├── orchestrator.py           # + runs agents in order
│   ├── signal_agent.py
│   ├── cell_agent.py
│   ├── network_agent.py
│   ├── diagnosis_agent.py
│   ├── recommendation_agent.py
│   └── llm_explainer.py          # + OPTIONAL (Phase 9), off by default
├── pipelines/
│   └── run_pipeline.py           # + end-to-end CLI
├── dashboard/
│   ├── app.py
│   ├── theme.py
│   └── pages/
├── models/                       # joblib + .meta.json (git-ignored except metadata example)
├── notebooks/
│   └── exploratory_analysis.ipynb
├── scripts/                      # + make_manifest.py, misc helpers
├── docs/                         # + planning/ (PRD, DESIGN, TECH_RULES, ROADMAP), eda_findings.md, results.md, ...
├── tests/
│   ├── fixtures/                 # + synthetic CSVs, clearly named *_synthetic.csv
│   └── ...
├── .github/workflows/ci.yml      # +
├── .github/pull_request_template.md  # +
├── .env.example                  # +
├── .gitignore  pyproject.toml  Makefile  # +
├── requirements.txt  requirements-dev.txt
├── README.md
├── CONTRIBUTING.md               # +
├── todo.md                       # +
└── project-overview.md
```

---

## Data Contracts (the interfaces the two developers code against)

> Defined first (todo T1-008) so both people can work in parallel. Change a contract only via PR that updates this section, `ml/schema.py`, and affected tests.

### C1 — Raw CSV (from Android collector)
`timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn`
Missing values are the literal `NA` or Android sentinel (`2147483647`, plus any others found in EDA — ⚠️ UNCLEAR).

### C2 — `data/processed/measurements_clean.csv`
All C1 columns with proper dtypes (`timestamp` → datetime; numerics → float/Int64 with `NaN`/`<NA>`), plus:
| Column | Type | Meaning |
|---|---|---|
| `session_id` | str | `<device>-<n>`; new session when time gap > `SESSION_GAP_SECONDS` |
| `sample_idx` | int | 0-based index within session |
| `is_valid` | bool | passed plausible-range checks |
| `model_eligible` | bool | all required model features present |
| `csi_available` | bool | any CSI value present (informational only, **never** an anomaly signal) |
| `is_synthetic` | bool | always `False` for real data |

### C3 — `data/processed/features.csv`
C2 columns plus: `delta_rsrp, delta_rsrq, delta_sinr, pci_changed, nci_changed, network_changed, rolling_mean_{rsrp,rsrq,sinr}, rolling_std_{rsrp,rsrq,sinr}` and persistence features (e.g., `poor_sinr_run`, `poor_rsrq_run`, `weak_rsrp_run`). Final list = `FEATURE_COLUMNS` in `ml/config.py`, fixed after EDA.

### C4 — `data/processed/scores.csv`
C3 columns plus: `baseline_z_max, baseline_flag, if_score (0–1, higher = more unusual), if_flag, anomaly_type, severity, event_id`.

### C5 — `data/processed/events_diagnosed.json`
List of events:
```json
{
  "event_id": "redmi-1-e003",
  "session_id": "redmi-1",
  "start": "ISO-8601", "end": "ISO-8601",
  "anomaly_type": "COMBINED_ANOMALY",
  "severity": "MEDIUM",
  "ml": {"if_score": 0.71, "if_flag": true, "baseline_flag": true},
  "signal":  {"signal_condition": "degraded", "evidence": ["SINR dropped from +3 to -7", "RSRP decreased"]},
  "cell":    {"cell_event": "CELL_CHANGE", "evidence": ["PCI changed from 336 to 565", "NCI changed"]},
  "network": {"network_state": "STABLE_NR", "deployment_mode": "UNKNOWN", "evidence": []},
  "diagnosis": {"summary": "Possible radio-quality degradation associated with a cell transition.", "evidence": ["..."], "confidence_note": "correlation, not confirmed cause"},
  "recommendation": {"text": "Continue monitoring...", "kind": "MONITORING"}
}
```
(The example values echo the overview's illustrative scenario — not a ground-truth diagnosis.)

### C6 — Agent I/O
`agents/contracts.py` defines frozen dataclasses: `EventWindow` (DataFrame slice + metadata), `SignalReport`, `CellReport`, `NetworkReport`, `Diagnosis`, `Recommendation`. Every report has `evidence: list[str]` (human-readable, no LLM required).

---

## Coding Standards

### Naming Conventions
- Files/modules: `snake_case.py`. Classes: `PascalCase`. Functions/variables: `snake_case`. Constants: `UPPER_SNAKE` in `ml/config.py`.
- CSV columns: `snake_case`, identical to overview §11; engineered columns as listed in C3–C4.
- Enums (strings, UPPER_SNAKE): `NORMAL`, `SIGNAL_DEGRADATION`, `SUDDEN_SIGNAL_DEGRADATION`, `CELL_TRANSITION`, `NETWORK_STATE_TRANSITION`, `PERSISTENT_POOR_QUALITY`, `COMBINED_ANOMALY`; severity `LOW|MEDIUM|HIGH`; deployment `NSA|SA|UNKNOWN`.

### Component Structure
- Pure functions preferred: `DataFrame in → DataFrame out`, no hidden global state, no I/O inside computation functions (I/O only in thin CLI/`run_*` wrappers).
- One responsibility per module and per agent. Agents accept an `EventWindow` and return a report dataclass; they never read files.
- Thresholds live in `ml/config.py` with a comment stating their origin (EDA finding, documented assumption, or literature). **No magic numbers inline.** Thresholds are dataset-specific and must not be described as universal.

### API Standards
- No HTTP API in MVP. Public Python functions have type hints and docstrings (purpose, inputs, outputs, raises). CLI via `argparse`/`python -m`, with `--help`.
- If an Ollama call is added (Phase 9): isolated in `agents/llm_explainer.py`, plain HTTP to localhost, 10 s timeout, no retries beyond one, returns `None` on any failure.

### Error Handling Strategy
- Custom exceptions in `ml/schema.py`: `SchemaError` (missing/extra columns), `DataQualityError` (empty after filtering, all-NA required feature), `ConfigError`.
- CLIs catch these, print a one-line cause + fix hint, exit code 2. No bare `except`. Never silently drop rows — always log counts.
- Dashboard converts exceptions to `st.error` messages (no tracebacks).

### Logging Standards
- Python `logging`, module-level logger, INFO for pipeline steps with row counts (`loaded 412 rows → 405 after validation`), WARNING for data-quality issues, DEBUG for per-sample details. No `print` in library code. Never log raw PII (none collected).

---

## Guardrails (testable rules from overview §56 — each maps to a test in todo Phase 7)

| # | Rule | Test idea |
|---|---|---|
| G1 | Collector ≠ ML pipeline | Repo check: no ML imports in `android-collector/`; pipeline reads only CSV |
| G2 | Never fabricate measurements | No `fillna`/interpolation on `ss_*`/`csi_*` in processed output; test asserts NaN preserved |
| G3 | `NA` is missing | `NA`, `2147483647` → NaN; never 0 |
| G4 | Never infer SA from UNKNOWN | Network Agent test with UNKNOWN input never outputs SA |
| G5 | Weak signal alone ≠ anomaly | Classification test: low RSRP only → `NONE` |
| G6 | PCI/NCI change alone ≠ anomaly | Classification test: cell change only → `CELL_TRANSITION` event, not anomaly |
| G7 | Preserve raw data | Preprocessing refuses `--output` inside `data/raw/`; manifest check |
| G8 | Reproducible preprocessing | Run twice → identical output hash |
| G9 | ML separate from agents | Agent modules do not import `sklearn`; changing agent text does not change flags |
| G10 | Document assumptions | `docs/assumptions.md` (or section in EDA findings) exists and is linked |
| G11 | Use real data | Tests/sample use real excerpt; synthetic only in `tests/fixtures/*_synthetic.csv` |
| G12 | Label synthetic data | Synthetic files must end `_synthetic.csv`; preprocessing sets `is_synthetic=True` for them; test asserts it |
| G13 | No unnecessary LLM | Core pipeline runs with LLM env unset and no network |
| G14 | Clear agent responsibilities | Each agent module ≤ 1 report type; contract tests |
| G15 | Tests per major component | CI coverage gate on `ml/`, `agents/` |
| G16 | No "implemented" claims before tested | README status table updated only in a PR that adds passing tests |

---

## Security Rules
- **Authentication / Authorization:** N/A by design (local single-user tool). If ever hosted, add auth *before* exposing uploads.
- **Data validation:** all CSV loads go through `ml/schema.py` validation (exact header, dtypes, row cap, file-size cap for uploads — proposed 20 MB); reject files with unexpected columns rather than guessing.
- **Privacy:** no phone number, contacts, messages, or precise location in data or logs (overview §49). Location metadata is coarse text (e.g., "hostel indoor").
- **Rate limiting:** N/A (no server).
- **Secrets:** none required in MVP. Any future key via environment variable; `.env` git-ignored; `.env.example` committed with placeholders only. Run a secret scan (e.g., `gitleaks` or grep-based check) in CI or pre-commit.
- **Android project hygiene:** never commit `local.properties`, keystores, or signing passwords.
- **HTTPS/TLS:** N/A locally; if Streamlit is exposed, terminate TLS at a reverse proxy. Streamlit binds to `127.0.0.1` by default in scripts.
- **Raw data:** kept locally/shared-private storage during development (overview §50); not committed.

## Performance Rules
- **Frontend:** `st.cache_data` for loaded CSVs; downsample plots above ~5,000 points for rendering only (never for scoring); lazy-render pages.
- **Backend:** vectorised pandas (no row-wise Python loops for features); process per device/session with `groupby`; avoid copying large frames unnecessarily.
- **Database:** N/A. **Indexing:** sort once by (`device`, `timestamp`); keep `session_id` categorical.
- **Caching:** cache processed artifacts on disk keyed by input hash; recompute only when raw manifest changes.

## Testing Rules
- **Unit:** pytest; every function in `ml/` and `agents/` has at least one test including a negative/edge case; coverage gate ≥80% on `ml/` and `agents/` *(proposed)*.
- **Integration:** full pipeline on `data/sample/` and on synthetic fixtures; asserts contracts C2–C5 (columns, dtypes, no NaN in required outputs).
- **End-to-end:** `run_pipeline` → dashboard smoke test (Streamlit's app-testing utility, if available in the pinned version — verify) confirming pages render without exceptions on sample data.
- **Determinism:** same input + seed → identical scores (assert with tolerance 0 on flags, tiny tolerance on floats).
- **Guardrail tests:** one test per G1–G16 where automatable.
- **Fixtures:** synthetic data lives only in `tests/fixtures/` and is named `*_synthetic.csv`.

## Git Workflow
- **Branches:** `main` (protected: PR + 1 approval + green CI). Feature branches: `feat/<owner>/<task-id>-<slug>` e.g. `feat/yashwant/T3-002-timestamp-parsing`; fixes `fix/<owner>/<slug>`; docs `docs/<owner>/<slug>`. Owners: `yashwant`, `sushil`.
- **Commits:** Conventional Commits with the task ID in scope: `feat(T4-008): train isolation forest with fixed seed`. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.
- **Pull requests:** one task (or a tightly-related pair) per PR; the **other** teammate reviews; PR template checklist: task ID, acceptance criteria ticked, tests added, guardrails checked, docs/README status updated only if tested. Squash-merge.
- **Task claiming:** a task is started by changing its status marker in `todo.md` to 🔄 in the same PR/branch that starts the work; finished tasks are marked ✅ in the PR that completes them.
- **AI-agent PRs** follow the same rules; the human owner reviews and remains responsible.

## Deployment Rules
- **CI/CD:** GitHub Actions — on PR: install pinned deps, `ruff check`, `ruff format --check`, `pytest --cov`. No deployment step in MVP.
- **Environments:** single local environment (dev). `config` differences via env vars only.
- **Monitoring & alerting:** N/A for local tool; pipeline logs are the record. Model metadata JSON records data hash, params, seed, feature list.
- **Backup strategy:** raw CSVs mirrored to a private shared cloud folder both teammates can access; `MANIFEST.sha256` committed so integrity is checkable; never rely on a single laptop.

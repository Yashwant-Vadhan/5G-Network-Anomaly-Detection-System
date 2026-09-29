# ROADMAP — 5G-NADS

> Effort figures come from `todo.md` (planning estimates, not measurements). No calendar dates or deadline were provided, so milestones are ordered by dependency and sized in hours per person. Add dates once the team's deadline is known.
> Team: Yashwant Vadhan M (repo/CI, Redmi + OnePlus-coordination data, preprocessing/feature core, model training and scoring, signal-side classification, Signal/Cell/Diagnosis agents) · M A Sushil Kumar (schema/contracts, Samsung data, sessions/missing-value handling, baseline, cell/network classification and severity, Network/Recommendation agents, most of the dashboard) — MVP totals 38.8 h / 40.2 h, within ~4%.

---

## Overview

Delivery is phased so that **a complete but minimal pipeline exists before anything is polished**, matching the overview's "Minimum Viable Final System" (§54): real data → preprocessing → features → Isolation Forest → classification → five agents → basic dashboard → evaluation.

| Milestone | Theme | `todo.md` phases | Yashwant | Sushil |
|---|---|---|---|---|
| M0 | Foundation & Data | 1–2 | 9.3 h | 5.3 h |
| M1 | MVP Core (pipeline works end-to-end in code) | 3–5 | 14.6 h | 14.2 h |
| M2 | MVP Complete & Polish (dashboard, tests, evaluation, docs, v1.0.0) | 6–8 | 14.9 h | 20.8 h |
| M3 | Growth (optional) | 9 | 3.0 h | 3.2 h |
| M4 | Scale & Optimise (future, not planned in detail) | — | — | — |
| **MVP total (M0–M2)** | | 1–8 | **38.8 h** | **40.2 h** |

Yashwant's hours front-load into M0–M1 (repo/CI, all data collection, preprocessing, training); Sushil's back-load into M2 (the dashboard is mostly his). Both can start immediately once the Phase 1 contracts are merged — see `todo.md`'s Parallelizable Tasks list.

Note: the generic template puts "Should Have" in M2. Here the dashboard and the baseline-vs-IF evaluation are **Must Have** in the overview (§54), so they live in M2 together with the polish items (severity validation, dual labelling, docs).

---

## Milestone Structure

### Milestone 0 — Foundation & Setup
- **Objective:** Two people can work in parallel without stepping on each other; real multi-device data exists and is protected.
- **Tasks/Features:** repo skeleton, tooling, CI, shared config, data contracts (C1–C6), Makefile, Android project import + collector verification, raw-data conventions and checksum manifest, data collection (Redmi, Samsung, OnePlus if it arrives), committed real sample, synthetic edge-case fixtures, decision log.
- **Dependencies:** none (starts immediately). Data collection needs phones and physical movement — schedule it early, it is the least compressible work.
- **Estimated Complexity:** Low–Medium (logistics-heavy, not algorithm-heavy).
- **Acceptance Criteria:**
  - [ ] `pip install -r requirements-dev.txt`, `make lint test` work on both machines and CI is green.
  - [ ] Contracts C1–C6 and `ml/config.py` / `ml/schema.py` / `agents/contracts.py` merged.
  - [ ] ≥200 samples per scenario (A/B/C) for Redmi and Samsung in `data/raw/`, manifest committed and `--verify` passes.
  - [ ] `data/sample/` (real) and `tests/fixtures/edge_cases_synthetic.csv` (labelled synthetic) exist.
  - [ ] Timestamp format and sentinel behaviour documented in `data/README.md`.

### Milestone 1 — MVP Core
- **Objective:** Raw CSV → scored, classified, agent-explained events, produced by code and verified by tests on the sample.
- **Features (Must Have only):** preprocessing (validation, timestamps, NA/sentinels → missing, range flags, sessions, missing-value policy, CLI), EDA and findings doc, feature engineering (deltas, change flags, rolling stats, persistence), rolling z-score baseline, Isolation Forest (train + score), classification (6 categories + precedence), severity, event grouping, five agents + deterministic text renderer, `events_diagnosed.json`.
- **Dependencies:** M0 (contracts, fixtures, at least Redmi + Samsung stationary data). EDA (T3-012) gates threshold-dependent tasks in Phase 4.
- **Estimated Complexity:** High (most of the intellectual work; the critical path of ~21 sequential hours runs through here and into evaluation).
- **Acceptance Criteria:**
  - [ ] Preprocessing is idempotent (identical output hash on two runs) and never writes into `data/raw/`.
  - [ ] `scores.csv` (C4) and `events_diagnosed.json` (C5) generated from `data/sample/`.
  - [ ] Negative cases pass: low RSRP alone, low SINR alone, PCI/NCI change alone, 5G→LTE alone, UNKNOWN alone → **not anomalies**.
  - [ ] Network Agent never outputs SA for UNKNOWN; agent modules do not import scikit-learn.
  - [ ] `docs/eda_findings.md` answers PRD Open Questions 1–4 or states why they remain open.

### Milestone 2 — MVP Complete & Polish
- **Objective:** A demonstrable, tested, evaluated, documented system and a tagged release.
- **Features (Must Have remainder + Should Have):** Streamlit dashboard (six screens, states, filters, upload validation), end-to-end pipeline CLI, unit/integration/e2e/security tests, guardrail audit (G1–G16), two-labeller evaluation set with agreement, evaluate.py, baseline vs Isolation Forest comparison with detection latency, device/operator analysis, false-positive investigation, severity validation, README, architecture/dataset/methodology/agent/testing/limitations docs, presentation material, fresh-clone verification, Definition-of-Done audit, `v1.0.0`.
- **Dependencies:** M1 (scores and events), labelled data from both people, dashboard needs `scores.csv`.
- **Estimated Complexity:** Medium–High (evaluation with tiny, self-labelled data needs careful honesty).
- **Acceptance Criteria:**
  - [ ] `make setup demo` works from a fresh clone on both teammates' machines.
  - [ ] Coverage ≥80% on `ml/` and `agents/` *(proposed target)*; all guardrails G1–G16 mapped to a test or documented check.
  - [ ] `docs/results.md` reports precision/recall/F1/FPR/detection rate/latency for **both** baseline and IF on the same labels, with label counts; states plainly if IF does not beat the baseline.
  - [ ] False positives investigated in `docs/false_positive_analysis.md`.
  - [ ] README, dashboard About page and slides contain the Non-Claims (overview §53).
  - [ ] Overview §58 Definition of Done audited with evidence links; `v1.0.0` tagged only if MVP is complete.

### Milestone 3 — Growth Features (optional; start only after M2 is accepted)
- **Objective:** Strengthen the project without touching the core decision path.
- **Features (Nice To Have + first Future Enhancements):**
  - Local LLM explainer via **Ollama** — rephrases the already-decided structured diagnosis; off by default; timeout falls back to template text; must not change flags/type/severity (see TECH_RULES Decision Record).
  - Supplementary public LTE/4G benchmark (clearly labelled LTE, never presented as the 5G dataset).
  - Local Outlier Factor / One-Class SVM comparison on the same labels.
  - Controlled natural-event experiments with logged event times.
  - iOS collection research note (no code).
- **Dependencies:** M2 accepted; hardware check before Ollama.
- **Estimated Complexity:** Medium.
- **Acceptance Criteria:**
  - [ ] Pipeline outputs are byte-identical with LLM on vs off.
  - [ ] Every supplementary result is labelled with its data source and scope.
  - [ ] No new claim exceeds the evidence.

### Milestone 4 — Scale & Optimise (future; not scheduled)
- **Objective:** Directions the overview lists as future scope (§55). **Do not claim any of these as implemented.**
- **Features:** larger multi-device/operator/location dataset; mobility-aware detection; supervised classification once enough labels exist; LSTM/Transformer time-series models (only if data size justifies); edge inference; federated learning; O-RAN integration; network-side KPIs and 5G core metrics; automated alerting; live streaming from the phone to the dashboard; richer visualisation; integration with operator systems; iOS collector.
- **Dependencies:** M2/M3 results; substantially more labelled data.
- **Estimated Complexity:** High.
- **Acceptance Criteria:** defined per feature when (and if) one is adopted.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| External OnePlus/Vodafone data (Yaashwanth SKP) never arrives | Medium | Medium | MVP needs only Redmi + Samsung (two devices, both Airtel); operator-variation analysis is then stated as not possible, not faked |
| Only ~150–200 samples per scenario → unstable model, weak evaluation | High | High | Multiple scenarios, seed-stability study, honest small-sample caveats, no generalisation claims |
| No verified labels; self-labelling bias | High | High | Two blind labellers, agreement score, labels made from raw plots not model output, optional controlled events |
| Unknown timestamp format / extra sentinel values break preprocessing | Medium | Medium | Verify in T2-002 first; loud failures; update config after EDA |
| Device/API differences (CSI missing, UNKNOWN mode) cause spurious flags | Medium | Medium | CSI excluded from model features; missing ≠ anomaly; per-device availability reported |
| Isolation Forest does not outperform the z-score baseline | Medium | Medium | That is a valid result — report it; do not tune on evaluation labels |
| Two-person merge conflicts and cross-dependencies stall work | Medium | Medium | Contracts first, fixtures for parallel work, small PRs, mutual review, owner swap rule if blocked >2 days |
| Over-claiming (universal detection, root cause, SA/NSA) | Medium | High | Non-Claims in README/dashboard/slides; hedged-language tests on agent text |
| Scope creep into LLMs/deep learning | Medium | Medium | M3 gated behind M2; LLM off by default (G13) |
| Streamlit theming/accessibility/testing limitations | Low | Low | Accept and document; manual checklist fallback |
| Raw data loss or accidental commit of data/secrets | Low–Medium | High | Manifest + verify, pre-commit block, `.gitignore`, shared private backup, secret scan |
| Local LLM too heavy for laptops | Medium | Low | Optional; check RAM first; template text default |

# ROADMAP — 5G-NADS (v1 complete · v2 real-time added)

> **v2 update (2026-10-09):** adds Milestones M5–M8 (todo_v2 Phases 10–15) for real-time streaming, alerting and optional edge inference. M0–M3 text below is unchanged v1 history; M4 is amended to show which items moved into v2. v2 effort figures come from `todo_v2.md` (planning estimates, not measurements); no calendar dates or deadline were provided.

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
| M5 | v2 Foundation & Streaming Core (contracts, ingest server, engine, live API) | 10–11 | 15.75 h | 19.25 h |
| M6 | v2 Clients, Live Dashboard & Alerts (Android streaming, edge *gated*, Live pages, alert engine) | 12–13 | 27.25 h | 18.50 h |
| M7 | v2 Hardening, Evaluation & Release (`v2.0.0`) | 14 | 9.75 h | 11.75 h |
| M8 | v2 Extras & Research Notes (optional) | 15 | 2.50 h | 3.25 h |
| **v2 MVP total (M5–M7)** | | 10–14 | **52.75 h** | **49.50 h** |
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
  - [x] `pip install -r requirements-dev.txt`, `make lint test` work on both machines and CI is green.
  - [x] Contracts C1–C6 and `ml/config.py` / `ml/schema.py` / `agents/contracts.py` merged.
  - [x] ≥200 samples per scenario (A/B/C) for Redmi and Samsung in `data/raw/`, manifest committed and `--verify` passes.
  - [x] `data/sample/` (real) and `tests/fixtures/edge_cases_synthetic.csv` (labelled synthetic) exist.
  - [x] Timestamp format and sentinel behaviour documented in `data/README.md`.

### Milestone 1 — MVP Core
- **Objective:** Raw CSV → scored, classified, agent-explained events, produced by code and verified by tests on the sample.
- **Features (Must Have only):** preprocessing (validation, timestamps, NA/sentinels → missing, range flags, sessions, missing-value policy, CLI), EDA and findings doc, feature engineering (deltas, change flags, rolling stats, persistence), rolling z-score baseline, Isolation Forest (train + score), classification (6 categories + precedence), severity, event grouping, five agents + deterministic text renderer, `events_diagnosed.json`.
- **Dependencies:** M0 (contracts, fixtures, at least Redmi + Samsung stationary data). EDA (T3-012) gates threshold-dependent tasks in Phase 4.
- **Estimated Complexity:** High (most of the intellectual work; the critical path of ~21 sequential hours runs through here and into evaluation).
- **Acceptance Criteria:**
  - [x] Preprocessing is idempotent (identical output hash on two runs) and never writes into `data/raw/`.
  - [x] `scores.csv` (C4) and `events_diagnosed.json` (C5) generated from `data/sample/`.
  - [x] Negative cases pass: low RSRP alone, low SINR alone, PCI/NCI change alone, 5G→LTE alone, UNKNOWN alone → **not anomalies**.
  - [x] Network Agent never outputs SA for UNKNOWN; agent modules do not import scikit-learn.
  - [x] `docs/eda_findings.md` answers PRD Open Questions 1–4 or states why they remain open.

### Milestone 2 — MVP Complete & Polish
- **Objective:** A demonstrable, tested, evaluated, documented system and a tagged release.
- **Features (Must Have remainder + Should Have):** Streamlit dashboard (six screens, states, filters, upload validation), end-to-end pipeline CLI, unit/integration/e2e/security tests, guardrail audit (G1–G16), two-labeller evaluation set with agreement, evaluate.py, baseline vs Isolation Forest comparison with detection latency, device/operator analysis, false-positive investigation, severity validation, README, architecture/dataset/methodology/agent/testing/limitations docs, presentation material, fresh-clone verification, Definition-of-Done audit, `v1.0.0`.
- **Dependencies:** M1 (scores and events), labelled data from both people, dashboard needs `scores.csv`.
- **Estimated Complexity:** Medium–High (evaluation with tiny, self-labelled data needs careful honesty).
- **Acceptance Criteria:**
  - [x] `make setup demo` works from a fresh clone on both teammates' machines.
  - [x] End-to-end pipeline CLI (T7-001), full integration test (T7-007), and security/privacy checks (T7-009) implemented and passing.
  - [x] Labelling guidelines (T7-011) and evaluation labels for labeller 1 (T7-012) created.
  - [x] Coverage ≥80% on `ml/` and `agents/` *(proposed target)*; all guardrails G1–G16 mapped to a test or documented check.
  - [x] `docs/results.md` reports precision/recall/F1/FPR/detection rate/latency for **both** baseline and IF on the same labels, with label counts; states plainly if IF does not beat the baseline.
  - [x] False positives investigated in `docs/false_positive_analysis.md`.
  - [x] README, dashboard About page and slides contain the Non-Claims (overview §53).
  - [x] Overview §58 Definition of Done audited with evidence links in `docs/definition_of_done.md`; `v1.0.0` ready.

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
  - [x] Pipeline outputs are byte-identical with LLM on vs off.
  - [x] Every supplementary result is labelled with its data source and scope.
  - [x] No new claim exceeds the evidence.

### Milestone 4 — Scale & Optimise (future; not scheduled)
> **v2 amendment:** four items listed below moved into scheduled v2 work — *live streaming from the phone to the dashboard* (M5–M6), *edge inference* (M6, **gated** by a go/no-go spike), *automated alerting* (M6) — and the *iOS collector* and *O-RAN integration* are **not** built in v2 (research notes only, M8). Everything else in this list remains unscheduled. Do not claim any of it as implemented until `todo_v2.md` tasks are ✅ with passing tests.
- **Objective:** Directions the overview lists as future scope (§55). **Do not claim any of these as implemented.**
- **Features:** larger multi-device/operator/location dataset; mobility-aware detection; supervised classification once enough labels exist; LSTM/Transformer time-series models (only if data size justifies); edge inference; federated learning; O-RAN integration; network-side KPIs and 5G core metrics; automated alerting; live streaming from the phone to the dashboard; richer visualisation; integration with operator systems; iOS collector.
- **Dependencies:** M2/M3 results; substantially more labelled data.
- **Estimated Complexity:** High.
- **Acceptance Criteria:** defined per feature when (and if) one is adopted.

---

---

# v2 — Real-Time Extension (Milestones M5–M8)

> Inputs: `PRD_v2.md`, `DESIGN_v2.md`, `TECH_RULES_v2.md`, `todo_v2.md` (Phases 10–15). Starts only after v1 M2 is accepted (it is: M0–M2 criteria are ticked above).
> **Gate before any work:** `T10-001` — amend `project-overview.md` (A1–A3) with both authors' approval. v2 contradicts three v1 statements; do not work around them silently.
> **Principle:** the live path must equal the batch path (G17). A stream–batch parity test is the first thing to pass in M5 and the last thing to break in M7.

## Milestone 5 — v2 Foundation & Streaming Core
- **Objective:** A phone-independent live path: replay a CSV through a local server and get the same scores, events and agent diagnoses as batch, via a live API.
- **Tasks/Features:** overview amendments and decision log; contracts C7–C9 with golden examples and drift check; guardrail test stubs G17–G26; config constants; CI/secret-scan updates; `streaming/` package (session buffer, shared-code coercion, engine, event tracker with PROVISIONAL/FINAL, agent invocation unchanged, live capture store); FastAPI ingest WebSocket with auth, acks, resume, rate limits; live API (WebSocket + REST); replay tool; latency/stream-quality metrics; stale/skew handling; link check on both phones (todo Phases 10–11).
- **Dependencies:** v1 accepted; both authors' approval of contracts; model metadata gains `model_version`/`feature_hash` (T10-013).
- **Estimated Complexity:** Medium–High (parity and idempotent ingest are the hard parts, not the framework code).
- **Acceptance Criteria:**
  - [ ] Overview amendments A1–A3 merged and `docs/decisions.md` extended (T10-001); v1 network-import check re-scoped to `ml/` and `agents/` (T10-014); sentinel per-column behaviour confirmed (T10-015).
  - [ ] C7–C9 schemas, golden examples committed; drift check green in CI.
  - [ ] **G17 parity test passes** on `data/sample/` and all synthetic fixtures (flags identical, scores within 1e-6).
  - [ ] Replay → server → live subscriber integration test passes; batch-on-capture equals live results.
  - [ ] Agents unchanged (`git diff` under `agents/` empty); ML flags identical with agents stubbed.
  - [ ] Non-loopback bind without a token refuses to start; wrong token rejected.
  - [ ] No claim of "implemented" in README for anything without a passing test (G16).

## Milestone 6 — v2 Clients, Live Dashboard & Alerts
- **Objective:** A real phone streams reliably, the Live dashboard shows honest connection/freshness state, and alerts fire rarely and only with rule evidence.
- **Tasks/Features:** Android streaming client (settings, WebSocket, persistent queue, reconnect/resume, foreground service, status strip, CSV-independence proof, phone notifications); streaming-perturbation experiment; real-device session; **optional edge inference** (spike → export → Kotlin scorer/features → golden-vector parity → advisory UI, all dropped cleanly on no-go); alert policy, cooldown/escalation, dispatcher, in-app / webhook / email / phone channels, acknowledgement; policy replay evaluation; Live dashboard (mode switch + connection chip, Overview, Signals, Cells & Network, Events & Alerts, Stream Health, About update, accessibility, smoke tests) (todo Phases 12–13).
- **Dependencies:** M5 (ingest, live API, replay tool); alert policy needs the event tracker; Android needs ingest protocol (T11-011). The Android track and the dashboard/alerting track run in parallel.
- **Estimated Complexity:** High (Android background limits and OEM behaviour are device-specific; Streamlit live refresh needs verification).
- **Acceptance Criteria:**
  - [ ] 20-min real-phone session: phone CSV and live capture match except documented drops (T12-010).
  - [ ] Killing the server mid-session leaves a complete phone CSV (G18).
  - [ ] Alert policy negative cases pass (ML-only, low RSRP/SINR alone, UNKNOWN alone, cell/network change alone → no alert) (G21).
  - [ ] Every Live page shows connection chip and sample age; all six connection states testable with mocked state; provisional vs final visibly different.
  - [ ] No Live chart interpolates across gaps or NA.
  - [ ] Edge inference: **either** golden-vector parity passes **or** it is recorded as no-go with reasons; never shipped with a loosened tolerance (G25).
  - [ ] `docs/streaming_perturbation.md` states honestly what the data does and does not show.

## Milestone 7 — v2 Hardening, Evaluation & Release
- **Objective:** Measured, attacked, documented, tagged.
- **Tasks/Features:** auth/abuse/fuzz tests; bind-policy tests; security and privacy audits; guardrail tests G17–G26 implemented; soak (2 h at 1× and 20×); latency benchmark; recovery matrix; live-vs-batch equivalence on real data; streaming detection-latency evaluation (baseline vs IF); alert precision/volume evaluation; protocol and architecture docs; README live quickstart; limitations update; `docs/results_v2.md`; v2 Definition-of-Done audit; fresh-clone check; slides/demo script with replay fallback; tag `v2.0.0` (todo Phase 14).
- **Dependencies:** M6 (real sessions, alert engine, Live pages).
- **Estimated Complexity:** Medium (mostly measurement and honesty).
- **Acceptance Criteria:**
  - [ ] G17–G26 each mapped to an automated test or a documented manual check.
  - [ ] `docs/results_v2.md` reports setups, counts and caveats for latency, soak, alert quality and detection latency; states plainly any KPI that was missed, and whether IF beats the baseline in the streaming setting.
  - [ ] No document claims guaranteed latency or "real-time" without the no-guarantee wording (G24).
  - [ ] Non-claims (PRD_v2 list) appear in README, dashboard About page and slides.
  - [ ] `docs/definition_of_done_v2.md` has an evidence link or an explicit ❌ for every Must Have; both authors sign off.
  - [ ] `make setup demo-live` works from a fresh clone on both machines; `v2.0.0` tagged.

## Milestone 8 — v2 Extras & Research Notes (optional; after `v2.0.0`)
- **Objective:** Optional refinements and honest documentation of what was *not* built.
- **Features:** HTTP batch-ingest fallback; separate ingest/view tokens; test that the optional LLM has no effect on the live path; O-RAN feasibility note and refreshed iOS note (**no code**) (todo Phase 15).
- **Dependencies:** M7 accepted.
- **Estimated Complexity:** Low–Medium.
- **Acceptance Criteria:**
  - [ ] Research notes say **NOT IMPLEMENTED** and cite verified sources or mark statements unverified.
  - [ ] Any new capability has tests before it is marked ✅.

## v2 Critical Path
Longest dependency chain to the v2.0.0 tag (T14-019) is about **18.5 h** (1,110 min) of sequential work: amendments (45m) → config (45m) → C7 schema (60m) → session buffer (60m) → sessionisation (45m) → engine (90m) → event tracker (60m) → agents (60m) → live API (60m) → live client (60m) → mode switch/chip (60m) → Stream Health (45m) → latency benchmark (60m) → results doc (45m) → DoD audit (45m) → tag T14-019 (30m). Real elapsed time will be longer (reviews, phone logistics).

## v2 Effort Notes
- MVP (M5–M7): Yashwant 52.75 h, Sushil 49.5 h, including 9.25 h / 0.75 h of **optional edge inference**. If edge is a no-go, totals become 43.5 h / 48.75 h and ~2.5 h of Phase 14 work should move from Sushil to Yashwant.
- These are task-sum estimates in the same style as v1 (38.8 h / 40.2 h); v1 actuals were not provided, so I cannot calibrate v2 against them. Treat v2 as likely *less* certain than v1 because of Android device behaviour and Streamlit live-refresh uncertainty.

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
| **v2:** Stream path diverges from batch results | Medium | High | One implementation (`ml/*` reused); G17 parity test in CI |
| **v2:** Android OEM background limits stop streaming/logging | High | Medium | Foreground service, per-device manual tests, documented behaviour, replay fallback for demos |
| **v2:** Streaming perturbs the measured radio | Medium (unverified hypothesis) | Medium | Prefer USB/Wi-Fi link; experiment T12-009; no cellular streaming |
| **v2:** Alert fatigue from high false-positive rate of global IF threshold | High | High | Evidence-gated policy, persistence/severity gates, cooldown, ML-only never alerts |
| **v2:** Streamlit cannot meet live-latency KPI | Medium | Medium | REST-polling fallback; revisit front end only if T14-008 fails |
| **v2:** Edge Isolation Forest parity unreachable | Medium | Low | Time-boxed spike; clean no-go; nothing depends on it |
| **v2:** Ingest endpoint exposed on LAN | Medium | High | Loopback default; token + limits; abuse tests; optional TLS docs |
| **v2:** Over-claiming "real-time" or implementing O-RAN/iOS/SMS | Medium | High | G24, non-claims, scope table; research notes only |

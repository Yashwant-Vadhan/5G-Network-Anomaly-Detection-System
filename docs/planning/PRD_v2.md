# PRD v2 — 5G-NADS Real-Time Monitoring (Streaming, Edge Inference, Alerting)

> **Builds on:** `docs/planning/PRD.md` (v1, MVP — unchanged unless this document says otherwise).
> **Raw material:** `limitations_and_future_scope.md` §2.2–§2.4 and `project-overview.md` §55.
> **Source-of-truth rule (inherited from v1):** if this PRD and `project-overview.md` disagree, the overview wins. **v2 deliberately conflicts with parts of the overview** (see *Required Amendments to project-overview.md*). Those amendments must be approved by both authors and merged *before* any Phase 11+ task starts (todo_v2 `T10-001`).
> **Status legend:** ✅ implemented · 🔄 in progress · ⬜ not started · ⚠️ UNCLEAR = needs a decision
> **Honesty note:** every number marked *(proposed)* is a planning target chosen by the authors of this plan, not a measurement. Figures quoted from v1 (dataset size, false-positive rate) are taken from `limitations_and_future_scope.md`; I have not seen `docs/results.md`, so **verify them there before reusing them**.

---

## Executive Summary

| Item | Value |
|---|---|
| **Project name** | 5G-NADS v2 — real-time extension of the 5G Network Anomaly Detection and Intelligent Diagnosis System |
| **Problem statement** | v1 is a *batch/replay* system: a CSV is collected, copied to a laptop, processed, and replayed in the dashboard. A tester walking through a handover cannot see, while it happens, that their radio quality is degrading or what kind of event it is. `limitations_and_future_scope.md` §2.2–§2.4 lists live streaming, on-device inference, and alerting as unimplemented. |
| **Solution overview** | The Android collector additionally **streams each ~3 s measurement** over a WebSocket to a local Python server. The server runs the **same** preprocessing/feature/scoring code as v1 incrementally, tracks events as they open and close, runs the unchanged five deterministic agents, and pushes results to a **live dashboard** and to an **alert engine** (in-app, phone notification, webhook, email). An **optional, gated** on-device Isolation Forest scorer gives an advisory score on the phone. |
| **Target audience** | Same as v1 (the two authors, evaluators, technically curious testers) plus a *live-demo presenter*. Still a research prototype, **not** operator-grade monitoring. |
| **Platform** | Android collector (Kotlin) + Python server (FastAPI/WebSocket) + React SPA dashboard (Vite + TypeScript). Supported across static hosted, containerized hosted, and local network modes; v1 Streamlit frozen for replay baseline. |

**Core v2 objective:** reduce the delay between "radio behaviour happens" and "user sees an evidence-backed, hedged explanation" from *minutes–hours (manual CSV copy)* to *seconds*, **without** weakening any v1 guardrail (no fabricated values, `UNKNOWN` ≠ SA, correlation ≠ causation, ML decides before agents explain).

**Non-negotiable invariant:** the live path and the batch path must produce the **same** scores and flags for the same samples (stream–batch parity, guardrail G17). If they diverge, the live path is wrong.

---

## Scope Decisions (from `limitations_and_future_scope.md` §2.2–§2.4)

| Source item | v2 decision | Reason |
|---|---|---|
| §2.2 Real-time WebSocket streaming | **In scope — Must Have** | Core of v2. |
| §2.2 On-device edge inference | **In scope — Should Have, gated** by a go/no-go spike (`T12-011`) and a parity test | Needs Isolation Forest to be re-implemented or exported for Android; may fail parity. Drop cleanly if it does. |
| §2.3 Automated alerting | **In scope — Must Have for in-app; Should Have for phone/webhook/email** | Alert policy must account for v1's high false-positive rate (below). |
| §2.3 SMS alerts | **Out of scope (non-goal)** | Needs a paid third-party provider and would send data off-device. Webhook covers the use case. |
| §2.3 O-RAN / Near-RT RIC integration | **Out of scope for code; research note only (Nice To Have)** | Requires operator-side access the project does not have. Must not be claimed. |
| §2.4 iOS collector | **Out of scope for code; refresh the existing research note (Nice To Have)** | Documented iOS `CoreTelephony` restrictions in `docs/ios_collection_note.md`. |
| §2.1 Mobility-aware / supervised / LSTM | **Not in v2** | Not named in the request; stays in Future Scope. |

> ⚠️ UNCLEAR: the request named §2.2–§2.4. If you also want §2.1 (mobility-aware detection), it needs a separate PRD section and more labelled data than v1 has.

---

> **Research Prototype Notice:** 5G-NADS is an academic research prototype and educational demonstration system for UE-side 5G NR telemetry anomaly exploration, NOT a real-world, commercial, or carrier-grade network fault detector.

---

## Required Amendments to `project-overview.md`

v2/v2.1 contradicts statements in v1. Do **not** silently work around them; amend the overview first (`T10-001`).

| # | v1 statement | Conflict | Proposed amendment |
|---|---|---|---|
| A1 | Overview §9 / PRD v1 "Hard boundary": the Android app does **not** run ML. Guardrail G1: collector ≠ ML pipeline. | Optional edge inference puts a scorer on the phone. | Keep the **measurement/CSV path ML-free**. Edge scoring lives in a **separate Gradle module** (`edge-inference`), is **off by default**, is **advisory only**, and never alters what is logged. G1 is reworded accordingly (see TECH_RULES_v2). |
| A2 | Overview §53 non-claim: "real-time operator-network control". PRD v1 lists "live streaming" as a future enhancement. | v2 adds real-time *monitoring*. | Keep "no operator-network control". Add: "near-real-time *monitoring and alerting of UE-side measurements*, with no latency guarantee". |
| A3 | PRD v1 Security and `docs/decisions.md` entry (6): "Authentication, rate limiting and HTTPS are N/A by design (local single-user tool)." Also v1 `T7-009`'s "no network calls in the core pipeline" check. | The phone must connect to a server over a network, so an ingest endpoint is now reachable by other devices; and `streaming/` legitimately imports a web framework. | Authentication, message/rate limits and optional TLS become **required** for any non-loopback binding; amend decisions entry (6) and `docs/testing.md`; re-scope the network-import check to `ml/` and `agents/` only (`T10-014`). |
| A4 | Overview names Streamlit as the dashboard. | v2.1 frontend is React SPA. | v1 dashboard = Streamlit (frozen benchmark result, maintained for bug fixes only). v2 dashboard = React single-page app (Vite + TypeScript) deployable to static hosts or paired to live server. |
| A5 | "Local single-user tool"; local-first. | Target product allows web service pairing. | v2 may run as a **hosted web service** where a user pairs their own phone. Public hosting is permitted **only** with: user consent (G28), ephemeral memory-only sessions (G29), per-session tokens (C10), and cell-ID protection in logs. |
| A6 | A3 (v2) specified one shared pairing token. | Multi-user / hosted web pairing. | Replaced by **per-session ingest and viewer tokens** (Contract C10) generated via ephemeral pairing codes/QRs. |

---

## Goals & Objectives

### Business / Project Goals
1. Deliver a working **phone → server → dashboard** live path demonstrable in a viva, with a **replay fallback** that needs no phone.
2. Preserve v1's scientific honesty: live results are validated against batch results, latency is **measured and reported, not promised**, and alert quality is evaluated on labelled data.
3. Keep the deterministic agent layer **unchanged** (`agent_architecture.md`, contract C6 stays as is).
4. Document unimplemented items (O-RAN, iOS, SMS) as *not implemented*.

### User Goals
- **Tester (P3):** see the current state and a plain-language, hedged explanation within seconds of an event, and get a phone/in-app alert only when something persistent and evidence-backed happens.
- **Researcher (P1):** capture live sessions as C1 CSVs that feed the existing batch pipeline unchanged.
- **Reviewer (P2):** see connection state, data freshness, provisional-vs-final events, and the limitations at all times.
- **Presenter (P5):** run a convincing live demo, or replay a recorded session at speed if the network misbehaves.

### Success Metrics (KPIs)

All targets are *(proposed)* unless noted; revise after the first measurement.

| KPI | Target |
|---|---|
| **Stream–batch parity** | For every fixture and the sample dataset: `baseline_flag`, `if_flag`, `anomaly_type`, `severity` identical; `if_score` and `baseline_z_max` within 1e-6. **100%** (hard requirement, G17). |
| **Sample-to-dashboard latency** | p95 < 2 s from server receipt to dashboard-visible on a laptop over LAN/loopback, replay at 1×. *Measured per run and reported; not a product promise.* |
| **No silent loss** | In a 10-minute test with ≥3 forced disconnects (Wi-Fi off/on, server restart), 100% of samples either arrive (with original timestamps) or are counted as lost in the stream-health page. |
| **Alert volume on normal data** | ≤ 1 alert per 30 min on stationary-normal replay data. Threshold set on v1 non-evaluation data, **not** tuned on evaluation labels. |
| **Alert quality** | Report precision and recall of alerts against the v1 labelled events (counts shown). No pre-committed target — report honestly. |
| **Detection latency (stream)** | Report samples/seconds from event start to first alert and to first provisional event, for baseline and IF, on replayed labelled data. |
| **Edge parity (only if edge is built)** | On-device vs Python `if_score`: absolute difference ≤ 1e-6 on golden vectors (double precision) *(proposed)*; otherwise edge is dropped, not shipped. |
| **Soak** | 2 h continuous replay: no crash, bounded memory (no monotonic growth beyond configured buffers). |
| **Test coverage** | ≥80% on `ml/`, `agents/`, and new `streaming/` *(proposed, same gate as v1)*. |
| **Guardrails** | G1–G16 (v1, G1 amended) + G17–G26 (new) each mapped to a test or documented check: 100%. |

### Context the targets must respect (from v1, verify in `docs/results.md`)
- `limitations_and_future_scope.md` §1.1: **5,532 raw samples** (3,760 raw / 3,756 valid Redmi 13 5G [4 dropped per `preprocess_log.json`], 1,772 Samsung), single operator (Airtel, NSA). `docs/eda_findings.md` lists 3,756 Redmi samples (153 sessions) and 1,772 Samsung (3 sessions).
- §1.4: Isolation Forest at the global threshold `0.60` has a high false-positive rate (**73.55%** in `docs/results.md` and `limitations_and_future_scope.md`) on normal mobility variance. Consequence for v2: **an alert must never fire on a raw IF flag**. See FR-17.

---

## User Personas

Personas P1–P4 are unchanged from PRD v1. New/updated:

### P3 — Field Tester (updated)
- **Pain points:** wants to know *now* whether a drop is a handover or a real problem; does not want a phone that buzzes every few minutes.
- **Goals:** live status, rare and trustworthy alerts, one-line recommendation.

### P5 — Live-Demo Presenter (new)
- **Description:** One of the two authors demonstrating to faculty.
- **Pain points:** venue Wi-Fi, phone sleeping, server not reachable, 5 minutes to show value.
- **Goals:** one-command start, visible connection health, instant fallback to recorded-session replay, no embarrassing crashes.

---

## User Stories

### Live Streaming
- As a tester, I want the app to stream each measurement to my laptop as it is logged so that I can watch the radio state live.
- As a tester, I want the app to keep logging to CSV even when streaming fails so that no data is lost.
- As a researcher, I want samples buffered on the phone while disconnected and re-sent with their original timestamps so that the live dataset has no silent gaps.
- As a researcher, I want every live session saved as a C1-format CSV so that I can run the v1 batch pipeline on it.
- As a presenter, I want to replay a recorded CSV through the same live path at 1×–20× so that I can demo without a phone.

### Real-Time Analysis
- As a reviewer, I want live scores to equal batch scores for the same data so that I can trust the live path.
- As a tester, I want an event to appear as *provisional* while it is developing and become *final* when it ends so that I'm not shown a premature diagnosis as settled.
- As a reviewer, I want `UNKNOWN` deployment mode and `NA` values to behave exactly as in v1 so that live data is never "cleaned up" with invented values.

### Alerting
- As a tester, I want an alert only for events with rule-based evidence and sufficient persistence/severity so that ML-only noise does not wake me.
- As a tester, I want repeated alerts for the same event suppressed (cooldown) but an escalation if severity rises.
- As a tester, I want a phone notification, and as a researcher I want an optional webhook/email, so that I'm informed while away from the dashboard.
- As a reviewer, I want every alert logged with its evidence so that I can audit false alarms.

### Edge Inference (optional)
- As a tester, I want an advisory on-device score so that the phone can show *something* when the laptop is unreachable.
- As a reviewer, I want the phone score to be clearly labelled advisory and checked against the server score so that it can never contradict the authoritative result silently.

### Live Dashboard
- As a tester, I want a connection indicator (LIVE / STALE / DISCONNECTED) and "last sample N s ago" so that I never mistake old data for current data.
- As a tester, I want live charts with anomaly markers and a stream-health page so that I can see latency, gaps and queue depth.
- As a public visitor, I want a zero-backend Static Demo running from an anonymised bundle on GitHub Pages/Vercel (Mode 1) so I can explore the system immediately.

### Hosted Pairing & Privacy
- As a phone user, I want to pair my phone to the web service using an ephemeral 8-character pairing code or QR code (Contract C10) without entering long credentials or configuring servers.
- As a phone user, I want an explicit consent screen detailing exactly what telemetry is transmitted and what is excluded (no GPS/PII) before streaming can be activated (G28).
- As a user, I want live sessions to be ephemeral and held only in memory, automatically deleted when I disconnect (G29).
- As a public visitor, I want demo bundles to hash cellular identifiers (PCI/NCI) by default so private cell tower locations are protected (G27).

### Platform & Security
- As an author, I want the ingest endpoint to reject unauthenticated or malformed clients so that exposing it on a LAN or cloud does not expose the host.
- As an author, I want secrets (tokens, SMTP, webhook URL) only in environment variables.

---

## Functional Requirements

Numbering continues from PRD v1 (FR-1 … FR-11 remain in force).

### FR-12 — Android Streaming Client ⬜
- **Description:** In the existing collector app, a `StreamClient` sends each logged measurement to the server over a WebSocket, independent of CSV logging.
- **Inputs:** the same measurement object that is written to CSV; settings: host, port, pairing token, stream on/off.
- **Outputs:** JSON `sample` messages (contract C7); local unacked-sample queue; connection status in UI.
- **User actions:** enter host/port/token once; toggle streaming; see status (Connected / Reconnecting / Off), queue depth, last ack.
- **Validation rules:** CSV logging path is unchanged and never blocked by streaming (G18); missing values are sent as JSON `null` (never `0`); every Android sentinel (v1 `SENTINEL_INTS`: `2147483647`, `-1`, `99`, `999`) and the `NA` token are sent **as-is** and converted server-side by the shared v1 preprocessing code (single source of truth, G3); the timestamp is sent as the exact string the collector writes to CSV; token stored in encrypted preferences, never logged.
- **Edge cases:** server unreachable at start; Wi-Fi switches; app backgrounded or killed by OEM battery management (⚠️ UNCLEAR: Xiaomi/Redmi and some Samsung builds aggressively stop background apps — needs a foreground service and per-device testing); queue full (drop **oldest** unsent stream sample, count it, CSV still has it); phone clock changes; permission denied.

### FR-13 — Ingestion Server ⬜
- **Description:** `streaming/server.py` (FastAPI) exposes `WS /api/v1/ingest` (phone → server) and `/healthz`.
- **Inputs:** C7 messages (`hello`, `sample`, `ping`, `bye`).
- **Outputs:** `hello_ack`, cumulative `ack`, `error`, `pong`; validated rows handed to the streaming engine; raw live CSV per session.
- **Validation rules:** bearer token required; `schema_version` must match; message size cap; per-client rate cap; `seq` strictly increasing per `(client_id, session)`; duplicates are acknowledged but not re-processed (idempotent); invalid sample → `error` with code, connection stays open for recoverable errors.
- **Edge cases:** reconnect with `resume_from_seq`; out-of-order seq; sample timestamps in the future/past (clock skew flagged, not "fixed"); second client with same `client_id`; client sends C1 `deployment_mode` outside `{NSA,SA,UNKNOWN}`.

### FR-14 — Streaming Analysis Engine ⬜
- **Description:** `streaming/engine.py` incrementally applies v1's pipeline per session: validate → coerce (`NA`/sentinel → missing) → sessionize → features → baseline z-score → Isolation Forest → classification/severity → event tracking → agents.
- **Design rule:** **no second implementation of any feature or rule.** The engine calls the same `ml/` functions as the batch pipeline over the session buffer, so parity holds by construction and is verified by test (G17).
- **Outputs:** `ScoredSample` (C4-compatible columns + latency timestamps), event open/update/close records, diagnosed events (C5-compatible, with a `status` of `PROVISIONAL` or `FINAL`).
- **Validation rules:** model and feature list pinned by `models/if_v1.meta.json`; rows with missing model features are `model_eligible=False`, never imputed; ML flag decided **before** agents run; agents run on event open/change/close, never mutate flags (G9); no network calls in the core path (G13).
- **Edge cases:** first samples of a session (warm-up, shorter than window); gap > `SESSION_GAP_SECONDS` starts a new session; session buffer cap reached (rollover to a new session, logged); event closes after `EVENT_CLOSE_GAP_SAMPLES` normal samples; classification of a provisional event changes as more samples arrive (e.g., becomes `PERSISTENT_POOR_QUALITY`).

### FR-15 — Live API ⬜
- **Description:** read-side API for the dashboard and tools: `WS /api/v1/live` (push) and REST (`/api/v1/sessions`, `…/samples?since_seq=`, `/events`, `/alerts`, `/model`, `/metrics`, pairing and ticket endpoints per C10).
- **Validation rules:** read endpoints are loopback-only unless `NADS_ALLOW_REMOTE_VIEW=true` or in hosted mode with origin allow-list; per-session tokens required; bounded per-subscriber queues (slow consumers lose oldest, are told so).
- **Edge cases:** dashboard starts before any session exists; server restart (dashboard must reconnect and re-sync via REST); thousands of samples requested at once (pagination cap).

### FR-16 — React Dashboard (Static Demo & Live Modes) ⬜
- **Description:** A modern React SPA (Vite + TypeScript) replaces Streamlit for all v2.1 interfaces across 3 deployment modes: (1) Static Demo on GitHub Pages/Vercel (precomputed C11 demo-bundle), (2) Local Live, and (3) Hosted Live with phone pairing. The v1 Streamlit dashboard is frozen as a historical v1 baseline. Details in `DESIGN_v2.md`.
- **Must show:** connection state, sample age, current metrics/network state, status banner, score (baseline and IF shown separately), provisional/final event with agent evidence, alerts, stream health, pairing modal.
- **Validation rules:** the frontend never computes scores, flags, transitions, or diagnoses (G30); stale data is labelled stale; `UNKNOWN` and `NA` display rules from v1 DESIGN apply unchanged; public bundles use hashed cell IDs (G27).
- **Edge cases:** no data yet; connection lost mid-event; multiple concurrent sessions (select one); browser refresh.

### FR-17 — Alert Engine ⬜
- **Description:** `streaming/alerts/` decides, de-duplicates and dispatches alerts.
- **Alert policy (proposed, thresholds in `ml/config.py`, tuned on non-evaluation data):**
  1. An alert requires an event whose `anomaly_type` is **not** `NORMAL`, `STATISTICAL_ONLY`, `CELL_TRANSITION` or `NETWORK_STATE_TRANSITION` **and** rule evidence from at least one agent. An ML-only flag (v1 labels it `STATISTICAL_ONLY`: "statistically unusual, no rule evidence") is shown on the dashboard but **never pushes an alert** (v1 copy rule: don't hide ML-only flags; v2 adds: don't page on them).
  2. Event must meet `ALERT_MIN_PERSISTENCE_SAMPLES` **or** `severity ≥ ALERT_MIN_SEVERITY`.
  3. A `CELL_TRANSITION` or `NETWORK_STATE_TRANSITION` alone never alerts (they are events, not anomalies — v1 G6).
  4. Cooldown per event and per type; escalation alert only if severity increases.
- **Channels:** `InApp` (default on), `PhoneNotification` (server → app message → Android local notification), `Webhook` (optional, HTTP POST, minimal payload), `Email` (optional, SMTP). All external channels **off by default**; a failing channel never blocks the pipeline or other channels.
- **Alert text:** same hedged copy rules as v1 ("possible … associated with …"). No "we fixed/re-routed".
- **Validation rules:** payload contains no raw dataset, no PII, no precise location; secrets only via env; every alert logged to `data/live/alerts.jsonl` (C9).
- **Edge cases:** burst of events; channel timeout; duplicate event IDs after reconnect; alert for an event later revised (send a `RESOLVED`/update, not a second "new" alert).

### FR-18 — Edge Inference (optional, gated) ⬜
- **Description:** separate Gradle module computes v1's feature set and Isolation Forest score on the phone from an exported model artefact; shown as **advisory**.
- **Gate:** `T12-011` spike decides export approach (custom tree-JSON traversal vs ONNX runtime) and a go/no-go. ⚠️ UNCLEAR: whether the Isolation Forest converts cleanly to ONNX with the pinned scikit-learn — **verify against current converter docs**, do not assume.
- **Validation rules:** golden-vector parity test (Python-generated vectors, Kotlin asserts); model artefact carries `model_version` and feature-order hash; phone refuses to score if hashes mismatch; the server score is authoritative and the server logs any divergence (`edge_divergence`).
- **Edge cases:** model file missing/corrupt; feature-order mismatch; first samples of a session; battery impact (measure and report, no target).

### FR-19 — Live Session Capture & Replay Tooling ⬜
- **Description:** server writes each live session as an append-only C1 CSV in `data/live/`; on session close it is finalised and hashed. `scripts/promote_live_session.py` copies it into `data/raw/` with the v1 naming convention and manifest entry. `scripts/replay_stream.py` replays any C1 CSV through the ingest path at 1×–N×.
- **Validation rules:** live files never overwrite `data/raw/` (G7); replayed data is labelled `replay` in session metadata and is not counted as new real data.
- **Edge cases:** crash mid-session (file left un-finalised → marked `INCOMPLETE`); disk full; replay of a file with timestamp gaps.

### FR-20 — Streaming Security ⬜
- **Description:** pairing token, bind-address policy, size/rate limits, optional TLS, privacy checks.
- **Rules:** default bind `127.0.0.1`; binding a non-loopback address requires an explicit flag **and** a non-empty token (server refuses to start otherwise); constant-time token comparison; `client_id` is a random UUID created at install (no IMEI, phone number, advertising ID, or MAC); logs never contain the token.
- **Edge cases:** token rotation; token in a screenshot/log; public Wi-Fi (documented as "use USB `adb reverse` or a private hotspot").

### FR-21 — Research Notes (Nice To Have) ⬜
- `docs/oran_feasibility_note.md` and a refreshed `docs/ios_collection_note.md`. **No code. No implementation claims.** Statements about third-party APIs/standards must be verified against current primary sources or marked unverified.

---

## Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Per-sample server processing is cheap at ~1 sample/3 s (a session buffer is at most `SESSION_MAX_ROWS`); target p95 end-to-end < 2 s *(proposed)*. Replay at 20× must not fall behind unboundedly (bounded queues, drop-oldest with a visible counter). |
| **Scalability** | One phone, one server, one or a few dashboard viewers. Multi-phone is allowed (sessions are keyed by `client_id`) but not load-tested. No distributed infrastructure. |
| **Security & Privacy** | See FR-20 and TECH_RULES_v2 §Security. No PII; data stays on the local network by default; webhook/email are explicit opt-ins that send **only** the minimal alert payload. |
| **Accessibility** | WCAG 2.1 AA target for the React SPA; alerts use text + icon + shape, not colour only; native ARIA live regions (`aria-live="polite"`). |
| **Reliability** | Idempotent ingest, bounded queues, explicit stale/disconnected states, graceful degradation: if the server is down the phone still logs CSV; if an alert channel fails the dashboard still works. |
| **Maintainability** | Same standards as v1 (type hints, `ruff`, Conventional Commits). Wire schemas live in one place (`streaming/schema.py`) with golden examples. |
| **Reproducibility** | Replay of a CSV through the live path is deterministic (same seed, same model) and compared to batch in CI. |
| **Honesty** | The About page, README and slides carry the v1 non-claims **plus** the v2 non-claims below. |

---

## Assumptions & Constraints

- Team of two; no paid infrastructure; no calendar deadline supplied, so milestones are ordered by dependency (see ROADMAP).
- Sampling remains ≈ 1 sample / 3 s.
- Phone and laptop can reach each other via Wi-Fi/hotspot or USB (`adb reverse`). ⚠️ UNCLEAR: which link the demo venue allows.
- **Measurement perturbation risk.** Streaming over the *cellular* connection would add data traffic on the very radio being measured and could change the readings or network state. v2 therefore **recommends Wi-Fi or USB for the stream** and includes an experiment (`T12-009`) to check whether streaming changes the distributions. This is a hypothesis to test, not an established effect.
- v1 facts relied on (from `docs/eda_findings.md`): `SESSION_GAP_SECONDS=30`, `DEFAULT_WINDOW=10` (so the first 10 samples of any session are warm-up with missing rolling features), 3 s sampling, `csi_*` excluded from model features, persistence thresholds `PERSIST_THRESHOLDS` (−110 dBm / −15 dB / 0 dB). v1 sessions are short (Redmi: 153 sessions over 3,756 samples, ~25 each); live sessions will usually be longer.
- The model is **pinned** (`if_v1`); v2 does no online learning or retraining.
- The server's clock is not trusted to equal the phone's: device timestamps order data; server timestamps measure latency; large skew is flagged, never "corrected".
- Python 3.11+, FastAPI/uvicorn and WebSocket library versions are design intent — **verify exact versions and APIs at implementation time**.
- Real data still has no verified labels beyond v1's two-labeller set; v2 reuses it and adds none unless time allows.

## Open Questions (⚠️ UNCLEAR — record answers in `docs/decisions.md`)

1. Approve amendments A1–A3 to `project-overview.md`?
2. Streaming link for the demo: venue Wi-Fi, laptop hotspot, or USB `adb reverse`?
3. Does a foreground service keep logging alive on the Redmi and the Samsung with screen off? (device-specific)
4. ~~Is Streamlit auto-refresh/fragment polling fast and stable enough for the latency KPI~~ — **resolved in v2.1:** Replaced with a React SPA (Vite + TS) consuming WebSocket events directly with native client-side state.
5. Edge inference: custom tree-JSON vs ONNX — result of spike `T12-011`.
6. Which alert channels does the team actually want ON in the demo? (Proposal: in-app + phone notification; webhook/email optional.)
7. ~~Timestamp format of live samples~~ — **resolved by v1 EDA (Open Question 1):** `dd-MM-yy HH:mm:ss` in device-local time with no offset (ISO-8601 also seen). The app sends the collector's exact CSV string; the separate `sent_at` field (ISO-8601 **with** offset) is used for latency and skew, because the CSV timestamp has no timezone.
8. v1 sentinel list `[2147483647, -1, 99, 999]`: confirm each sentinel is applied only to the columns where it is truly a sentinel (`-1`/`99` can be legitimate dB values) — todo_v2 `T10-015`. The live path inherits whatever batch does (G17).

---

## MVP Scope (v2)

### Must Have
1. Amended overview + contracts C7–C9 + guardrails G17–G26.
2. Android streaming client with offline queue and reconnect/resume.
3. Ingestion server (auth, validation, idempotent ack) and streaming engine with **stream–batch parity test passing**.
4. Event tracking with provisional/final status; agents unchanged.
5. Live API and Live dashboard mode (connection state, live charts, events, stream health).
6. In-app alerting with the evidence-gated policy, cooldown, and alert log.
7. Live session capture + replay tool.
8. Security controls (token, bind policy, limits) and tests.
9. Latency, soak and recovery tests; alert evaluation; updated docs; `v2.0.0`.

### Should Have
- Phone notification channel; webhook channel; email channel.
- Edge inference (only if the spike passes and parity holds).
- Measurement-perturbation experiment write-up.
- Optional TLS (`wss`) documentation/config.
- Stream-health page with latency percentiles.

### Nice To Have
- O-RAN feasibility note; iOS note refresh.
- Alert acknowledgement history analytics.
- Demo script and screen-recorded fallback.

## Future Enhancements (must **not** be claimed as implemented)
Mobility-aware detection (§2.1) · supervised/LSTM/Transformer models · SMS alerting · multi-user hosted deployment · cloud streaming · O-RAN/Near-RT RIC integration (needs operator access) · iOS collector · federated learning · network-side KPIs · online learning/auto-retraining.

---

## Explicit Non-Claims (v1 list, amended, plus v2 additions)

Must appear in README, the dashboard About page, and slides.

1. Not universal 5G anomaly detection.
2. No guaranteed root cause (correlation ≠ causation).
3. No guaranteed SA/NSA identification; `UNKNOWN` stays `UNKNOWN`.
4. No operator-network control. Alerts inform the *user*; the system changes nothing in the network.
5. No universal thresholds.
6. Not every cell transition is an anomaly.
7. **Amended:** the Android *measurement path* performs no ML. Optional on-device scoring, if built, is a separate, advisory module; the server result is authoritative.
8. **New:** "Real-time" means near-real-time monitoring of **UE-side** measurements with **no latency guarantee**; reported latencies are measurements from specific test setups.
9. **New:** Alerts are **not** outage notifications and not a safety or emergency-communication system.
10. **New:** The system has no visibility into the operator's RAN or core; it cannot tell whether an anomaly is a network fault.
11. **New:** Live results are provisional until an event closes.
12. **New:** O-RAN integration, iOS collection, and SMS alerting are **not implemented**.
13. **New:** 5G-NADS is an exploratory academic research prototype, **not** a real-world, commercial, or operational network detector.

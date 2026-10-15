# todo_v2.md — 5G-NADS Real-Time Extension (v2)
> Generated from: `PRD_v2.md` · `DESIGN_v2.md` · `TECH_RULES_v2.md` · `ROADMAP.md` (updated) in `docs/planning/`, the v1 `todo.md` and `docs/eda_findings.md`, and the source-of-truth `project-overview.md`
> Continues v1 numbering (Phases 1–9, all ✅); v2 starts at **Phase 10**. Target: MVP-first execution by the same **two developers** and their AI coding agents.
> Last Updated: 2026-10-09 · No calendar dates or deadline were provided; effort figures are planning estimates, not measurements.

---

## 0. How to use this file

### Team and ownership (same people, same module ownership as v1)
| Person | GitHub branch prefix | Owns in v2 |
|---|---|---|
| **Yashwant Vadhan M** | `feat/yashwant/…` | Android streaming client and the optional edge-inference module (he owns the collector), model metadata/export (he owns training), replay tool, v1-sidebar changes, parity/soak/real-device tests, CI/DevOps, protocol/security docs |
| **M A Sushil Kumar** | `feat/sushil/…` | Wire contracts C7–C9 (he owns schema/contracts), ingest and live API servers, event tracker (he owns event grouping), agent invocation (he owns the orchestrator), alert policy and channels, most Live dashboard pages, abuse/recovery/latency tests, architecture docs |

The split follows who owns the underlying v1 code, so there is still one owner per function. Cross-dependencies are kept safe by **contracts C1–C9** — code against the contract and golden fixtures, not against the other person's unfinished code.

### Status markers (same as v1)
`⬜` not started · `🔄` in progress (put your name in the PR title) · `✅` done and merged with tests · `⛔` blocked **or dropped** (write why under the task; a dropped task says `dropped: <reason>`).
Tags: `🧑 Human-only` (needs a phone/human judgement — AI agents must skip these) · `➕ Optional` (not required for the v2 MVP; edge-inference tasks are *gated* by T12-011) · `⚠️ UNCLEAR` (ambiguity — ask the human, record the answer in `docs/decisions.md` or `docs/eda_findings.md`).

### Already done before this file
- ✅ v1 MVP, Phases 1–9 (`todo.md`), including the Android collector, the batch pipeline, six agents-layer modules, the six-screen Replay dashboard, evaluation, docs, and the optional Ollama explainer (T9-001/T9-002).
- Facts from `docs/eda_findings.md` this plan now relies on: timestamps are `dd-MM-yy HH:mm:ss` (device-local, no offset) or ISO-8601; `SENTINEL_INTS = [2147483647, -1, 99, 999]`; `SESSION_GAP_SECONDS = 30`; `DEFAULT_WINDOW = 10`; `RANDOM_STATE = 42`; `csi_*` are not model features; `PERSIST_THRESHOLDS` = −110 dBm RSRP, −15 dB RSRQ, 0 dB SINR.

### Protocol for AI coding agents (v1 protocol + v2 additions)
1. Read `project-overview.md` (source of truth, **including the v2 amendments once T10-001 is merged**) and the Guardrails tables in `TECH_RULES.md` (G1–G16) and `TECH_RULES_v2.md` (G1′, G17–G26). If anything conflicts, the overview wins.
2. Pick **one** task: the first `⬜` task in ID order whose **Dependencies are all ✅**, belonging to the **Owner you are assisting**. Skip `🧑 Human-only` and `➕ Optional` tasks unless told otherwise.
3. Do only what the task says; touch only the files it names (plus tests). Do not refactor other modules. **Do not change anything under `agents/` (v2 leaves it unchanged) and do not change v1 batch behaviour** — if a task needs a v1 helper extracted, the batch output must stay byte-identical on `data/sample/`.
4. Write the tests listed in the task. Run `make lint test`. Do not mark ✅ until tests pass (G16).
5. Never fabricate or interpolate measurements; never impute missing radio values; never treat `NA` as 0; never infer SA from `UNKNOWN`; never alert on an ML-only (`STATISTICAL_ONLY`) flag, a weak signal alone, or a PCI/NCI/network change alone; never use synthetic or replayed data as new real data; never add an LLM to the live decision path; never log a token or webhook URL.
6. Function names below come from the v1 todo/EDA docs. **Confirm the exact names and signatures in the repo** before coding; if they differ, fix the task text in the same PR.
7. If you find an ambiguity or a `⚠️ UNCLEAR`, **stop and ask the human**.
8. Commit as `type(T##-###): message`, branch `feat/<owner>/T##-###-slug`, open a PR, have the *other* teammate review (contract PRs need both).
9. When done: change the task's status to ✅ and tick its acceptance boxes in the same PR.

### Task format
Each task: **Status · Description · Dependencies · Acceptance Criteria (checkboxes) · Estimated Effort · Assigned To (role) · Owner (person)**. Effort is 15–90 minutes of focused work.

---



## Phase 10: v2 Foundation & Contracts
*Goal: Approved scope, contracts C7–C9, guardrail test stubs, config and CI ready so both people can work in parallel.*

#### T10-001: Amend project-overview.md and extend docs/decisions.md
**Status:** ✅
**Description:** Add a 'v2 amendments' section to `project-overview.md` covering A1 (optional isolated edge module), A2 (near-real-time monitoring, no latency guarantee, still no operator control) and A3 (auth/limits/TLS required off-loopback), exactly as worded in `PRD_v2.md`. Extend the v1 `docs/decisions.md` (six ADR entries exist) with entries (7)–(10): scope table (§2.2–2.4), transport = WebSocket, dashboard stays Streamlit, SMS/O-RAN/iOS code out of scope; and amend v1 entry (6) ('auth/rate-limit/HTTPS N/A') to say it no longer holds for the streaming server.
**Dependencies:** None
**Acceptance Criteria:**
- [x] Both authors approve the PR
- [x] Amendments A1–A3 present and match PRD_v2 wording
- [x] decisions.md has the four new entries with date and rationale, and entry (6) is amended
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T10-002: Place v2 planning docs and add a v2 row to the README status table
**Status:** ✅
**Description:** Commit `PRD_v2.md`, `DESIGN_v2.md`, `TECH_RULES_v2.md`, updated `ROADMAP.md` under `docs/planning/`; add 'v2 real-time' rows to the README status table marked ⬜ (G16: nothing marked implemented).
**Dependencies:** T10-001
**Acceptance Criteria:**
- [x] Files present under docs/planning/
- [x] README status rows exist and all show ⬜
- [x] Links in README resolve
**Estimated Effort:** 30 min
**Assigned To:** Backend
**Owner:** Sushil

#### T10-003: Add streaming dependencies to requirements files
**Status:** ✅
**Description:** Add FastAPI, uvicorn (with a WebSocket implementation), pydantic, httpx and `websockets` to `requirements.txt` (runtime) / `requirements-dev.txt` (test tools). Verify current stable versions at the time and pin them; run `pip install -r requirements-dev.txt` on both machines.
**Dependencies:** None
**Acceptance Criteria:**
- [x] Versions verified against the package indexes and pinned
- [x] `make lint test` still green on both machines
- [x] No new dependency added for anything the stdlib covers
**Estimated Effort:** 30 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T10-004: Add streaming constants to ml/config.py
**Status:** ✅
**Description:** Add `SESSION_MAX_ROWS`, `EVENT_CLOSE_GAP_SAMPLES`, `STALE_AFTER_SECONDS`, `CLOCK_SKEW_WARN_SECONDS`, `SESSION_RESUME_WINDOW_SECONDS`, `MAX_MESSAGE_BYTES`, `MAX_MSGS_PER_MIN`, `MAX_INFLIGHT_UNACKED`, `ALERT_MIN_PERSISTENCE_SAMPLES`, `ALERT_MIN_SEVERITY`, `ALERT_COOLDOWN_SECONDS`, using the *proposed* values from TECH_RULES_v2, each with an origin comment ('proposed — tune on non-evaluation data'). Do **not** redefine constants v1 already settled in EDA: `SESSION_GAP_SECONDS=30`, `DEFAULT_WINDOW=10`, `SAMPLING_SECONDS=3`, `PERSIST_THRESHOLDS`, `SENTINEL_INTS`, `RANDOM_STATE=42`; import them.
**Dependencies:** T10-001
**Acceptance Criteria:**
- [x] Every constant has a type and an origin comment
- [x] No threshold appears inline anywhere in streaming/ (grep check added in T10-009)
- [x] Constants are importable without importing sklearn
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Sushil

#### T10-005: Implement C7 ingest models in streaming/schema.py
**Status:** ✅
**Description:** Create pydantic models `IngestHello`, `IngestSample`, `IngestPing`, `IngestBye` and server messages `HelloAck`, `Ack`, `ErrorMsg`, `AlertPush`, plus `SCHEMA_VERSION = 2`. `IngestSample.payload` must carry exactly the 18 C1 columns (null = NA); `payload.timestamp` is a string exactly as the collector writes it to CSV (`dd-MM-yy HH:mm:ss`, device-local, no offset — `eda_findings.md` Open Question 1), parsed server-side by the existing `parse_timestamps`; `sent_at` is ISO-8601 *with* offset. Reject unknown `type`, over-long strings, negative `seq`.
**Dependencies:** T10-003, T10-004
**Acceptance Criteria:**
- [x] Golden valid/invalid examples round-trip (one with the real collector timestamp format)
- [x] Unknown fields in payload rejected; unknown top-level fields ignored
- [x] Version constant exported
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Sushil

#### T10-006: Implement C8 live-event models
**Status:** ✅
**Description:** In `streaming/schema.py` add `LiveSampleEvent` (all C4 columns + `seq`, `received_at`, `scored_at`, `published_at`, `edge_if_score`, `edge_divergence`, `model_eligible`), `EventRecord` (C5-compatible + `status` PROVISIONAL|FINAL + `alert_decision{alerted,reason}`), `ConnectionEvent`, `SnapshotEvent`, `DroppedEvent`, `HeartbeatEvent`, and the REST response models.
**Dependencies:** T10-005
**Acceptance Criteria:**
- [x] `status` is a closed enum
- [x] `alert_decision.reason` is one of the five fixed strings from DESIGN_v2
- [x] Models serialise to JSON with ISO-8601 timestamps
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T10-007: Implement C9 alert model and log format
**Status:** ✅
**Description:** Add `AlertRecord` (fields exactly as in TECH_RULES_v2 C9), `AlertDelivery`, and a `to_webhook_body()` method returning only `title, body, severity, anomaly_type, event_status, created_at`. Define `alerts.jsonl` as one JSON object per line.
**Dependencies:** T10-006
**Acceptance Criteria:**
- [x] Webhook body contains no evidence/cell IDs/device identifiers by default
- [x] `kind` enum NEW|ESCALATION|RESOLVED
- [x] JSONL round-trip test
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Sushil

#### T10-008: Export golden contract examples and add a drift check
**Status:** ✅
**Description:** Write `scripts/export_contract_examples.py` that emits JSON Schema and one valid example per message to `tests/fixtures/stream/`; add `--check` mode that fails if committed files differ from regenerated ones.
**Dependencies:** T10-005, T10-006, T10-007
**Acceptance Criteria:**
- [x] Files committed under tests/fixtures/stream/
- [x] `--check` fails after a deliberate schema edit
- [x] Kotlin tests can read the same example files
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T10-009: Create guardrail test stubs for G17–G26
**Status:** ⬜
**Description:** Create `tests/test_guardrails_v2.py` with one test function per G17–G26 (docstring quotes the rule), marked `xfail(strict=True)` with the task ID that will implement it. Add the grep check: no numeric threshold literals in `streaming/` outside config.
**Dependencies:** T10-001
**Acceptance Criteria:**
- [ ] Ten stubs exist and are listed by `pytest -v`
- [ ] Each stub names its implementing task
- [ ] Grep check runs in `make lint`
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T10-010: Extend CI for streaming tests and secret patterns
**Status:** ⬜
**Description:** Update `.github/workflows/ci.yml` to run `pytest tests/streaming`, the contract drift check, and the secret scan with extra patterns (webhook URLs, SMTP passwords, 32-byte hex/base64 tokens). Soak tests excluded from CI.
**Dependencies:** T10-003
**Acceptance Criteria:**
- [ ] CI green on a PR touching streaming/
- [ ] A planted fake token in a test branch makes CI fail
- [ ] Runtime stays reasonable (note it in the PR)
**Estimated Effort:** 45 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T10-011: Add env template, token generator and Makefile targets
**Status:** ✅
**Description:** Update `.env.example` with `NADS_HOST`, `NADS_PORT`, `NADS_INGEST_TOKEN`, `NADS_ALLOW_LAN`, `NADS_ALLOW_REMOTE_VIEW`, `NADS_ALERT_WEBHOOK_URL`, `NADS_ALERT_EMAIL_*`, `NADS_ALERT_INCLUDE_EVIDENCE` (placeholders only). Extend the existing v1 Makefile (targets `setup, lint, format, test, preprocess, pipeline, dashboard, clean-processed, help`; `dashboard` already binds 127.0.0.1) with `make token` (prints a CSPRNG token, does not save it), `make serve`, `make replay CSV=…`, `make demo-live`; update `make help`; `clean-processed` must still never touch `data/raw/` or `data/live/`.
**Dependencies:** T10-003
**Acceptance Criteria:**
- [x] `.env` ignored; `.env.example` has placeholders only
- [x] `make token` output is ≥32 bytes of randomness
- [x] `make help` lists the new targets; existing targets unchanged
**Estimated Effort:** 45 min
**Assigned To:** DevOps
**Owner:** Sushil

#### T10-012: Check the phone↔laptop link options on both test phones
**Status:** ⬜ · 🧑 Human-only
**Description:** Verify that `adb reverse tcp:<port> tcp:<port>` works on the Redmi (Android 16 per `eda_findings.md`) and the Samsung SM-A156E with a trivial echo server; note Wi-Fi/hotspot reachability. Record results and any OEM quirks in `docs/decisions.md`. ⚠️ UNCLEAR: demo venue link.
**Dependencies:** None
**Acceptance Criteria:**
- [ ] Result per device (works / fails / needs setting) recorded
- [ ] Recommended demo link written down
**Estimated Effort:** 45 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T10-013: Add model_version and feature_hash to the model metadata
**Status:** ✅
**Description:** `models/if_v1.meta.json` already records feature list, params, seed, sklearn version, training-data SHA-256, row count and date (v1 T4-008). Extend `ml/train.py` to also write `model_version`, `feature_hash` (hash of the ordered `FEATURE_COLUMNS`), `model_sha256` and the saved scaler's SHA-256; add a loader check that raises `ConfigError` on mismatch. Retraining must not change scores (re-run with the same seed and compare).
**Dependencies:** None
**Acceptance Criteria:**
- [x] Metadata contains the three new fields
- [x] Loader raises ConfigError on tampered feature list
- [x] `scores.csv` hash on data/sample unchanged
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T10-014: Re-scope v1 'no network in core pipeline' checks and amend the N/A security notes
**Status:** ✅
**Description:** v1 T7-009 (`tests/test_security_privacy.py`) asserts no network library imports (`requests`, `httpx`, `urllib`, `socket`) in `ml/` and `pipelines/`, and a loopback-bound dashboard. Ensure core `ml/`, `pipelines/` and `agents/` remain network-free (G13) while allowing the new `streaming/` package to import FastAPI/httpx; keep the dashboard-binds-127.0.0.1 check. Amend `docs/testing.md` and `docs/decisions.md` (entry 6) where auth/rate-limiting/HTTPS are listed as N/A.
**Dependencies:** T10-001
**Acceptance Criteria:**
- [x] Check still fails if `ml/` or `agents/` import a network library
- [x] `streaming/` is explicitly exempt and documented
- [x] `docs/testing.md` N/A list updated
**Estimated Effort:** 30 min
**Assigned To:** QA
**Owner:** Yashwant

#### T10-015: ⚠️ UNCLEAR: confirm how SENTINEL_INTS are applied per column
**Status:** ✅
**Note:** sentinel behaviour recorded in docs/eda_findings.md; fix deferred to a separate v1 change
**Description:** `eda_findings.md` records `SENTINEL_INTS = [2147483647, -1, 99, 999]`. `-1` and `99` can be legitimate dB values (e.g. SINR −1 dB). Read `coerce_numeric` and `docs/eda_findings.md` to confirm whether each sentinel is applied only to the columns where it is actually a sentinel; if applied to all columns, record the effect on real samples (count of legitimate-looking values turned missing). This is a v1 behaviour the live path inherits through G17, so do not change it silently — record the finding and ask the human.
**Dependencies:** None
**Acceptance Criteria:**
- [x] Per-column behaviour documented in eda_findings.md
- [x] Count of affected rows on data/raw reported (or 'none')
- [x] Decision recorded in decisions.md; any change goes through a separate v1 PR
**Estimated Effort:** 45 min
**Assigned To:** QA
**Owner:** Sushil

---

## Phase 11: Streaming Server Core
*Goal: Phone-independent live path: ingest → engine → events → agents → live API, proven equal to batch.*

#### T11-001: Create the streaming/ package skeleton
**Status:** ✅
**Description:** Create `streaming/{__init__,schema,server,session_manager,engine,event_tracker,hub,store,metrics}.py` and `streaming/alerts/{__init__,policy,dispatcher}.py` plus `channels/` with module docstrings stating each module's single responsibility. No logic yet.
**Dependencies:** T10-001
**Acceptance Criteria:**
- [x] Package importable
- [x] Each module has a one-paragraph responsibility docstring
- [x] ruff passes
**Estimated Effort:** 30 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-002: Implement the per-session buffer
**Status:** ✅
**Description:** In `streaming/session_manager.py` implement `SessionBuffer`: append validated C2 rows, track `last_seq`, ignore duplicate seq, keep device-timestamp order, enforce `SESSION_MAX_ROWS` (close and roll to a new session, log WARNING). Pure, synchronous, injectable clock.
**Dependencies:** T11-001, T10-005
**Acceptance Criteria:**
- [x] Duplicate seq adds no row
- [x] Out-of-order arrivals end up ordered by timestamp
- [x] Rollover at cap tested
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T11-003: Validate and coerce ingest samples via the batch code
**Status:** ⬜
**Description:** In `streaming/engine.py` add `coerce_sample(payload) -> DataFrame` that builds a one-row C1 frame and calls the existing `ml.schema` validation and the `ml.preprocessing` functions `coerce_numeric`, `flag_invalid`, `add_missing_flags` (every `NA` token and every `SENTINEL_INTS` value → missing, range flag, `csi_available`, `model_eligible`; `nci` stays 64-bit-safe). No new coercion logic may be written.
**Dependencies:** T11-001, T10-005
**Acceptance Criteria:**
- [ ] `NA`, null and every `SENTINEL_INTS` value become missing, never 0 (G3); `nci=13322280247` survives
- [ ] Invalid `deployment_mode` raises SchemaError
- [ ] Function body contains no duplicated range/sentinel constants
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T11-004: Apply the batch session-gap rule in the stream
**Status:** ⬜
**Description:** Call `add_sessions(df, gap_seconds=SESSION_GAP_SECONDS)` (30 s, from EDA) so a gap starts a new `session_id` (`<device_slug>-<n>`) and `sample_idx` restarts at 0 exactly as in batch. v1 also starts a session when `source_file` changes, so the server sets `source_file` to the live capture filename and a `hello` without `resume_from_seq` opens a new one. Use `parse_timestamps` for the collector's `dd-MM-yy HH:mm:ss` strings.
**Dependencies:** T11-002, T11-003
**Acceptance Criteria:**
- [ ] A >30 s gap fixture yields 2 sessions, same ids as batch
- [ ] Warm-up semantics identical at session start
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T11-005: Implement StreamingEngine.process()
**Status:** ⬜
**Description:** `StreamingEngine.process(sample) -> ScoredSample`: append to buffer, call the same v1 functions on the session buffer — `build_features(df, window=DEFAULT_WINDOW)`, `baseline_scores`, `if_scores(df, model, scaler)` (model and the saved scaler loaded once, meta verified per T10-013), `classify`, `estimate_severity` (confirm exact names/signatures in the repo) — and return the last row with C4 columns. Rows with missing model features get `model_eligible=False` and no IF score.
**Dependencies:** T11-004, T10-013
**Acceptance Criteria:**
- [ ] Model and meta verified at startup; ConfigError on mismatch
- [ ] No fillna/interpolation on ss_*/csi_* (G2)
- [ ] No sklearn import outside ml/ and the model loader
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T11-006: Write the stream–batch parity test (G17)
**Status:** ⬜
**Description:** `tests/streaming/test_parity.py`: replay `data/sample/` and every `tests/fixtures/*_synthetic.csv` through the engine sample by sample and compare to the batch `detect()` / `pipelines.run_pipeline` output: flags, type, severity identical; `if_score`, `baseline_z_max` within 1e-6. Add variants: chunked delivery, shuffled arrival with correct timestamps.
**Dependencies:** T11-005
**Acceptance Criteria:**
- [ ] Test passes on real sample and synthetic fixtures
- [ ] Deliberately breaking a feature in streaming/ makes it fail
- [ ] Test wired into CI and into G17 stub
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Yashwant

#### T11-007: Implement the EventTracker
**Status:** ⬜
**Description:** `streaming/event_tracker.py`: open an event at the first classified sample, update type/severity as it grows by reusing the event-grouping logic in `ml/anomaly_analysis.detect()` (if grouping is not separately callable, extract it into a helper with unchanged batch output — `scores.csv`/`events.json` byte-identical on `data/sample/`), close after `EVENT_CLOSE_GAP_SAMPLES` normal samples or session end. Status PROVISIONAL → FINAL; FINAL events immutable.
**Dependencies:** T11-005
**Acceptance Criteria:**
- [ ] Event ids match the batch format (`<session>-eNNN`)
- [ ] FINAL event cannot be modified (raises)
- [ ] Closed events equal batch events on fixtures (extends T11-006)
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-008: Run the unchanged agents on event open/change/close
**Status:** ⬜
**Description:** In the tracker, call `agents.orchestrator.build_event_window(scores_df, event, context=N)` and `run_agents(window)` on open, on type/severity change and on close; cache by `(event_id, window_hash)`. Validate each record with the same check `write_events_diagnosed` uses, and attach the `PROVISIONAL|FINAL` status. No file under `agents/` may change.
**Dependencies:** T11-007
**Acceptance Criteria:**
- [ ] `git diff` shows no change under agents/
- [ ] ML flags identical with agents stubbed out (G9)
- [ ] Diagnosis text passes the existing hedged-language tests
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-009: Implement the live capture store
**Status:** ⬜
**Description:** `streaming/store.py`: append each accepted sample to `data/live/<client>_<session>_<YYYYMMDD>_<HHMM>.csv` in exact C1 header/format, write `.meta.json` (`source`, `status` OPEN/CLOSED/INCOMPLETE), fsync and sha256 on close. Refuse any path under `data/raw/`.
**Dependencies:** T11-002
**Acceptance Criteria:**
- [ ] Capture re-ingested by the batch pipeline gives identical rows
- [ ] Path guard test (G7/G22)
- [ ] Crash simulation leaves status INCOMPLETE
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-010: Create the FastAPI app with auth dependency and config loading
**Status:** ✅
**Description:** `streaming/server.py`: app factory, `/healthz`, env/config loading, per-request correlation id, token dependency using `hmac.compare_digest`, generic error handler returning the C8 error body (no tracebacks).
**Dependencies:** T10-004, T10-005, T11-001
**Acceptance Criteria:**
- [x] Wrong/missing token → 401
- [x] Errors never leak stack traces or the token
- [x] `/healthz` needs no token and leaks nothing sensitive
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-011: Implement WS /api/v1/ingest
**Status:** ⬜
**Description:** hello/hello_ack, sample handling (coerce → engine → store → hub), cumulative `ack` every 5 samples or 5 s, `ping/pong`, `bye`, error closes with the C7 codes, `MAX_MESSAGE_BYTES` and token-bucket rate limit.
**Dependencies:** T11-010, T11-003, T11-005, T11-009
**Acceptance Criteria:**
- [ ] All C7 message types handled per TECH_RULES_v2
- [ ] Oversize frame closes with 1009
- [ ] Rate limit returns RATE_LIMITED without closing
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-012: Implement resume and idempotent acks
**Status:** ⬜
**Description:** Honour `resume_from_seq` and `SESSION_RESUME_WINDOW_SECONDS`; duplicates re-acked but not reprocessed (G19); forward seq gaps recorded in metrics as ranges; `SESSION_CONFLICT` for a second live connection on one `client_id`.
**Dependencies:** T11-011
**Acceptance Criteria:**
- [ ] Duplicate fixtures add no rows
- [ ] Gap ranges visible in `/api/v1/metrics`
- [ ] Reconnect within window continues the same session
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-013: Implement the live fan-out hub
**Status:** ⬜
**Description:** `streaming/hub.py`: async pub/sub with bounded per-subscriber queues; on overflow drop oldest and send a `dropped` event; subscriber cleanup on disconnect.
**Dependencies:** T11-001, T10-006
**Acceptance Criteria:**
- [ ] Slow subscriber never blocks the engine
- [ ] `dropped` event emitted with count
- [ ] Cleanup test (no leaked subscribers)
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T11-014: Implement WS /api/v1/live and the REST endpoints
**Status:** ⬜
**Description:** Implement `snapshot` on connect, `sample`, `event_*`, `alert`, `connection`, `heartbeat`; REST `sessions`, `samples?since_seq=`, `events`, `alerts`, `model`, `metrics` with `MAX_PAGE=1000`. Read endpoints loopback-only unless `NADS_ALLOW_REMOTE_VIEW=true`.
**Dependencies:** T11-013, T11-008, T11-010
**Acceptance Criteria:**
- [ ] Matches golden C8 examples
- [ ] Non-loopback client refused by default
- [ ] Pagination cap enforced
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-015: Write the replay tool
**Status:** ⬜
**Description:** `scripts/replay_stream.py --csv --speed N --host --port --token`: send a C1 CSV through the ingest WebSocket honouring acks, assigning seq, setting session `source=replay`; clear error messages and exit code 2 on bad args.
**Dependencies:** T11-011
**Acceptance Criteria:**
- [ ] Replays `data/sample/` at 1× and 20×
- [ ] Respects acks (no unbounded flooding)
- [ ] Session metadata shows `source=replay`
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T11-016: Unit tests for buffer, validation and ingest handling
**Status:** ⬜
**Description:** `tests/streaming/`: buffer dedupe/order/rollover, coercion negatives (bad enum, extra column, sentinel), seq gap and duplicate handling, rate limiter token bucket (injectable clock).
**Dependencies:** T11-002, T11-003, T11-012
**Acceptance Criteria:**
- [ ] Each function has a negative/edge test
- [ ] No sleep-based assertions
- [ ] Coverage on streaming/ ≥80% so far
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Sushil

#### T11-017: Integration test: replay → server → live subscriber
**Status:** ⬜
**Description:** Using the FastAPI test client: connect a live subscriber, replay the sample via the real ingest handler, assert `snapshot`, `sample`, `event_open/closed` ordering, live-capture CSV equals input, and batch-on-capture equals live results.
**Dependencies:** T11-014, T11-015
**Acceptance Criteria:**
- [ ] Test is deterministic (injectable clock)
- [ ] Live-vs-batch-on-capture comparison passes
- [ ] Runs in CI under a minute
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Sushil

#### T11-018: Add latency and stream-quality instrumentation
**Status:** ⬜
**Description:** `streaming/metrics.py`: record `received_at`, `scored_at`, `published_at` per sample (monotonic where possible), rolling p50/p95/max, sequence-gap ranges, duplicates, drops, skew estimate; expose via `/api/v1/metrics`.
**Dependencies:** T11-005, T11-013
**Acceptance Criteria:**
- [ ] Percentiles computed over a bounded window
- [ ] Metrics reset per session
- [ ] No wall-clock sleeps in tests
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T11-019: Add the server CLI with the bind policy
**Status:** ⬜
**Description:** `python -m streaming.server --host --port --allow-lan`; default `127.0.0.1`; non-loopback requires `--allow-lan` and a non-empty `NADS_INGEST_TOKEN` or exit code 2 with a one-line fix hint. Wire `make serve`.
**Dependencies:** T11-010
**Acceptance Criteria:**
- [ ] Empty token + 0.0.0.0 refuses to start
- [ ] `--help` documents every flag
- [ ] Startup log lists enabled channels without secrets
**Estimated Effort:** 45 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T11-020: Implement stale detection and clock-skew flagging
**Status:** ⬜
**Description:** Server-side `connection` state machine (LIVE/STALE/RECONNECTING/WAITING) from last-sample age and socket state using `STALE_AFTER_SECONDS`; skew estimate between `sent_at` and `received_at`, flag above `CLOCK_SKEW_WARN_SECONDS` without altering timestamps.
**Dependencies:** T11-011, T11-018
**Acceptance Criteria:**
- [ ] State transitions tested with an injectable clock
- [ ] Skewed fixture raises the flag, data unchanged
- [ ] `connection` events published to the hub
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Sushil

---

## Phase 12: Android Streaming Client & Edge Inference
*Goal: Phone streams reliably without ever harming CSV logging; optional advisory edge scoring only if it passes parity.*

#### T12-001: Add streaming settings to the Android app
**Status:** ⛔ superseded by T19-008
**Description:** Add host, port, pairing-token fields (masked, stored with Keystore-backed encrypted storage — verify the current AndroidX/Keystore approach), a stream on/off switch and a 'Test connection' button reporting unreachable / unauthorised / version mismatch / OK. Show the privacy warning for `session_label`.
**Dependencies:** T10-005
**Acceptance Criteria:**
- [ ] Token never appears in logs or UI after entry
- [ ] Test connection shows specific failures
- [ ] Settings survive app restart
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-002: Implement StreamClient (WebSocket, hello/sample/ack)
**Status:** ⬜
**Description:** Package `...streaming`: OkHttp WebSocket (verify current version), serialise the existing measurement object to C7 `sample` (null for NA, sentinels sent as-is), generate and persist a random UUID `client_id`, send `hello` with `resume_from_seq`, handle `hello_ack`, `ack`, `error`, `alert`. All I/O off the main thread.
**Dependencies:** T19-008, T11-011
**Acceptance Criteria:**
- [ ] Serialisation equals the golden C7 example byte-for-byte after canonicalisation
- [ ] No hardware identifiers in any message
- [ ] Fatal error codes stop reconnect loops
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-003: Implement the unacked-sample queue
**Status:** ⬜
**Description:** Persistent queue (decide Room/SQLite vs append-only file, record the choice in decisions.md) with cap `MAX_QUEUE` (proposed 5,000 ≈ 4 h); drop **oldest** when full and increment `dropped_from_queue`; delete items ≤ cumulative `ack`.
**Dependencies:** T12-002
**Acceptance Criteria:**
- [ ] Survives process kill
- [ ] Drop-oldest counter reported in `hello`/`ping`
- [ ] Max in-flight unacked ≤ `MAX_INFLIGHT_UNACKED`
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-004: Implement reconnect with backoff and resume
**Status:** ⬜
**Description:** Exponential backoff with jitter (cap 30 s), resume from `last_seq_acked`, flush backlog paced by acks, re-`hello` with queue stats. Reconnect is cancelled on fatal errors (UNAUTHORIZED, VERSION_MISMATCH).
**Dependencies:** T12-003, T11-012
**Acceptance Criteria:**
- [ ] Server restart mid-session resumes with no duplicates stored
- [ ] Flush does not flood (respects window)
- [ ] Backoff unit-tested with a fake clock
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-005: Keep logging and streaming alive in a foreground service
**Status:** ⛔ superseded by T19-009
**Description:** Run collection+streaming in a foreground service with the notification and service type required by current Android versions (verify), request battery-optimisation guidance with the one-time dialog from DESIGN_v2, and test screen-off behaviour on the Redmi 13 5G (Android 16 per `eda_findings.md`) and the Samsung SM-A156E. ⚠️ UNCLEAR: OEM background restrictions; 🧑 Human-only (needs the phones).
**Dependencies:** T12-002
**Acceptance Criteria:**
- [ ] 20 min with screen off on each phone: samples continue or the failure is documented per device
- [ ] No dark-pattern prompts
- [ ] Notification text states what is running
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-006: Add the streaming status strip
**Status:** ⛔ superseded by T19-006
**Description:** Show `Streaming: Connected | Reconnecting (queue n) | Off`, last ack time and dropped counter on the logging screen with icon + text (DESIGN_v2 Android section); touch targets ≥48 dp.
**Dependencies:** T12-004
**Acceptance Criteria:**
- [ ] States match the C7 connection lifecycle
- [ ] Readable with TalkBack labels (manual check)
**Estimated Effort:** 45 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-007: Prove CSV logging is independent of streaming (G18)
**Status:** ⬜
**Description:** Ensure the CSV writer is called before/independently of the stream path and that any `StreamClient` exception is caught, counted and surfaced without touching logging. Add a regression test with a failing fake client.
**Dependencies:** T12-002
**Acceptance Criteria:**
- [ ] Killing the server mid-session leaves a complete CSV
- [ ] Exception in StreamClient never stops logging
- [ ] Test fails if the order is reversed
**Estimated Effort:** 45 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-008: Android unit tests for serialisation, queue and backoff
**Status:** ⬜
**Description:** JVM tests: golden C7 JSON, null/sentinel handling, queue cap/drop-oldest/ack-delete, backoff schedule, resume logic.
**Dependencies:** T12-003, T12-004
**Acceptance Criteria:**
- [ ] Tests run via Gradle without a device
- [ ] Golden files shared with Python tests
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T12-009: Experiment: does streaming change the measurements?
**Status:** ⬜ · 🧑 Human-only
**Description:** Collect matched stationary and walking sessions with streaming off, streaming over Wi-Fi, over USB `adb reverse`, and (once, as a negative control) over cellular to a reachable host. Compare RSRP/RSRQ/SINR distributions and `network_type` shares; write `docs/streaming_perturbation.md` with counts, plots and honest caveats. This tests a hypothesis; do not assume an effect either way.
**Dependencies:** T12-004, T11-011
**Acceptance Criteria:**
- [ ] ≥200 samples per condition or the shortfall stated
- [ ] Conclusion states what the data can and cannot show
- [ ] Recommended link in decisions.md updated
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Yashwant

#### T12-010: Real-device live session test
**Status:** ⬜ · 🧑 Human-only
**Description:** Run a 20-minute walking session on the Redmi streaming to the server (USB or Wi-Fi) with two forced disconnects; verify seq continuity, live capture CSV vs phone CSV row match, and dashboard events.
**Dependencies:** T19-009, T19-006, T11-014
**Acceptance Criteria:**
- [ ] Phone CSV and live capture match except documented drops
- [ ] All gaps reported in Stream Health data
- [ ] Result recorded in docs/results_v2.md
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T12-011: Edge spike: choose the export approach and decide go/no-go
**Status:** ⬜ · ➕ Optional
**Description:** Time-boxed (90 min): try (a) exporting `if_v1.joblib` trees/scaler to JSON for a Kotlin traversal and (b) checking ONNX conversion support for `IsolationForest` in the pinned scikit-learn/converter versions (verify in current docs). Compare a handful of scores in Python. Record the decision and reasons in decisions.md; 'no-go' marks T12-012..T12-018 ⛔ (dropped: reason).
**Dependencies:** T10-013
**Acceptance Criteria:**
- [ ] Decision recorded with evidence
- [ ] If go: tolerance (1e-6 proposed) confirmed achievable on 20 vectors
- [ ] If no-go: remaining edge tasks marked ⛔ with a 'dropped:' reason
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T12-012: Export the edge model artefact
**Status:** ⬜ · ➕ Optional
**Description:** `ml/export_edge_model.py` writes `models/if_v1.edge.json` (tree arrays, thresholds, normalisation constant inputs, the fitted `StandardScaler` parameters from `models/`, the `if_score` normalisation formula from v1 T4-009, `PERSIST_THRESHOLDS` and `DEFAULT_WINDOW`, feature order, `model_version`, `feature_hash`, source `model_sha256`). Re-running yields byte-identical output.
**Dependencies:** T12-011
**Acceptance Criteria:**
- [ ] Deterministic output
- [ ] Hash fields match if_v1.meta.json
- [ ] Python re-implementation of the traversal reproduces sklearn scores within tolerance
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T12-013: Kotlin EdgeScorer in the separate edge-inference module
**Status:** ⬜ · ➕ Optional
**Description:** New Gradle module `edge-inference`: load the artefact, verify `feature_hash`, compute the IF score for a feature vector; refuse to score on mismatch. No dependency from the collector's measurement packages (G1′).
**Dependencies:** T12-012
**Acceptance Criteria:**
- [ ] Hash mismatch disables scoring
- [ ] Gradle check: only the composition root depends on the module
- [ ] Scores match golden vectors (after T12-016)
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-014: Kotlin features: deltas, change flags, rolling stats
**Status:** ⬜ · ➕ Optional
**Description:** Implement in `edge-inference` the `FEATURE_COLUMNS` for deltas (`delta_rsrp/rsrq/sinr`), change flags (`pci_changed`, `nci_changed`, `network_changed`), rolling mean/std (window 10) and, if `ml/config.py` lists them, the raw `pci`/`nci`/`nrarfcn` (`nci` needs a 64-bit Long), using the same missing-value rules (NaN stays NaN; first sample of a session: delta missing, flags 0).
**Dependencies:** T12-011
**Acceptance Criteria:**
- [ ] Matches the Python column order
- [ ] NaN never becomes 0 (G2)
- [ ] Edge cases: window longer than session
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-015: Kotlin features: persistence (run-length) features
**Status:** ⬜ · ➕ Optional
**Description:** Implement `poor_sinr_run`, `poor_rsrq_run`, `weak_rsrp_run` (and any other persistence columns present in `FEATURE_COLUMNS`) using thresholds read from the artefact, not hard-coded.
**Dependencies:** T12-014
**Acceptance Criteria:**
- [ ] Run-lengths reset at session boundaries and on missing values exactly as in Python
- [ ] Thresholds come from the artefact
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-016: Golden-vector parity tests (G25)
**Status:** ⬜ · ➕ Optional
**Description:** Python script writes `tests/fixtures/stream/edge_parity.json` (raw sample sequences → features → scores); Kotlin unit test asserts features and scores within tolerance. If it cannot pass, mark edge as no-go and stop (do not loosen tolerance).
**Dependencies:** T12-013, T12-015
**Acceptance Criteria:**
- [ ] Python and Kotlin read the same fixture
- [ ] Failure blocks release of edge
- [ ] Tolerance documented
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Yashwant

#### T12-017: Server: store edge score and log divergence
**Status:** ⬜ · ➕ Optional
**Description:** In the engine/hub, accept optional `edge` blocks, verify `model_version`/`feature_hash`, compute `edge_divergence = |edge − server|`, flag above tolerance, expose in `ScoredSample` and metrics. The server score stays authoritative.
**Dependencies:** T12-016, T11-005
**Acceptance Criteria:**
- [ ] Mismatched hash ignores the edge score with a WARNING
- [ ] Divergence counter in /metrics
- [ ] Flags/type/severity unchanged with edge present (G25)
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Sushil

#### T12-018: Show the advisory edge score on the phone
**Status:** ⬜ · ➕ Optional
**Description:** Display 'Edge score (advisory): x.xx' as a secondary line only when the edge module is enabled; never display 'anomaly detected' or a diagnosis; add `edge` block to `sample` messages.
**Dependencies:** T12-016, T19-006
**Acceptance Criteria:**
- [ ] Edge off by default
- [ ] Wording per DESIGN_v2
- [ ] Disabled automatically on any parity-hash mismatch
**Estimated Effort:** 45 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T12-019: Phone: show server alerts as local notifications
**Status:** ⬜
**Description:** Handle C7 `alert` messages by posting a standard Android notification (normal importance channel) with title/body from the message; request the notification permission on versions that require it (verify); tapping opens the status screen. No sound pattern customisation.
**Dependencies:** T12-004, T13-006
**Acceptance Criteria:**
- [ ] Notification text equals the C9 title/body
- [ ] Permission denial handled gracefully
- [ ] Duplicate alert ids notify once
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

---

## Phase 13: Live Dashboard & Alerting
*Goal: Evidence-gated alerts and the Live mode pages from DESIGN_v2.*

#### T13-001: Implement the alert policy as a pure function
**Status:** ⬜
**Description:** `streaming/alerts/policy.py: decide(event_state, history, config) -> AlertDecision`. Rules 1–3 from TECH_RULES_v2: type not in {NORMAL, STATISTICAL_ONLY, CELL_TRANSITION, NETWORK_STATE_TRANSITION}, ≥1 agent with rule evidence, and (persistence ≥ `ALERT_MIN_PERSISTENCE_SAMPLES` or severity ≥ `ALERT_MIN_SEVERITY`). Return one of the five fixed `reason` strings.
**Dependencies:** T11-007
**Acceptance Criteria:**
- [ ] No I/O or clock access inside
- [ ] `STATISTICAL_ONLY` (ML-only) → 'ML-only (no rule evidence)'
- [ ] Cell/network change alone never alerts (G6/G21)
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T13-002: Add cooldown, escalation and resolution
**Status:** ⬜
**Description:** Extend `decide` / a small state object: cooldown per `(session, anomaly_type)` using `ALERT_COOLDOWN_SECONDS`; `ESCALATION` only when severity rises; `RESOLVED` only after a delivered NEW/ESCALATION and event close.
**Dependencies:** T13-001
**Acceptance Criteria:**
- [ ] Cooldown tested with an injectable clock
- [ ] No duplicate NEW after reconnect
- [ ] RESOLVED never sent without a prior delivered alert
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T13-003: Implement the dispatcher and in-app channel
**Status:** ⬜
**Description:** `dispatcher.py` fans out to channels with per-channel timeout, one retry, exception isolation, `delivery[]` recording; `in_app.py` publishes C9 to the hub and appends to `data/live/alerts.jsonl`. Alert text comes from `agents.text_renderer` templates.
**Dependencies:** T13-002, T11-013, T10-007
**Acceptance Criteria:**
- [ ] A raising channel never reaches the engine
- [ ] `alerts.jsonl` has one valid C9 per line
- [ ] No LLM import on this path (G13)
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Sushil

#### T13-004: Implement the webhook channel
**Status:** ⬜
**Description:** `channels/webhook.py` with httpx: POST the minimal `to_webhook_body()` JSON, 5 s timeout, one retry, URL from `NADS_ALERT_WEBHOOK_URL`, never logged; off unless the env var is set; `--dry-run` prints the payload instead of sending.
**Dependencies:** T13-003
**Acceptance Criteria:**
- [ ] Payload equals the minimal subset (G26)
- [ ] Timeout recorded as FAILED, pipeline unaffected
- [ ] URL absent from all logs
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T13-005: Implement the email channel
**Status:** ⬜
**Description:** `channels/email.py` using stdlib `smtplib` with STARTTLS (verify server requirements), env-only credentials (`NADS_ALERT_EMAIL_*`), 10 s timeout, plain-text body equal to the minimal subset; off by default.
**Dependencies:** T13-003
**Acceptance Criteria:**
- [ ] No credentials in logs
- [ ] Failure isolated
- [ ] Dry-run mode prints the message
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T13-006: Implement the phone-notification channel (server side)
**Status:** ⬜
**Description:** `channels/phone.py`: send C7 `alert` (compact C9) to the live ingest connection of the event's session; if the phone is disconnected, mark delivery `SKIPPED` (no queueing in v2).
**Dependencies:** T13-003, T11-011
**Acceptance Criteria:**
- [ ] Delivery status recorded
- [ ] No message sent to other clients
- [ ] LOW severity not pushed by default
**Estimated Effort:** 30 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T13-007: Implement alert acknowledgement
**Status:** ⬜
**Description:** `POST /api/v1/alerts/{alert_id}/ack` idempotent, rate-limited, sets `acknowledged_at`, appends an ack record to `alerts.jsonl`, publishes an `alert` update.
**Dependencies:** T13-003, T11-014
**Acceptance Criteria:**
- [ ] Second ack returns 200 without a second record
- [ ] Unknown id → 404 with C8 error body
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Sushil

#### T13-008: Evaluate the alert policy on existing data by replay
**Status:** ⬜
**Description:** `scripts/eval_alert_policy.py`: stream the v1 sample/exploration data, list which events alert and why, compute alerts/hour on stationary-normal data. Choose thresholds on **non-evaluation** data only; record the procedure.
**Dependencies:** T13-002, T11-015
**Acceptance Criteria:**
- [ ] Report lists every event with its alert decision
- [ ] Thresholds origin documented; evaluation labels untouched
- [ ] Result feeds docs/results_v2.md
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T13-009: Alert tests: policy negatives, cooldown, channel failure
**Status:** ⬜
**Description:** `tests/streaming/test_alerts.py`: ML-only, low RSRP only, low SINR only, UNKNOWN only, cell change only, 5G→LTE only → no alert; cooldown/escalation/resolve; webhook timeout and email failure do not affect in-app delivery.
**Dependencies:** T13-002, T13-003
**Acceptance Criteria:**
- [ ] All negative cases from v1 list covered (G21)
- [ ] Property-style test over fixtures
- [ ] Coverage on alerts/ ≥85%
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Sushil

#### T13-010: Build the live client and connection state machine
**Status:** ⛔ superseded by T17-001
**Description:** `dashboard/live_client.py`: background consumer of `WS /api/v1/live` with REST resync on `dropped`/reconnect, thread-safe snapshot, dashboard-side DISCONNECTED detection; falls back to 1 s REST polling if the WebSocket thread is unstable (note in decisions.md). ⚠️ Verify Streamlit threading behaviour in the current docs.
**Dependencies:** T11-014
**Acceptance Criteria:**
- [ ] Snapshot read never blocks UI
- [ ] Reconnect resyncs without duplicates
- [ ] No token ever rendered
**Estimated Effort:** 90 min
**Assigned To:** Full-stack
**Owner:** Sushil

#### T13-011: Add the Mode switch and connection chip
**Status:** ⛔ superseded by T17-002, T17-010
**Description:** Extend the v1 sidebar (`dashboard/app.py`, T6-010) with a Live/Replay switch; connection chip with state, icon, text and sample age (states and colours per DESIGN_v2); Replay mode untouched. Yashwant owns the v1 sidebar code, so he takes this task to keep one owner per module.
**Dependencies:** T13-010
**Acceptance Criteria:**
- [ ] All six states renderable from a mocked snapshot
- [ ] Replay mode behaves exactly as v1
- [ ] Chip text, not only colour, conveys state
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Yashwant

#### T13-012: Build Live Overview (L1)
**Status:** ⛔ superseded by T17-003
**Description:** Status banner with PROVISIONAL badge, ML-only line, metric cards with deltas, network-state card (Unknown never shown as SA), score block (baseline and IF separate, edge secondary), event/status, diagnosis/evidence/recommendation, sparkline, Pause toggle, WAITING/DISCONNECTED states.
**Dependencies:** T13-011
**Acceptance Criteria:**
- [ ] Matches DESIGN_v2 L1 layout
- [ ] STALE view shows 'last known values'
- [ ] UNKNOWN/NA display rules from v1 hold
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T13-013: Build Live Signals (L2)
**Status:** ⛔ superseded by T17-004
**Description:** Three stacked Plotly time series over a 5/15/60 min window, anomaly × markers, cell-change lines, score chart with threshold, baseline/IF toggle, gap bands, text summary above each chart, data-table expander; render-only downsampling above ~5,000 points.
**Dependencies:** T13-011
**Acceptance Criteria:**
- [ ] Lines break at gaps/NA; never interpolated (G2)
- [ ] Zoom behaviour documented (freeze/reset fallback)
- [ ] Summary sentence updates each refresh
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T13-014: Build Live Cells & Network (L3)
**Status:** ⛔ superseded by T17-005
**Description:** PCI/NCI/NRARFCN step charts, network-type strip, transitions table, markers linking to events; v1 copy rule about cell changes shown.
**Dependencies:** T13-011
**Acceptance Criteria:**
- [ ] Neutral wording for transitions
- [ ] Empty state text per DESIGN_v2
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T13-015: Build the events panel (L4, events half)
**Status:** ⛔ superseded by T17-006
**Description:** Events table with status and 'alerted? (reason)' columns, row-select detail with Signal/Cell/Network/Diagnosis/Recommendation, window chart, download event JSON; PROVISIONAL diagnoses prefixed 'Provisional —'.
**Dependencies:** T13-011, T11-008
**Acceptance Criteria:**
- [ ] Reason strings are the five fixed values
- [ ] FINAL events show no 'provisional' wording
- [ ] Download JSON validates against C5 + status
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T13-016: Build the alerts panel and banner (L4, alerts half)
**Status:** ⛔ superseded by T17-006
**Description:** Alert banner on L1/L4 with severity chip, Acknowledge button calling the ack API, alerts history table, per-channel status rows (red only for failures), toast once per alert id.
**Dependencies:** T13-015, T13-007
**Acceptance Criteria:**
- [ ] Alert uses icon + word + colour
- [ ] Ack persists across refresh
- [ ] Failed channel shows cause text
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T13-017: Build Stream Health (L5)
**Status:** ⛔ superseded by T17-007
**Description:** Show connection timeline, latency p50/p95/max with the 'no latency guarantee' footnote, completeness counters, gap ranges, phone queue depth, subscriber drops, clock skew warning, model version/hash, edge divergence (only if enabled).
**Dependencies:** T13-011, T11-018
**Acceptance Criteria:**
- [ ] Numbers shown exactly as served by /metrics
- [ ] Footnote present
- [ ] Edge section hidden when edge disabled
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T13-018: Update About & Limitations for v2
**Status:** ⛔ superseded by T16-015
**Description:** Add the v2 non-claims (PRD_v2 list), the provisional-vs-final explanation, what does *not* alert, and 'O-RAN, iOS, SMS: not implemented'.
**Dependencies:** T13-011
**Acceptance Criteria:**
- [ ] All twelve non-claims present
- [ ] Text passes the forbidden-phrase lint (G24)
**Estimated Effort:** 30 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T13-019: Accessibility pass on Live pages
**Status:** ⛔ superseded by T16-016
**Description:** Verify: icon+word on every state/severity, chart text summaries, Pause toggle, keyboard order and focus, contrast tokens from DESIGN_v2; record Streamlit limitations (no live regions) in docs.
**Dependencies:** T13-012, T13-013, T13-014, T13-015, T13-016
**Acceptance Criteria:**
- [ ] Manual checklist completed and committed
- [ ] No colour-only signal remains
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Sushil

#### T13-020: Dashboard smoke tests with mocked live state
**Status:** ⛔ superseded by T17-009
**Description:** Using Streamlit's app-testing utility if it supports the pinned version (verify), otherwise test the snapshot→view-model functions directly: each connection state, provisional vs final, alert banner, stale view; plus a no-'caused'/'fixed' text assertion.
**Dependencies:** T13-019
**Acceptance Criteria:**
- [ ] Each DESIGN_v2 checklist item has a test or a documented manual check
- [ ] Tests run in CI
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Yashwant

---

## Phase 14: Security, Validation, Evaluation & Release
*Goal: Everything measured honestly, attacked, documented, and tagged v2.0.0.*

#### T14-001: Auth and abuse tests for ingest and live APIs
**Status:** ⬜
**Description:** Tests: wrong/missing token, replayed seq, oversize frame, malformed JSON, flood, second connection same `client_id`, non-loopback read request, token absent from logs (log-scan). Map to G19/G20.
**Dependencies:** T11-011, T11-014
**Acceptance Criteria:**
- [ ] Each abuse case in TECH_RULES_v2 has a test
- [ ] Log-scan test finds no token/URL
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Sushil

#### T14-002: Harden input handling with fuzz-style tests
**Status:** ⬜
**Description:** Property-based/fuzz tests over C7 messages (random types, huge strings, extreme seq jumps vs the cap, NaN/inf numbers, wrong dtypes); server must answer BAD_MESSAGE/SCHEMA_ERROR, never crash.
**Dependencies:** T11-011
**Acceptance Criteria:**
- [ ] No unhandled exception in 1,000 random messages
- [ ] `seq` jump cap enforced
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Sushil

#### T14-003: Test the bind and exposure policy
**Status:** ⬜
**Description:** Startup tests: default loopback; `--allow-lan` without token exits 2; read endpoints refuse non-loopback unless opted in; `/healthz` leaks nothing.
**Dependencies:** T11-019
**Acceptance Criteria:**
- [ ] All four cases automated
- [ ] Error messages tell the fix
**Estimated Effort:** 45 min
**Assigned To:** QA
**Owner:** Sushil

#### T14-004: Write the streaming security document
**Status:** ⬜
**Description:** `docs/streaming_security.md`: threat model for the local setup, token handling, bind policy, TLS options (verify uvicorn SSL options and Android cleartext rules in current docs), known limitations (single shared token, no per-device revocation).
**Dependencies:** T14-001, T14-002, T14-003
**Acceptance Criteria:**
- [ ] Limitations stated plainly
- [ ] Every claim about third-party behaviour verified or marked unverified
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T14-005: Privacy audit of payloads and logs
**Status:** ⬜
**Description:** Inspect C7/C8/C9 samples, server logs, `data/live/` files, webhook/email payloads and Android logs for tokens, hardware identifiers, location or PII; fix findings; record the checklist.
**Dependencies:** T11-011, T12-002
**Acceptance Criteria:**
- [ ] Checklist committed with results
- [ ] No PII or hardware IDs found, or fixed and re-checked
**Estimated Effort:** 45 min
**Assigned To:** QA
**Owner:** Sushil

#### T14-006: Implement guardrail tests G17–G26
**Status:** ⬜
**Description:** Replace each `xfail` stub in `tests/test_guardrails_v2.py` with a real test (or a documented manual-check entry where automation is impractical, e.g., OEM background behaviour). Includes forbidden-phrase lint for 'guaranteed/instant/zero latency' (G24) and webhook payload shape (G26).
**Dependencies:** T10-009, T11-006, T13-009, T14-001, T14-003
**Acceptance Criteria:**
- [ ] No xfail left unless explained in the docstring
- [ ] Every G17–G26 mapped in docs
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Yashwant

#### T14-007: Soak test
**Status:** ⬜
**Description:** 2 h replay at 1× and 20×; record RSS/CPU, queue sizes, drops, event counts; assert memory is bounded after warm-up (threshold set from a first baseline run and written down).
**Dependencies:** T11-017
**Acceptance Criteria:**
- [ ] Report in docs/results_v2.md with setup
- [ ] No crash; no monotonic memory growth
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T14-008: Latency benchmark
**Status:** ⬜
**Description:** Measure sample→published and, via the dashboard client, sample→visible at 1× replay on LAN/loopback; report p50/p95/max with machine, Python/Streamlit versions and refresh interval. Compare to the proposed 2 s p95 and state pass/fail honestly.
**Dependencies:** T17-007, T11-018
**Acceptance Criteria:**
- [ ] Setup fully described (G24)
- [ ] If the KPI fails, the 'revisit Streamlit' entry in docs/decisions.md is opened
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Sushil

#### T14-009: Recovery test matrix
**Status:** ⬜
**Description:** Automated/manual cases: Wi-Fi drop, server restart mid-session, dashboard restart, phone sleep, duplicate seq, slow subscriber; record observed behaviour and any data loss counts.
**Dependencies:** T12-004, T11-012
**Acceptance Criteria:**
- [ ] Each case has expected/observed result
- [ ] Loss, if any, is counted and explained
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Sushil

#### T14-010: Live-vs-batch-on-capture equivalence on real data
**Status:** ⬜
**Description:** Take the real session from T12-010: run `python -m pipelines.run_pipeline --input <capture dir>` on the live capture CSV and compare to live outputs (flags, type, severity, scores within tolerance).
**Dependencies:** T12-010, T11-006
**Acceptance Criteria:**
- [ ] Zero flag differences or each difference explained
- [ ] Result in docs/results_v2.md
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T14-011: Evaluate streaming detection latency
**Status:** ⬜
**Description:** Replay the v1 labelled windows; for baseline and IF measure delay from labelled event start to first flag, first provisional event and first alert; report counts and uncertainty; no tuning on evaluation labels.
**Dependencies:** T13-008, T11-015
**Acceptance Criteria:**
- [ ] Both methods reported with label counts
- [ ] Small-sample caveats stated
- [ ] States plainly if IF does not beat baseline
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Yashwant

#### T14-012: Evaluate alert quality and volume
**Status:** ⬜
**Description:** Using the v1 labelled events: alert precision/recall, alerts per hour on normal-condition data, list of false alerts with causes (extends `docs/false_positive_analysis.md` style). Verify the v1 FPR figure in `docs/results.md` before citing it.
**Dependencies:** T13-008, T14-011
**Acceptance Criteria:**
- [ ] Counts shown next to every rate
- [ ] Every false alert investigated or flagged as unexplained
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Sushil

#### T14-013: Write the streaming protocol document
**Status:** ⬜
**Description:** `docs/streaming_protocol.md`: C7/C8/C9 with examples, error codes, resume/ack semantics, limits, versioning rules; examples generated from the golden files.
**Dependencies:** T14-009
**Acceptance Criteria:**
- [ ] Examples are included from tests/fixtures/stream
- [ ] Doc and schema drift check pass
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T14-014: Write the streaming architecture document
**Status:** ⬜
**Description:** `docs/streaming_architecture.md`: diagrams (mermaid), module responsibilities, data flow, parity design, decision record summary; update `docs/architecture.md` to link it.
**Dependencies:** T14-009
**Acceptance Criteria:**
- [ ] Diagrams render
- [ ] Agent layer described as unchanged
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T14-015: Update README with a live quickstart
**Status:** ⬜
**Description:** Add: link options, `make token`, `make serve`, `make dashboard`, `make replay`, phone setup, the full non-claims list, status table updated only for tested items (G16).
**Dependencies:** T14-013, T14-014
**Acceptance Criteria:**
- [ ] A teammate follows it from a fresh clone
- [ ] No item marked ✅ without a passing test
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Sushil

#### T14-016: Update limitations_and_future_scope.md
**Status:** ⬜
**Description:** Move implemented items out of Future Scope, keep O-RAN, iOS, SMS, mobility-aware, supervised/LSTM labelled NOT IMPLEMENTED; add the new limitations (measurement-perturbation findings, OEM background limits, single-token security).
**Dependencies:** T12-009, T14-004
**Acceptance Criteria:**
- [ ] Nothing unimplemented described as done
- [ ] New limitations cite the experiments/tests
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T14-017: Write docs/results_v2.md
**Status:** ⬜
**Description:** Consolidate T12-009, T12-010, T14-007, T14-008, T14-010, T14-011, T14-012 with setups, counts and caveats; state failures plainly.
**Dependencies:** T14-007, T14-008, T14-010, T14-011, T14-012
**Acceptance Criteria:**
- [ ] Every number has its setup and sample count
- [ ] No latency guarantee language (G24)
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T14-018: Definition-of-Done v2 audit
**Status:** ⬜
**Description:** `docs/definition_of_done_v2.md`: each PRD_v2 Must Have, KPI and G17–G26 with an evidence link (test, doc, or measurement) or an honest ❌.
**Dependencies:** T14-006, T14-017, T14-015, T14-016, T16-019, T17-009, T18-014, T19-014
**Acceptance Criteria:**
- [ ] No item without evidence or an explicit gap
- [ ] Both authors sign off in the PR
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Sushil

#### T14-019: Fresh-clone verification and v2.0.0 tag
**Status:** ⬜
**Description:** On a clean clone on both machines: `make setup`, `make demo-live` (replay), then a real-phone session; fix blockers; tag `v2.0.0` only after T14-018 passes.
**Dependencies:** T14-018
**Acceptance Criteria:**
- [ ] Both machines pass
- [ ] Tag created from main with green CI
**Estimated Effort:** 60 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T14-020: Update slides and the demo script
**Status:** ⬜
**Description:** Add live-path slides, a 5-minute demo script with a pre-recorded fallback (replay at 5×), and the v2 non-claims slide.
**Dependencies:** T14-017
**Acceptance Criteria:**
- [ ] Fallback demo needs no phone
- [ ] Non-claims slide present
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

---

## Phase 15: Should-Have Extras & Research Notes
*Goal: Optional work after Phase 14 is accepted; none of it may be claimed as implemented without tests.*

#### T15-001: HTTP batch ingest fallback
**Status:** ⬜ · ➕ Optional
**Description:** `POST /api/v1/ingest/batch` accepting an array of C7 `sample` objects using the same validation, auth, dedupe and rate limits; Android flushes via it when WebSocket upgrade fails.
**Dependencies:** T14-019
**Acceptance Criteria:**
- [ ] Same golden examples validate
- [ ] Duplicates ignored (G19)
- [ ] Auth required
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T15-002: Per-role tokens (ingest vs read)
**Status:** ⛔ superseded by T18-002
**Description:** Separate `NADS_INGEST_TOKEN` and `NADS_VIEW_TOKEN`; update docs and tests; document that revocation is still manual.
**Dependencies:** T14-019
**Acceptance Criteria:**
- [ ] Ingest token cannot read; view token cannot ingest
- [ ] Docs updated
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T15-003: Test that the optional LLM has no effect on the live path (G13)
**Status:** ⬜ · ➕ Optional
**Description:** With `NADS_USE_LLM` unset and no network the live path works; with it set (v1 `agents/llm_explainer.py`, T9-001/T9-002, exists) flags, types, severities and alert decisions are byte-identical.
**Dependencies:** T14-006
**Acceptance Criteria:**
- [ ] Test passes both ways
- [ ] Alert text always from the template renderer
**Estimated Effort:** 45 min
**Assigned To:** QA
**Owner:** Sushil

#### T15-004: O-RAN feasibility note (no code)
**Status:** ⬜ · ➕ Optional
**Description:** `docs/oran_feasibility_note.md`: what UE-side measurements could and could not inform an operator-side RIC, what access would be needed, why this project cannot implement it. Verify every statement against current primary sources or mark it unverified; state 'NOT IMPLEMENTED'.
**Dependencies:** T14-019
**Acceptance Criteria:**
- [ ] No implementation claims
- [ ] Unverified statements marked
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Sushil

#### T15-005: Refresh the iOS collection note (no code)
**Status:** ⬜ · ➕ Optional
**Description:** Re-check current iOS telephony API restrictions from Apple's documentation and update the v1 note (T9-006, `docs/ios_collection_note.md`) with dated, sourced statements; state 'NOT IMPLEMENTED'.
**Dependencies:** T14-019
**Acceptance Criteria:**
- [ ] Each claim cites a source or is marked unverified
- [ ] Date of check recorded
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

---
## Appendix

### Critical Path
> Longest dependency chain to the `v2.0.0` tag: **20.0 h of sequential work** (planning estimate; real elapsed time is longer because of reviews and phone/device logistics). Everything else can slip without delaying release; these cannot.

1. T10-001 — Amend project-overview.md and extend docs/decisions.md
2. T10-004 — Add streaming constants to ml/config.py
3. T10-005 — Implement C7 ingest models in streaming/schema.py
4. T11-002 — Implement the per-session buffer
5. T11-004 — Apply the batch session-gap rule in the stream
6. T11-005 — Implement StreamingEngine.process()
7. T11-007 — Implement the EventTracker
8. T11-008 — Run the unchanged agents on event open/change/close
9. T11-014 — Implement WS /api/v1/live and the REST endpoints
10. T13-010 — Build the live client and connection state machine
11. T13-011 — Add the Mode switch and connection chip
12. T13-017 — Build Stream Health (L5)
13. T14-008 — Latency benchmark
14. T14-017 — Write docs/results_v2.md
15. T14-018 — Definition-of-Done v2 audit
16. T14-019 — Fresh-clone verification and v2.0.0 tag

### Parallelizable Tasks
> Safe to run simultaneously across the two people / agents once the stated dependency is met.
- **After T10-001 + T10-003:** T10-004 (S), T10-009 (Y), T10-010 (Y), T10-011 (S), T10-012 (Y), T10-013 (Y) are independent of each other.
- **After T10-005..T10-008 (contracts merged):** server track (T11-002, T11-003, T11-009, T11-010, T11-013) and Android track (T12-001) start together. This is the main parallel split of v2.
- **After T11-011:** T11-015 (replay tool, Y), T11-012 (S), T12-002 (Y) in parallel.
- **After T11-014:** the whole Live dashboard (T13-010 → T13-011, then T13-012, T13-013, T13-014, T13-015, T13-017 in parallel) is independent of Android work.
- **After T13-003:** T13-004, T13-005, T13-006 (three channels) are independent.
- **Edge track** (T12-011 → T12-018) runs in parallel with Phase 13 and can be abandoned without affecting anything else.
- **Phase 14 tests** T14-001, T14-002, T14-003, T14-005 can all run in parallel once ingest exists.
- Contract PRs (T10-005..T10-007) need both authors' approval, so schedule them early in a shared session.

### Risk Register
| Risk | Affected Tasks | Likelihood | Mitigation |
|------|---------------|-----------|-----------|
| Stream path drifts from batch results (duplicated logic) | T11-003..T11-007, T11-006 | Medium | One implementation (call `ml/*`); G17 parity test in CI; fail the build on any flag difference |
| Android OEM background restrictions kill the app (Redmi/Xiaomi, some Samsung) | T12-005, T12-010, T14-009 | High | Foreground service + battery guidance; per-device manual test; document unsupported behaviour; replay fallback for demos |
| Streaming perturbs the very radio being measured | T12-009, docs/decisions.md | Medium (hypothesis, unverified) | Prefer USB `adb reverse` / Wi-Fi; run the experiment; never stream over cellular in v2 |
| Alert fatigue — v1 reported a very high false-positive rate for the global IF threshold (73.55% in `docs/results.md` and `limitations_and_future_scope.md`) | T13-001, T13-008, T14-012 | High | Evidence-gated policy (G21), persistence/severity gates, cooldown, thresholds tuned on non-evaluation data, ML-only flags never alert |
| Streamlit cannot meet the latency/smoothness KPI (rerun model, thread handling) | T13-010, T13-012, T14-008 | Medium | REST-polling fallback; accept 1–2 s refresh; open the 'revisit front end' decision only if T14-008 fails |
| Edge IF parity cannot be reached on Android | T12-011..T12-018 | Medium | Time-boxed spike, strict tolerance, clean no-go; no other task depends on edge |
| Ingest endpoint exposed on a LAN | T11-019, T14-001..T14-004 | Medium | Loopback default, token required for LAN, size/rate limits, optional TLS docs, abuse tests |
| Live capture quality (gaps, clock skew) pollutes later evaluation | T11-009, T11-020, T14-010 | Medium | Live files labelled and hashed; replay never counted as new real data; skew flagged not fixed |
| v1 sentinel list (`-1`, `99`, `999`) may erase legitimate values (e.g. SINR −1 dB) if applied to every column; the live path inherits it through G17 | T10-015, T11-003 | Low–Medium (unverified) | Confirm per-column behaviour (T10-015) before parity work; any fix is a separate v1 PR, never a silent live-only change |
| v1 'no network imports in core pipeline' test blocks `streaming/` | T10-014 | Medium | Re-scope that test to `ml/` and `agents/` only |
| Scope creep into O-RAN/iOS/SMS code | Phase 15 | Medium | Research notes only; non-claims list; scope table in PRD_v2 |
| Overview contradictions left unresolved | T10-001 | Low–Medium | Amend overview first; both authors approve |
| Two-person merge conflicts around `ml/config.py` and `streaming/schema.py` | Phase 10–11 | Medium | Contracts first; small PRs; mutual review; owner-swap rule if blocked > 2 days |
| Over-claiming 'real-time' | T13-018, T14-015, T14-017, T14-018 | Medium | G24; docs lint for 'guaranteed/instant'; latency reported with setup |

### Recommended Build Order
> Optimal sequence for the two of you (S = Sushil, Y = Yashwant).
1. **Kickoff session (both):** T10-001 → agree amendments; split contract work (T10-005..T10-007 S, T10-008 Y).
2. Phase 10 remainder in parallel (T10-002, T10-003, T10-004, T10-009..T10-015 (T10-015 is a ⚠️ UNCLEAR check — answer it before T11-003)).
3. **Server track (S first, then Y):** T11-001 → T11-010 → T11-011 → T11-012 → T11-014; Y: T11-002 → T11-003 → T11-004 → T11-005 → **T11-006 (parity — do not move on without it)** → T11-015 (replay tool).
4. **Android track (Y):** T12-001 → T12-002 → T12-003 → T12-004 → T12-007 → T12-005 → T12-006 → T12-008; run T12-009 (perturbation) as soon as the client streams.
5. **Alerting (S):** T13-001 → T13-002 → T13-003 → T13-007 (S also T13-004 webhook; Y: T13-005 email, T13-006 phone channel).
6. **Live dashboard:** S: T13-010; Y: T13-011 (extends his v1 sidebar); then S: T13-012..T13-017 → T13-019; Y: T13-020.
7. **Edge decision gate (Y):** T12-011 — only after the core path works. If go, T12-012..T12-018; if no-go, mark the edge tasks ⛔ (`dropped: <reason>`) and hand ~2.5 h of Phase 14 docs/tests from S to Y to rebalance.
8. Real-device validation: T12-010, then T14-010.
9. Phase 14 evaluation and hardening: T14-001..T14-012 (parallel), docs T14-013..T14-017, audit T14-018, tag T14-019.
10. Phase 15 only after the tag.

### Workload split (generated, effort in hours)
| Phase | Yashwant | Sushil |
|---|---|---|
| 10. v2 Foundation & Contracts | 6.00 h | 6.00 h |
| 11. Streaming Server Core | 9.75 h | 13.25 h |
| 12. Android Streaming Client & Edge Inference | 22.25 h | 0.75 h |
| 13. Live Dashboard & Alerting | 5.00 h | 17.75 h |
| 14. Security, Validation, Evaluation & Release | 9.75 h | 11.75 h |
| 15. Should-Have Extras & Research Notes (optional) | 2.50 h | 3.25 h |
| **v2 MVP total (Phases 10–14, edge included)** | **52.75 h** (48 tasks) | **49.50 h** (46 tasks) |
| of which edge inference (T12-011..T12-018, gated) | 9.25 h | 0.75 h |
| **v2 MVP if edge is dropped** | **43.50 h** | **48.75 h** |

Human-only tasks (phone sessions, device checks) are included. Estimates are planning figures, not measurements; v1 actuals were not available to calibrate them. Re-balance by swapping task owners if one person falls behind; keep totals within ~10% of each other.

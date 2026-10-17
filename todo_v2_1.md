# todo_v2_1.md — 5G-NADS v2.1: React Frontend, Hosted Pairing, Android UI Refresh
> Generated from: `docs/planning/V2_1_DELTA.md` + the inventories (`dashboard_inventory.md`, `android_inventory.md`, `demo_data_sizes.md`) + `todo_v2.md` / `TECH_RULES_v2.md`.
> **Adds Phases 16–19** to `todo_v2.md` and **supersedes** some of its tasks. Same conventions as `todo_v2.md` §0 (statuses ⬜🔄✅⛔, tags 🧑 ➕ ⚠️, protocol for AI agents, one owner per module, tasks 15–90 min). Last updated 2026-10-09; no calendar dates; effort = planning estimates, not measurements.
> **Everything marked "verify" must be checked against current official docs before coding** (Android service types for `targetSdk 37`, Azure ingress/WebSocket/billing behaviour, library versions, AndroidX security APIs).
> Extra protocol rules for v2.1: (1) the frontend never computes scores, flags, events, transitions or diagnoses (G30); (2) never ship raw cell IDs in a public bundle (G27); (3) never start streaming without the consent screen (G28); (4) never persist live sessions on the public server (G29); (5) the Android CSV path must stay byte-identical for fixed inputs (G32). Do not edit the Streamlit dashboard except for bug fixes (it is the frozen v1 result).

## Milestone mapping (use when merging into ROADMAP at T16-000)
| Milestone | Phases | Outcome |
|---|---|---|
| M5 | 10–11 | unchanged (foundation, streaming server core, parity) |
| **M6a — Public demo** | 16 (+ T18-007..T18-010) | **First shippable result:** React dashboard live at a public link (GitHub Pages/Vercel), no backend, anonymised bundle. Can start immediately after T10-001 and T16-000, in parallel with M5. |
| M6b — Phone & live UI | 12 (non-superseded tasks), 17, 19, 13 (alert engine tasks only) | Android refresh, streaming client, React live mode |
| **M6c — Hosted live** | 18 | Pair a phone to the website; container deployment; privacy and abuse controls |
| M7 | 14 | Hardening, evaluation, release; `T14-018` gains four dependencies (below) |
| M8 | 15 (+ nothing else) | Optional extras; `T15-002` superseded |

## Superseded tasks in todo_v2.md (mark ⛔ `superseded by …` in T16-000)
| Old task | Replaced by |
|---|---|
| T12-001 Android settings | T19-008 |
| T12-005 Foreground service | T19-009 |
| T12-006 Status strip | T19-006 |
| T13-010 Live client (Streamlit) | T17-001 |
| T13-011 Mode switch + chip | T17-002, T17-010 |
| T13-012 Live Overview | T17-003 |
| T13-013 Live Signals | T17-004 |
| T13-014 Live Cells | T17-005 |
| T13-015 Events panel | T17-006 |
| T13-016 Alerts panel | T17-006 |
| T13-017 Stream Health | T17-007 |
| T13-018 About update | T16-015 |
| T13-019 Accessibility | T16-016 |
| T13-020 Dashboard smoke tests | T17-009 |
| T15-002 Per-role tokens | T18-002 (per-session tokens) |

**Dependency patches** (apply in `todo_v2.md`): wherever an active task depended on a superseded one, use the replacement above (e.g. `T12-010` → T19-009, T19-006; `T12-018` → T19-006; `T12-002` → T19-008; `T14-008` → T17-007). Add to `T14-018`: **T16-019, T17-009, T18-014, T19-014**. `T13-001`…`T13-009` (alert engine) are kept. Phase 15 tasks stay optional.

---


## Phase 16: React Foundation & Static Demo (deployment mode 1)
*Goal: A public-link React dashboard with parity to the six Streamlit pages, fed by a precomputed, anonymised data bundle — no backend, no phone.*

#### T16-000: Merge V2_1_DELTA into the v2 docs and amend the overview
**Status:** ✅
**Description:** Fold `V2_1_DELTA.md` into `PRD_v2`, `DESIGN_v2`, `TECH_RULES_v2`, `ROADMAP.md`, `todo_v2.md`; add overview amendments A4–A6 beside A1–A3 (extend `T10-001`'s PR or a follow-up); add decisions to `docs/decisions.md`; mark superseded tasks ⛔ (`superseded by T16-…`) and apply the dependency patches listed in this file's Appendix; add G27–G32 and contracts C10/C11 to TECH_RULES_v2; archive the delta file.
**Dependencies:** T10-001
**Acceptance Criteria:**
- [x] Both authors approve
- [x] No superseded task is a dependency of an active task
- [x] G27–G32 and C10/C11 present in TECH_RULES_v2
- [x] ROADMAP milestone table matches this file
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T16-001: Spike: choose the chart library and styling approach
**Status:** ✅
**Description:** Time-box 90 min: build one 4-panel stacked time series (5.5 k points, shared x, zoom/pan, red × markers, gap breaks, table fallback) with 2 candidate libraries; measure bundle size and interaction smoothness; pick one and record the decision. Default styling: CSS variables for DESIGN tokens (+ Tailwind if preferred). Verify library licences and current versions.
**Dependencies:** T16-000
**Acceptance Criteria:**
- [x] Decision and measurements in docs/decisions.md
- [x] Chosen library supports gap breaks and marker overlays
- [x] Bundle size noted
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-002: Write the demo-bundle builder (Contract C11)
**Status:** ✅
**Description:** `scripts/build_demo_bundle.py --source processed|sample --out frontend/public/demo-bundle.json`: assemble sessions, columnar samples (columns used by the dashboard per `dashboard_inventory.md` §4), **precomputed transitions** (move the logic now living in `3_Cells_And_Network.py` L42–78 into a tested helper; do not edit the Streamlit page), events from `events_diagnosed.json`, quality block from `preprocess_log.json` + missing/CSI/deployment-mode stats, model meta. Deterministic output; gzip-friendly.
**Dependencies:** T16-000
**Acceptance Criteria:**
- [x] Bundle < 1 MB uncompressed for sample (33.7 KB) and < 5 MB for processed (3.08 MB) (report sizes)
- [x] Running twice gives identical bytes
- [x] Transition helper has unit tests and a negative case (no change → no event)
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T16-003: Add cell-ID anonymisation and privacy flags (G27)
**Status:** ✅
**Description:** Hash `nci`/`pci` with a per-bundle salt for public bundles (stable within the bundle; `pci_changed`/`nci_changed` preserved); label values 'Cell A…' in a lookup; `--raw-cell-ids` allowed only without `--public`; record `privacy` block in the bundle; never ship `data/raw`.
**Dependencies:** T16-002
**Acceptance Criteria:**
- [x] Public bundle contains no raw nci/pci (grep test)
- [x] Change flags identical to unhashed bundle
- [x] `--public --raw-cell-ids` exits 2 with a fix hint
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Yashwant

#### T16-004: Test the bundle against its source files
**Status:** ✅
**Description:** Tests: row counts per device/session equal `scores.csv`; sample of 50 values equal; event count and ids equal `events_diagnosed.json`; quality counts equal `preprocess_log.json`; schema/version field present.
**Dependencies:** T16-003
**Acceptance Criteria:**
- [x] Tests run in CI
- [x] A deliberately altered value fails the test
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T16-005: Generate TypeScript types from the JSON Schemas
**Status:** ✅
**Description:** Extend `scripts/export_contract_examples.py` to emit JSON Schema for C11 (and C8/C9/C10 as they land); generate TS types into `frontend/src/types/` with a check that generated files are current (verify the generator tool and its licence).
**Dependencies:** T16-004, T10-008
**Acceptance Criteria:**
- [x] Types compile
- [x] CI fails if schema and types drift
**Estimated Effort:** 45 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-006: Scaffold the frontend project
**Status:** ✅
**Description:** `frontend/` with Vite + React + TypeScript, router (hash mode), lint/format, Vitest, Playwright config, `npm` scripts, `.gitignore`, CI job running lint + test + build (Node version pinned; verify current LTS).
**Dependencies:** T16-001
**Acceptance Criteria:**
- [x] `npm run build` produces static files
- [x] CI job green
- [x] README section 'run the frontend'
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-007: Implement design tokens, theme and app shell
**Status:** ✅
**Description:** DESIGN tokens as CSS variables (light + dark); app shell: single brand header (fixes duplicated sidebar title), nav for six pages, filters area, footer with version/model_version and the research-prototype notice; keyboard-reachable; no 'Deploy' chrome.
**Dependencies:** T16-006
**Acceptance Criteria:**
- [x] Light/dark switch persists
- [x] Contrast of text tokens ≥ 4.5:1 (checked)
- [x] Footer notice present on every page (G31)
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-008: Data layer: bundle loader, version check, filters, global state
**Status:** ✅
**Description:** Load and validate the bundle (version, required keys), expose typed selectors for device/operator/session, current sample, events, transitions; error state with fix text for a missing/invalid bundle (no stack traces).
**Dependencies:** T16-005, T16-007
**Acceptance Criteria:**
- [x] Invalid bundle shows a readable error
- [x] Selectors unit-tested
- [x] No score/flag is recomputed (G30)
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-009: Build the Overview page
**Status:** ✅
**Description:** Status banner (anomaly rule from `1_Overview.py` L47–52), network & device card (UNKNOWN shown as 'Unknown (not exposed by this device)'), six metric cards with deltas that never truncate, score block (baseline and IF separate, ML-only distinct), event label, diagnosis/evidence/recommendation, empty state; caption without 'Real-time'.
**Dependencies:** T16-008
**Acceptance Criteria:**
- [x] Values for 5 sample rows equal the Streamlit page
- [x] No ellipsis truncation at 1280 px and 375 px
- [x] `—` shown for missing, never 0
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-010: Build the replay player
**Status:** ✅
**Description:** Play/pause, speed 1×/5×/20×, scrubber; current sample drives Overview; keyboard operable; pauses at end.
**Dependencies:** T16-008
**Acceptance Criteria:**
- [x] Speed changes take effect immediately
- [x] Scrubber and keyboard arrows move one sample
- [x] State survives page navigation
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-011: Build Signal Explorer
**Status:** ✅
**Description:** Four stacked panels (RSRP, RSRQ, SINR, IF score with 0.60 line), flag overlay options (both / baseline / IF / hide), rolling-mean toggle, one-session-at-a-time with session tabs and prev/next plus an all-sessions overview strip, lines break at gaps and NA, zoom/pan, summary sentence, data-table expander.
**Dependencies:** T16-008
**Acceptance Criteria:**
- [x] No line bridges two sessions or an NA gap
- [x] Anomaly markers use × shape plus tooltip text
- [x] Summary stats equal the Streamlit page's min/max/mean
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-012: Build Cells & Network
**Status:** ⬜
**Description:** PCI/NCI/NRARFCN step charts per session (NCI/PCI as categorical labels), transition table from the bundle, the 'cell change is normal behaviour' note.
**Dependencies:** T16-008
**Acceptance Criteria:**
- [ ] Transition count equals bundle `transitions`
- [ ] No client-side transition detection (G30)
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Yashwant

#### T16-013: Build Events & Diagnosis
**Status:** ✅
**Description:** Virtualised events table (365+ rows), type/severity filters, selected-event agent cards, event-window chart, JSON download; time labelled 'device local time (no timezone recorded)'.
**Dependencies:** T16-008
**Acceptance Criteria:**
- [x] Filter counts equal the Streamlit page
- [x] Downloaded JSON validates against the C5 shape
- [x] Table stays responsive with 1,000 rows
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T16-014: Build Data Quality
**Status:** ⬜
**Description:** Missing-value table per device/column, CSI availability, deployment-mode distribution with the UNKNOWN note, raw vs processed row counts with the reason rows were dropped, synthetic-data banner.
**Dependencies:** T16-008
**Acceptance Criteria:**
- [ ] Numbers equal the Streamlit page (e.g. Redmi 3,756 processed)
- [ ] UNKNOWN copy rule shown verbatim
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Yashwant

#### T16-015: Build About & Limitations and the privacy note
**Status:** ⬜
**Description:** Description, v2 non-claims (12 items from PRD_v2), research-prototype statement, dataset summary (two phones, one operator), model metadata, privacy note on cell identifiers, links.
**Dependencies:** T16-007
**Acceptance Criteria:**
- [ ] No 'real-time' claim anywhere
- [ ] All non-claims present
**Estimated Effort:** 45 min
**Assigned To:** Frontend
**Owner:** Yashwant

#### T16-016: Accessibility pass
**Status:** ⬜
**Description:** Keyboard order and focus, ARIA labels, `aria-live` for state changes, one-sentence chart summaries, colour not the only signal, reduced-motion, contrast re-check; record results.
**Dependencies:** T16-009, T16-011, T16-012, T16-013, T16-014
**Acceptance Criteria:**
- [ ] Checklist committed
- [ ] Automated axe-style scan has no serious issues (tool to be chosen and verified)
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T16-017: Component tests for every page
**Status:** ⬜
**Description:** Vitest + Testing Library against a small bundle fixture: each page renders, key values appear, empty/error states, filters, replay player.
**Dependencies:** T16-009, T16-011, T16-012, T16-013, T16-014
**Acceptance Criteria:**
- [ ] Each page has ≥3 tests
- [ ] Coverage on `frontend/src` ≥ 70% (proposed)
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Sushil

#### T16-018: Data-parity test (frontend vs Python)
**Status:** ✅
**Description:** Test that numbers rendered for fixed samples/events equal the Python outputs (bundle values vs `scores.csv` rows, event counts, quality counts).
**Dependencies:** T16-004, T16-013
**Acceptance Criteria:**
- [x] 10 samples and 5 events checked field by field
- [x] Fails if the builder changes a value
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Sushil

#### T16-019: Playwright e2e and screenshots
**Status:** ⬜
**Description:** Smoke path through all six pages in light and dark, 1280 and 375 px; save screenshots to `docs/screens_react/`; compare visually with the Streamlit screenshots for content parity (manual sign-off).
**Dependencies:** T16-016
**Acceptance Criteria:**
- [ ] e2e runs in CI
- [ ] Screenshots committed
- [ ] Reviewer sign-off recorded
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Yashwant

#### T16-020: No-logic lint (G30)
**Status:** ✅
**Description:** A test that fails if frontend source contains score/threshold/z-score/event-grouping computations (denylist of identifiers + code review checklist); document what is allowed (formatting, filtering, sorting, plotting).
**Dependencies:** T16-006
**Acceptance Criteria:**
- [x] Test fails when a forbidden identifier is added
- [x] Allowed operations documented
**Estimated Effort:** 45 min
**Assigned To:** QA
**Owner:** Sushil

---

## Phase 17: React Live Mode
*Goal: Live and recorded data flow through the same React components, with honest connection state, alerts and pairing.*

#### T17-001: Live data source and connection state machine
**Status:** ✅
**Description:** WebSocket client with first-frame `auth` message and ticket, REST resync on `dropped`/reconnect, state machine LIVE/STALE/RECONNECTING/DISCONNECTED/WAITING/REPLAY, backoff, typed events from C8.
**Dependencies:** T11-014, T18-003, T16-008
**Acceptance Criteria:**
- [x] Reconnect resyncs without duplicates
- [x] Ticket never appears in a URL
- [x] Unit tests with a fake socket
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T17-002: Connection chip and live announcements
**Status:** ✅
**Description:** Chip with state, icon, word and sample age on every page; `aria-live="polite"` announcements on state change (debounced); alert announcements.
**Dependencies:** T17-001
**Acceptance Criteria:**
- [x] Chip text not colour-only
- [x] Flapping link announces at most once per 30 s
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T17-003: Live Overview
**Status:** ✅
**Description:** Reuse Overview with PROVISIONAL/FINAL badge, STALE 'showing last known values', ML-only line, alert banner with Acknowledge.
**Dependencies:** T17-001, T16-009
**Acceptance Criteria:**
- [x] All six states rendered from mock data
- [x] Provisional and final events visibly distinct
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T17-004: Live Signals
**Status:** ✅
**Description:** Rolling 5/15/60 min window, gap bands, no interpolation, pause/resume, table fallback.
**Dependencies:** T17-001, T16-011
**Acceptance Criteria:**
- [x] No line crosses a gap
- [x] Pause freezes the view without losing data
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T17-005: Live Cells & Network
**Status:** ⬜
**Description:** Windowed step charts and transitions as events arrive (transitions computed by the server in live mode).
**Dependencies:** T17-001, T16-012
**Acceptance Criteria:**
- [ ] No client-side transition detection (G30)
**Estimated Effort:** 45 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T17-006: Live Events & Alerts
**Status:** ✅
**Description:** Events table with status and 'alerted? (reason)', agent cards, alerts table, per-channel status, acknowledge via API.
**Dependencies:** T17-001, T16-013, T13-007
**Acceptance Criteria:**
- [x] Reason strings are the five fixed values
- [x] Ack persists across reload
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T17-007: Stream Health page
**Status:** ✅
**Description:** Latency percentiles with the 'no latency guarantee' footnote, gaps, drops, queue depth, clock skew, model/hash, edge divergence (only if enabled).
**Dependencies:** T17-001, T11-018
**Acceptance Criteria:**
- [x] Numbers shown exactly as served by /metrics
- [x] Footnote present
**Estimated Effort:** 60 min
**Assigned To:** Frontend
**Owner:** Sushil

#### T17-008: Pairing panel
**Status:** ⬜
**Description:** Start session, show pairing code + QR with countdown, 'waiting for phone' state, session info, End session, Download CSV (C1 format built from received samples), consent/privacy text.
**Dependencies:** T17-001, T18-002
**Acceptance Criteria:**
- [ ] Expired code shows how to retry
- [ ] CSV equals samples received (header + row count)
**Estimated Effort:** 90 min
**Assigned To:** Frontend
**Owner:** Yashwant

#### T17-009: Live-mode tests with a mock server
**Status:** ⬜
**Description:** Vitest/Playwright against a mock WebSocket server: every connection state, provisional→final, alert + ack, dropped→resync, auth failure.
**Dependencies:** T17-002, T17-006, T17-007, T17-008
**Acceptance Criteria:**
- [ ] Each state has a test
- [ ] Auth failure shows a clear message
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Yashwant

#### T17-010: Mode switch and empty/error states
**Status:** ⬜
**Description:** Demo ⇄ Live switch, clear labels ('Recorded demo data' vs 'Live'), unreachable-server and no-session states with fix text.
**Dependencies:** T17-001
**Acceptance Criteria:**
- [ ] Mode label always visible
- [ ] No stack traces shown
**Estimated Effort:** 45 min
**Assigned To:** Frontend
**Owner:** Yashwant

---

## Phase 18: Hosted Backend, Pairing & Deployment (deployment modes 2 and 3)
*Goal: One container serves the API and the React app; people can pair their own phone; free-tier deployments with limits and privacy controls.*

#### T18-001: Public-mode configuration and start-up guards
**Status:** ✅
**Description:** `NADS_MODE=local|public`; in public mode require `NADS_ALLOWED_ORIGINS`, force retention off, set caps; refuse to start (exit 2 with a fix hint) otherwise.
**Dependencies:** T11-010, T10-004
**Acceptance Criteria:**
- [x] Unsafe public config refuses to start
- [x] Mode printed in the start-up log without secrets
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T18-002: Pairing and session API (Contract C10)
**Status:** ✅
**Description:** `POST /api/v1/live-sessions`, `POST /api/v1/pair`, `POST /api/v1/live-sessions/{id}/ticket`, `DELETE /api/v1/live-sessions/{id}`; 8-char single-use pairing codes with 10 min TTL; per-session ingest token and viewer cookie; pydantic models + golden examples.
**Dependencies:** T18-001, T10-005, T11-011
**Acceptance Criteria:**
- [x] Code cannot be reused
- [x] Expired code rejected
- [x] Golden C10 examples committed
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Sushil

#### T18-003: Per-session WebSocket authentication
**Status:** ✅
**Description:** Ingest accepts only that session's bearer token; live endpoint requires the first-frame `auth` ticket within 5 s (single-use, 30 s); wrong or missing auth closes with the C7 code; no token in logs.
**Dependencies:** T18-002
**Acceptance Criteria:**
- [x] Token for session A cannot write to session B
- [x] Late or reused ticket rejected
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T18-004: Limits and abuse controls
**Status:** ✅
**Description:** `MAX_LIVE_SESSIONS`, per-IP session-creation and pairing-attempt rate limits, brute-force lockout on pairing codes, idle-session reaper (15 min), message/rate caps from C7.
**Dependencies:** T18-002
**Acceptance Criteria:**
- [x] Limits configurable in ml/config.py with origin comments
- [x] Lockout test passes
- [x] Reaper frees memory (test)
**Estimated Effort:** 90 min
**Assigned To:** Backend
**Owner:** Sushil

#### T18-005: Ephemeral session store and CSV export endpoint
**Status:** ✅
**Description:** In-memory bounded session buffers deleted at session end; `GET /api/v1/live-sessions/{id}/export.csv` (viewer auth) returns C1-format CSV; nothing written to disk when retention is off (G29).
**Dependencies:** T18-002, T11-009
**Acceptance Criteria:**
- [x] Disk scan after a session finds no live data in public mode
- [x] Export equals samples received
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T18-006: Origin and CORS enforcement
**Status:** ✅
**Description:** Allow-list applied to HTTP CORS and WebSocket `Origin` checks; deny by default in public mode.
**Dependencies:** T18-001
**Acceptance Criteria:**
- [x] Disallowed origin refused for REST and WS
- [x] Test covers both
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Sushil

#### T18-007: Dockerfile (multi-stage) and run scripts
**Status:** ⬜
**Description:** Build the SPA, then a slim Python image running FastAPI serving the SPA from static files plus API; non-root user; health check; `make docker-build docker-run`.
**Dependencies:** T16-006, T11-019
**Acceptance Criteria:**
- [ ] Image runs locally with `docker run`
- [ ] SPA and API both reachable on one port
- [ ] Image size reported
**Estimated Effort:** 90 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T18-008: CI for frontend and image
**Status:** ⬜
**Description:** GitHub Actions: frontend lint/test/build, Python tests, build the image (no push on PRs), cache dependencies.
**Dependencies:** T18-007, T10-010
**Acceptance Criteria:**
- [ ] CI green on a PR
- [ ] Build time noted
**Estimated Effort:** 60 min
**Assigned To:** DevOps
**Owner:** Sushil

#### T18-009: Deploy the static demo to GitHub Pages
**Status:** ⬜
**Description:** Vite `base` set for repo sub-path (`/5G-Network-Anomaly-Detection-System/`), `HashRouter` for client routing without 404s, Actions workflow publishing `frontend/dist` with the **public (hashed)** bundle; verify deep links and bundle loading under the sub-path. (Verified: GitHub Pages soft limit 100 GB/month bandwidth, 1 GB site storage; https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages#usage-limits, 2026-10-12).
**Dependencies:** T16-019, T10-010
**Acceptance Criteria:**
- [ ] Public URL loads all six pages
- [ ] Bundle contains no raw cell IDs (check in CI)
- [ ] Footer notice visible
**Estimated Effort:** 60 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T18-010: Deploy the static demo to Vercel
**Status:** ⬜ · ➕ Optional
**Description:** Project config, build command, same public bundle, preview deployments disabled for secrets-free repo; compare load time with GitHub Pages. (Verified: Vercel Hobby plan includes 100 GB bandwidth/month, non-commercial use only; https://vercel.com/docs/plans/hobby, 2026-10-12).
**Dependencies:** T18-009
**Acceptance Criteria:**
- [ ] Public URL works
- [ ] Differences from Pages noted
**Estimated Effort:** 45 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T18-011: Deploy the container to Azure Container Apps
**Status:** ⬜ · 🧑 Human-only
**Description:** Create the app with ingress `auto`/`http` and ≥1 replica, set env/secrets (`NADS_MODE=public`, allowed origins), confirm HTTPS/WSS. (Verified: Azure Container Apps monthly free grant is 180,000 vCPU-s / 360,000 GiB-s on Consumption plan; always-on 0.25 vCPU replica exceeds grant and accrues idle vCPU billing; WebSockets supported natively with ingress auto/http but require 15 s application heartbeats/pings to avoid proxy idle disconnects; https://azure.microsoft.com/en-us/pricing/details/container-apps/ and https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview, 2026-10-12). Record real cost after one week.
**Dependencies:** T18-007, T18-004, T18-006, T18-012
**Acceptance Criteria:**
- [ ] `wss://` handshake works from the browser
- [ ] Docs facts cited with date
- [ ] Cost note recorded
**Estimated Effort:** 90 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T18-012: Write docs/privacy.md and the shared consent text
**Status:** ✅
**Description:** What is collected, what is not, that cell identifiers can reveal approximate location, retention (none by default), platform logs outside our control, how to end a session; one text file reused by the website and the phone app.
**Dependencies:** T18-002
**Acceptance Criteria:**
- [x] Reviewed by both authors
- [x] Matches actual payload fields (C7)
**Estimated Effort:** 60 min
**Assigned To:** Backend
**Owner:** Sushil

#### T18-013: Security tests for pairing, tickets and limits
**Status:** ✅
**Description:** Abuse cases: guessing codes, reusing codes/tickets, cross-session token use, flooding session creation, oversize frames, wrong origin, token/code/query string absent from logs.
**Dependencies:** T18-004, T18-003
**Acceptance Criteria:**
- [x] Each case automated
- [x] Log-scan test passes
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Sushil

#### T18-014: Hosted end-to-end test
**Status:** ⬜ · 🧑 Human-only
**Description:** Browser → pair → phone (or replay tool) → hosted server → browser; measure latency (report setup, not a promise), force a reconnect, end the session, confirm data deleted; include a cellular-link run.
**Dependencies:** T18-011, T17-008, T11-015
**Acceptance Criteria:**
- [ ] Result recorded in docs/results_v2.md with setup
- [ ] Deleted-on-end verified
**Estimated Effort:** 90 min
**Assigned To:** QA
**Owner:** Yashwant

#### T18-015: Write docs/deployment.md
**Status:** ⬜
**Description:** Runbook for all three modes, env vars, free-tier caveats, rollback, cost watching, how to take the public site down.
**Dependencies:** T18-011
**Acceptance Criteria:**
- [ ] A teammate can redeploy from the doc
- [ ] Caveats cite dated sources
**Estimated Effort:** 45 min
**Assigned To:** Backend
**Owner:** Sushil

---

## Phase 19: Android UI Refresh, Pairing & Persistence
*Goal: A project-themed, accessible collector UI with pairing and consent, without changing what is collected.*

#### T19-001: Make the repo project the Android source of truth
**Status:** ⬜ · 🧑 Human-only
**Description:** Open `android-collector/5GNetworkTester` directly in Android Studio, build and install from it, delete the stale copy; add build/run steps to the README.
**Dependencies:** None
**Acceptance Criteria:**
- [ ] Build from repo works on both machines
- [ ] README steps verified
**Estimated Effort:** 30 min
**Assigned To:** DevOps
**Owner:** Yashwant

#### T19-002: Extract buildCsvRow() with a golden test (G32)
**Status:** ⬜
**Description:** Pull the row-building code out of `processNrCell()` into a pure function; unit-test fixed fake inputs against exact expected CSV lines (NA handling, timestamp format `dd-MM-yy HH:mm:ss`, 18 columns); no behaviour change.
**Dependencies:** T19-001
**Acceptance Criteria:**
- [ ] Golden tests pass before and after
- [ ] Header unchanged (C1)
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-003: Introduce UiState and decouple the UI
**Status:** ⬜
**Description:** Replace direct `outputText.text = …` writes in the collection path with publishing a `UiState`; keep `startCollection()`/`saveCsv()` behaviour.
**Dependencies:** T19-002
**Acceptance Criteria:**
- [ ] Golden tests still pass
- [ ] App behaves the same on a device (manual 2-min session)
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-004: Persist rows incrementally
**Status:** ⬜
**Description:** Append each row to the session file as collected (so a killed app keeps data); 'finish' closes and offers share; keep the file name pattern `5G_measurements_yyyyMMdd_HHmmss.csv`.
**Dependencies:** T19-003
**Acceptance Criteria:**
- [ ] Force-stop mid-session leaves a valid CSV
- [ ] Final file equals the old in-memory output for the same rows
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-005: Compose theme from the DESIGN tokens
**Status:** ⬜
**Description:** Use the existing `Color.kt/Theme.kt/Type.kt`: light and dark schemes, typography, spacing, status colours only for status; move strings to `strings.xml`.
**Dependencies:** T19-001
**Acceptance Criteria:**
- [ ] Dark theme follows system setting
- [ ] Contrast checked for text pairs
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-006: Home screen
**Status:** ⬜
**Description:** Logging and Streaming status (icon + word), RSRP/RSRQ/SINR cards, network-type chip, sample counter, Start/Stop; no anomaly verdicts on the phone (G9).
**Dependencies:** T19-003, T19-005
**Acceptance Criteria:**
- [ ] Touch targets ≥ 48 dp
- [ ] TalkBack labels on every control
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-007: Consent screen
**Status:** ⬜
**Description:** Shows what is sent and not sent using the shared text from `docs/privacy.md`; streaming cannot start until accepted (G28); acceptance stored locally with version.
**Dependencies:** T19-005, T18-012
**Acceptance Criteria:**
- [ ] No network call before consent
- [ ] Text matches docs/privacy.md
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-008: Pairing screen
**Status:** ⬜
**Description:** Enter code (QR optional), call the pair endpoint, show clear failure reasons (expired, wrong, server unreachable), store the ingest token in encrypted storage (verify current AndroidX/Keystore approach).
**Dependencies:** T19-005, T18-002
**Acceptance Criteria:**
- [ ] Token never logged
- [ ] Each failure case shows its own message
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-009: Foreground service for sampling and streaming
**Status:** ⬜ · 🧑 Human-only
**Description:** Move the 3 s loop into a foreground service with a notification; declare foreground service type (`dataSync` with `FOREGROUND_SERVICE_DATA_SYNC` or `specialUse`/`connectedDevice`; verified Android 15+ timeout rules enforce max 6 h in 24 h for `dataSync` with `Service.onTimeout(int, int)` callback where service must call `stopSelf()`, ref: https://developer.android.com/about/versions/15/behavior-changes-15#data-sync-timeout [verified 2026-10-12]); handle screen-off and OEM battery restrictions on Redmi and Samsung; screen-on fallback.
**Dependencies:** T19-004
**Acceptance Criteria:**
- [ ] 20 min screen-off session on each phone, or the failure documented per device
- [ ] Notification states what is running
- [ ] Service handles Android 15+ timeout callback cleanly
**Estimated Effort:** 90 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-010: Launcher icon, app title and strings
**Status:** ⬜
**Description:** New adaptive icon and 'NADS Collector' title keeping the same `applicationId`; all UI text in `strings.xml`.
**Dependencies:** T19-005
**Acceptance Criteria:**
- [ ] Installs over the old build without data loss
- [ ] No hard-coded UI strings remain
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Sushil

#### T19-011: Share/export the saved CSV
**Status:** ⬜ · ➕ Optional
**Description:** Android share intent for the finished file (FileProvider; verify current best practice).
**Dependencies:** T19-004
**Acceptance Criteria:**
- [ ] File shares to Drive/WhatsApp/email on a device
- [ ] Shared file equals the saved file
**Estimated Effort:** 45 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-012: INTERNET permission, WebSocket hook and debug-only localhost config
**Status:** ⬜
**Description:** Add `INTERNET`; wire the stream hook after a row is appended (one call, exceptions swallowed and counted); debug-build-only network-security config allowing `ws://localhost` for `adb reverse`; release uses `wss://` only. Reuses `T12-002`–`T12-004` for the client, queue and reconnect.
**Dependencies:** T19-002, T12-002
**Acceptance Criteria:**
- [ ] Release build rejects cleartext
- [ ] Collection unaffected when the server is down (G18)
**Estimated Effort:** 60 min
**Assigned To:** Full-stack (Android)
**Owner:** Yashwant

#### T19-013: Accessibility and theme check on both phones
**Status:** ⬜ · 🧑 Human-only
**Description:** TalkBack walkthrough, 200% font scale, dark mode, touch targets on the Redmi and the Samsung; fix findings.
**Dependencies:** T19-006, T19-007, T19-008
**Acceptance Criteria:**
- [ ] Checklist committed
- [ ] No clipped text at 200%
**Estimated Effort:** 45 min
**Assigned To:** QA
**Owner:** Sushil

#### T19-014: Before/after collection regression on a real phone
**Status:** ⬜ · 🧑 Human-only
**Description:** Record a 5-minute session on the old and new build under similar conditions; compare header, column count, sampling interval, NA/sentinel handling; record results.
**Dependencies:** T19-013, T19-004
**Acceptance Criteria:**
- [ ] Schema identical
- [ ] Interval ≈ 3 s on both builds
- [ ] Result stored in docs/results_v2.md
**Estimated Effort:** 60 min
**Assigned To:** QA
**Owner:** Sushil

---

## Appendix

### Critical path (merged graph, to the `v2.0.0` tag)
About **20.75 h** of sequential work (planning estimate): T10-001 → T10-004 → T10-005 → T11-002 → T11-004 → T11-005 → T11-011 → T18-002 → T19-008 → T12-002 → T12-003 → T12-004 → T14-009 → T14-013 → T14-015 → T14-018 → T14-019.

> It runs through pairing (T18-002) and the Android client because the hosted flow needs both ends. Anything off this chain can slip without delaying release.

### Workload split (hours; superseded tasks excluded; Phase 15 excluded)
| Scope | Yashwant | Sushil |
|---|---|---|
| Phase 10 — Foundation & Contracts | 6.00 h | 6.00 h |
| Phase 11 — Streaming Server Core | 9.75 h | 13.25 h |
| Phase 12 — Android streaming + edge (minus superseded) | 18.50 h | 0.75 h |
| Phase 13 — Alert engine (minus superseded Streamlit tasks) | 2.50 h | 6.75 h |
| Phase 14 — Security, Validation, Release | 9.75 h | 11.75 h |
| Phase 16 — React Foundation & Static Demo | 9.25 h | 14.50 h |
| Phase 17 — React Live Mode | 3.75 h | 7.75 h |
| Phase 18 — Hosted Backend, Pairing & Deployment | 6.25 h | 11.00 h |
| Phase 19 — Android UI Refresh, Pairing & Persistence | 11.75 h | 2.75 h |
| **Total, edge included** | **77.50 h** (71 tasks) | **74.50 h** (69 tasks) |
| of which optional edge inference (T12-011..T12-018) | 9.25 h | 0.75 h |
| **Total, edge dropped** | **68.25 h** | **73.75 h** |

If edge inference is dropped, move ~2.5–3 h of Phase 14/18 tasks from Sushil to Yashwant. Tasks tagged 🧑 need phones, an Azure account, or a human at a device. The v2.1 total is larger than `todo_v2.md`'s 52.75 h / 49.5 h because it adds the React rebuild, hosting and Android refresh, and removes 17.25 h of superseded Streamlit/Android work.

### Recommended build order
1. **Kickoff (both):** T10-001 + T16-000 (approve amendments A1–A6, merge the delta).
2. **Quick win, parallel with the server work:** Sushil T16-001 → T16-006 → T16-007 → T16-008 → pages; Yashwant T16-002 → T16-003 → T16-004. Ship the static demo: T16-019 → T18-009 (GitHub Pages) → T18-010 (Vercel, optional). *You now have a public link.*
3. **Server track (v2):** T10-xxx → T11-xxx incl. the parity test T11-006.
4. **Android (Yashwant):** T19-001 → T19-002 (golden test) → T19-003 → T19-004 → T19-005 → T19-006/007/012 → T12-002..004 → T19-008, T19-009.
5. **Hosted backend (Sushil):** T18-001 → T18-002 → T18-003/004/005 → T18-012; Yashwant: T18-007 → T18-008 → T18-011.
6. **React live mode:** T17-001 → T17-002..T17-008, T17-010 → T17-009.
7. **Validation:** T18-013, T18-014, T19-013, T19-014, T12-009 (include a cellular-link run), then Phase 14 and T14-018/019.

### Risk register (v2.1 additions)
| Risk | Tasks | Likelihood | Mitigation |
|---|---|---|---|
| Public ingest exposes location-revealing cell IDs of strangers | T18-002, T18-004, T18-005, T18-012 | Medium | Ephemeral sessions, consent screen, no server retention in public mode, privacy doc, session caps; do not launch publicly before the privacy review (T18-012/T18-013) |
| Abuse of an open public endpoint (session spam, code guessing) | T18-004, T18-013 | Medium | Per-IP limits, lockout, session cap, idle reaper; can fall back to invite codes |
| Azure free tier unsuitable for always-on WebSocket (billing, ingress idle timeout, cold start) | T18-011, T18-015 | Medium (UNVERIFIED) | Verify in docs first; 15 s pings; fallback: local mode + static demo only |
| Android refactor changes collected data | T19-002, T19-003, T19-014 | Low–Medium | Golden test before UI work, UiState step separate from UI step, before/after real-phone regression |
| Foreground-service rules for `targetSdk 37` / OEM battery management stop collection | T19-009 | High | Verify docs; per-device tests; document unsupported behaviour; screen-on fallback |
| Frontend drifts from Python results | T16-004, T16-018, T16-020 | Medium | Bundle tests, parity test, no-logic lint |
| Charting library cannot handle gap breaks/markers/size | T16-001 | Low | Time-boxed spike before building pages |
| GitHub Pages sub-path / deep-link breakage | T18-009 | Low | Hash routing, base path test in CI |
| Scope grows (upload feature, accounts, maps) | — | Medium | Not in v2.1; list in `V2_1_DELTA` §9 |
| Public demo labelled as a real-world detector | T16-015, T18-009 | Medium | Footer notice and non-claims on every page (G31) |

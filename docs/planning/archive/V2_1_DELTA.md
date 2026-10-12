# v2.1 DELTA — React Frontend, Hosted Pairing, Android UI Refresh

> **Read with:** `PRD_v2.md`, `DESIGN_v2.md`, `TECH_RULES_v2.md`, `ROADMAP.md`, `todo_v2.md` (all on branch `docs/v2-verification`). This file **overrides** them wherever they disagree; the merge task `T16-000` folds it into those files so this file can then be archived.
> **Evidence base:** `dashboard_inventory.md`, `android_inventory.md`, `demo_data_sizes.md`, six Streamlit screenshots. Anything I could not confirm from those is marked **UNVERIFIED**.
> **Owner decisions captured:** (1) v1 Streamlit dashboard is frozen as the v1 result. (2) v2 frontend is React, deployable to free platforms. (3) Target product: the phone app sends metrics to a **website**, which processes and displays them. (4) The Android app UI gets a project-themed refresh, without touching collection logic.

---

## 1. What the inventories showed (facts that change the plan)

| # | Finding | Source | Consequence |
|---|---|---|---|
| F1 | The dashboard is display-only over four artefacts: `scores.csv`, `events_diagnosed.json`, `models/if_v1.meta.json`, `preprocess_log.json` (plus `data/sample/` fallback). | dashboard_inventory §4 | A static React app can run from a precomputed JSON bundle. **No backend needed for the demo.** |
| F2 | The full processed dataset is ~367 KB gzipped (`scores.csv` 326 KB + events 32 KB); JSON form est. ~450 KB gz. | demo_data_sizes §10 | Bundle fits a static host easily. |
| F3 | `nci` is globally unique to a cell (High location sensitivity), `pci` medium, timestamps medium. | demo_data_sizes §11 | Public demo bundle must hash cell IDs by default (G27). |
| F4 | `3_Cells_And_Network.py` re-computes handover transitions in view code. | dashboard_inventory §5 | Violates the "no logic in the dashboard" rule. Move to a data-prep script; React only renders. |
| F5 | Signal Explorer / Cells charts plot **all sessions on one time axis**; screenshots show two vertical clusters and lines bridging session gaps. NCI is on a linear 10B axis. Metric cards truncate values (`-102…`, `133…`, `629…`). Sidebar branding appears twice. Overview caption says "**Real-time** & Replay". Event times show `+00:00` although device timestamps carry no timezone. | screenshots, inventory §2 | React design fixes all six (see §4). "Real-time" wording violates G24; remove. |
| F6 | Data Quality screenshot: CSI availability is `False 100%` for **both** devices. Redmi shows 3,756 rows and Samsung 1,772. | screenshot 5 | CSI is unavailable on both phones. The 3,756 vs 3,760 Redmi "mismatch" is **raw (3,760) vs processed (3,756)**, i.e. 4 rows dropped by validation — not an error. See §8 (correction to the round-3 prompt). |
| F7 | Samsung `ss_sinr` missing = 36 (2.0%), exactly the number of `ss_sinr = -1` rows found by the agent (36). | screenshot 5 + verification round 2 | Strong hint (not proof) that *all* Samsung missing SINR is the `-1` erasure. Redmi: 479 missing, of which 185 are `-1`. |
| F8 | Android UI is built **programmatically** (LinearLayout/TextView/Button) in `MainActivity.kt`; Compose + Material3 dependencies and `Color.kt/Theme.kt/Type.kt` exist but are unused. All UI strings are hard-coded; no dark mode; one activity. | android_inventory §12, §14 | Compose migration is feasible with deps already present. |
| F9 | **UI update happens inside the collection path**: `processNrCell()` builds the CSV row *and* sets `outputText.text`. The inventory's "UI is decoupled" claim is only half true. | android_inventory §14c | A UI refactor must touch `processNrCell`. Protect CSV output with an extracted pure `buildCsvRow()` + golden test (G32). |
| F10 | `csvRows` lives **in memory**; a file is written only when the user taps SAVE. Collection is a `Handler` loop in the Activity; **no foreground service**. | android_inventory §14c, §13 | A killed/backgrounded app can lose a whole session. Streaming needs incremental persistence and a foreground service. |
| F11 | Manifest has `READ_PHONE_STATE` and `ACCESS_FINE_LOCATION` only. **No `INTERNET` permission**; no network code; `targetSdk = 37`, `minSdk = 29`. | android_inventory §12, §13, §16 | Add `INTERNET`. Consent text must say location permission is needed by Android for cell info but **no location is recorded or sent**. |
| F12 | Dashboard accepts CSV upload (≤20 MB, PII/column validation) and processes it via the Python pipeline. | dashboard_inventory §3 | Upload needs a **backend**. Not available in the static demo; becomes a hosted-mode feature (optional). |

---

## 2. Amendments to `project-overview.md` (add to A1–A3)

| # | Statement in v1/v2 docs | New position |
|---|---|---|
| **A4** | Overview names Streamlit as the dashboard. | v1 dashboard = Streamlit (frozen, maintained only for bugs). v2 dashboard = React single-page app. |
| **A5** | "Local single-user tool"; local-first. | v2 may run as a **hosted web service** where a user pairs their own phone. Public hosting is allowed **only** with: consent (G28), ephemeral sessions (G29), per-session tokens, cell-ID protection in logs. |
| **A6** | A3 (v2) specified one shared pairing token. | Replaced by **per-session ingest and viewer tokens** (C10). |

Each needs both authors' approval in the same PR as `T10-001`.

---

## 3. Deployment architecture (three modes, one codebase)

```
(1) STATIC DEMO  — public link, no backend, no phone data
    GitHub Pages / Vercel / Azure Static Web Apps
      └─ React SPA + bundled demo data (demo-bundle.json.gz, hashed cell IDs)

(2) LOCAL LIVE   — real use on your laptop (private)
    Phone ──USB adb-reverse / Wi-Fi──► FastAPI (one container or `make serve`)
      └─ serves the built React app + ingest + live API; nothing leaves the machine

(3) HOSTED LIVE  — a person pairs their own phone to the website (the owner's target)
    Phone ──wss──► Azure Container Apps (FastAPI, min 1 replica) ◄──wss── Browser (React SPA)
      └─ SPA may be served by the same container or from Vercel/Pages (CORS allow-list)
```

- Mode 1 is the **first shippable result** (needs no streaming work) and gives a public link early.
- Mode 3 is built on the same code as mode 2; the extra work is pairing, consent, limits, TLS/CORS, deployment.
- **Hosting facts (checked 2026-10-09 via search; treat as dated):** Vercel's WebSocket support is a public beta with connections bounded by the function's maximum duration — so Vercel hosts the SPA only. Azure Container Apps' monthly free grant is 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 M requests, with scale-to-zero; an always-on 0.25 vCPU replica would use about 200 h of the free vCPU grant by my arithmetic. **UNVERIFIED:** whether idle-replica billing and the ingress WebSocket idle timeout suit this use — check the Azure pricing page and ingress docs before relying on it; the protocol's 15 s `ping` is designed to survive idle timeouts.
- **GitHub Pages specifics:** static only; project sites live under `/<repo>/`, so set the Vite `base` path and use hash-based routing (or a 404 redirect trick) so deep links work.

---

## 4. React app specification

### 4.1 Stack (default; confirm in spike `T16-001`)
Vite + React + TypeScript (SPA — no server rendering needed); client router (hash mode for GitHub Pages); CSS variables for the DESIGN tokens (light + dark); a time-series chart library chosen by spike against these criteria: 5.5 k points × 4 stacked panels, shared x-axis, zoom/pan, marker overlays, gap breaks, text/table fallback, bundle size; Vitest + React Testing Library for components; Playwright for e2e and screenshot checks. TypeScript types for C8/C9/C10/C11 are **generated from the JSON Schema** exported by `T10-008`, not hand-written (verify the generator tool at implementation time).

### 4.2 Pages (parity with v1 first, then fixes)
Same six pages and copy rules as the Streamlit dashboard, so reviewers can compare:

| Page | Keeps | Fixes / changes |
|---|---|---|
| 1. Overview | Status banner (NORMAL / ANOMALY + severity), network & device card, six metric cards with deltas, score block, event label, diagnosis / evidence / recommendation | Cards never truncate (wrap or shrink, tooltip on full value); caption drops "Real-time"; banner rule unchanged (anomaly if `is_anom` or type ∉ NORMAL/CELL_TRANSITION/NETWORK_STATE_TRANSITION) — add a distinct **ML-only** (`STATISTICAL_ONLY`) treatment |
| 2. Signal Explorer | 4 stacked panels (RSRP, RSRQ, SINR, IF score with 0.60 line), flag overlay radio (both/baseline/IF/hide), rolling-mean toggle, data-table expander, summary sentence | **One session at a time** (session tabs + prev/next) with a thin all-sessions overview strip; lines **break at gaps and `NA`**; shared zoom; no 2× downsampling unless measured necessary |
| 3. Cells & Network | PCI / NCI / NRARFCN step charts, transition table, "cell change is not an anomaly" note | Transitions come **precomputed** from the bundle (fixes F4); NCI/PCI shown as categorical labels (or hashed labels in the public bundle); per-session view |
| 4. Events & Diagnosis | Type and severity filters, event table, selected-event agent cards (Signal, Cell, Network, Diagnosis, Recommendation), event-window mini-chart, JSON download | Virtualised table (365 events); status column; times labelled **"device local time (no timezone recorded)"**, never `+00:00` |
| 5. Data Quality | Missing values per device and column, CSI availability, deployment-mode distribution with the UNKNOWN note, preprocessing log metrics, synthetic-data banner | Read from the bundle; show raw vs processed row counts with the reason rows were dropped |
| 6. About & Limitations | Description, non-claims, dataset summary, model metadata, links | v2 non-claims list (12 items from `PRD_v2`), "research prototype" statement, no "real-time" claim, privacy note |

**Replay player** (replaces the sidebar slider): play / pause / speed (1×, 5×, 20×) / scrubber; the current sample drives Overview. Replay and Live use the **same components** — only the data source differs (bundle vs WebSocket).

**Global shell:** single brand header (fixes the duplicated sidebar title), device/operator/session filters, light/dark theme, keyboard-reachable controls, footer with version, `model_version`, and a "Research prototype — see limitations" link.

### 4.3 Data bundle (Contract **C11**)
`scripts/build_demo_bundle.py` produces `demo-bundle.json` (served gzipped):
```
{ "bundle_version": 1, "generated_at": "...", "model_version": "...", "source": "processed|sample",
  "privacy": {"cell_ids": "hashed|raw", "time": "device-local, no timezone"},
  "sessions": [{ "session_id", "device", "operator", "n", "start", "end" }],
  "samples":  { "columns": [...], "rows": [[...], ...] },      // columnar/array-of-arrays to keep size small
  "transitions": [{ "ts", "session_id", "type", "from", "to" }],  // precomputed (replaces F4 logic)
  "events":   [ ...C5-compatible records as in events_diagnosed.json... ],
  "quality":  { "missing": {...}, "csi_available": {...}, "deployment_modes": {...}, "preprocess_log": {...} },
  "model_meta": { ... } }
```
Rules: **public bundles default to hashed `nci`/`pci`** (stable per-bundle salt; `pci_changed`/`nci_changed` flags preserved; UI labels like "Cell A"); raw IDs only for local use (`--raw-cell-ids`); a schema/version check on load; builder is deterministic and tested against the CSV/JSON it came from (row counts, a sample of values).

### 4.4 Live mode (same app)
Adds: connection chip with the states in `DESIGN_v2` (LIVE / STALE / RECONNECTING / DISCONNECTED / WAITING / REPLAY), alert banner + acknowledge, provisional vs final events, Stream Health page, pairing panel (§5). Everything in `DESIGN_v2` for Live screens L1–L5 carries over as the **behavioural** spec; Streamlit-specific parts (fragments, `st.toast`, `st.sidebar` limits) are dropped. Browsers can use real ARIA live regions, so the Streamlit accessibility fallbacks are replaced by proper `aria-live="polite"` announcements for state changes and alerts.

### 4.5 Frontend rules (new guardrails)
- **G30 — No logic in the frontend.** Scores, flags, events, transitions, diagnoses and quality statistics are computed in Python (bundle builder or server). The frontend formats and plots only. A lint/test checks that no module recomputes z-scores, thresholds or event grouping.
- **G27 — Public demo data are anonymised by default** (cell IDs hashed; no raw `data/raw` files shipped; bundle builder refuses `--raw-cell-ids` with `--public`).
- **G31 — Public deployments always show** the research-prototype notice and the non-claims; the demo page states the data came from two phones on one operator.

---

## 5. Hosted pairing and ingest (Contract **C10**; replaces the single shared token)

**Flow**
1. Browser: user clicks **Start live session** → `POST /api/v1/live-sessions` → `{session_id, pairing_code, expires_at}` (code: 8 characters from an unambiguous alphabet, single-use, TTL 10 min; also rendered as a QR). The server sets an `HttpOnly` viewer cookie for that session.
2. Phone: user enters the code (or scans the QR), after the consent screen → `POST /api/v1/pair {pairing_code, client_id, app_version, schema_version}` → `{session_id, ingest_token, ws_url, limits}`.
3. Phone opens `wss://…/api/v1/ingest` with `Authorization: Bearer <ingest_token>` (OkHttp can set headers) and continues with the C7 protocol unchanged (`hello`, `sample`, `ack`, `ping`, `bye`).
4. Browser opens `wss://…/api/v1/live`, and authenticates with a first-frame message `{"type":"auth","ticket":"…"}` within 5 s, where the ticket comes from `POST /api/v1/live-sessions/{id}/ticket` (single-use, 30 s). **The ticket is not placed in the URL**, so it cannot end up in proxy or platform logs. (This deliberately re-introduces the ticket mechanism removed in verification round 2: the hosted browser case needs it, the Streamlit server-side case did not.)
5. Session ends on `bye`, on 15 min idle, or when the user clicks **End session**.

**Rules**
- **Per-session tokens:** the ingest token only writes to its session; the viewer cookie/ticket only reads it. No global token; amends A3 (see A6). Tokens expire with the session.
- **Ephemeral by default (G29):** live data are held in memory (bounded) and deleted at session end; nothing is written to server disk unless `NADS_RETAIN_SESSIONS=true` (off in the public deployment). The user can **Download CSV** (C1 format) in the browser before ending.
- **Consent before streaming (G28):** the phone app cannot start streaming without a consent screen listing exactly what is sent (signal metrics, cell identifiers, device model, operator name, Android version) and what is not (no GPS/location, phone number, IMEI, contacts). The website shows the same text and the warning that **cell identifiers can reveal approximate location**.
- **Abuse limits (free tier):** `MAX_LIVE_SESSIONS` (proposed 5), per-IP session-creation and pairing-attempt rate limits, pairing-code brute-force lockout, message size/rate caps from C7, idle-session reaper. No user accounts in v2.1.
- **Network config:** `NADS_ALLOWED_ORIGINS` allow-list for CORS and WebSocket `Origin`; TLS terminated by the platform ingress; the server refuses to start in "public" mode without an allow-list and with retention on.
- **Logging:** never log tokens, pairing codes, full cell IDs or query strings; platform request logs are out of our control — state this in `docs/privacy.md`.
- **Always-on:** WebSocket sessions need ≥1 running replica; a cold start would break the first connection (UNVERIFIED how the platform handles idle/ingress timeouts — see §3).

**Measurement perturbation (unchanged hypothesis):** streaming from a phone over cellular sends ~1 KB per 3 s on the radio being measured. `T12-009` still applies and must include a hosted-over-cellular condition now that this is the intended use.

---

## 6. Android changes

**Principle:** the collection and CSV path stays functionally identical (G18, G32); everything else is additive.

| Area | Change | Why |
|---|---|---|
| Source of truth | Open `android-collector/5GNetworkTester` **directly in Android Studio** (it has its own Gradle project); stop copying files in from a second project | Prevents two diverging copies |
| Pure row builder | Extract `buildCsvRow(sample): String` from `processNrCell()`; add a golden unit test (fixed fake values → exact expected CSV line, including `NA` handling and the `dd-MM-yy HH:mm:ss` timestamp) | Gives a real "CSV unchanged" proof (G32) before any UI work |
| UI state | `processNrCell()` publishes a `UiState` object instead of setting `outputText.text` directly | Fixes F9 coupling; enables Compose |
| UI | Compose screens using the existing Material3 deps and `Theme.kt`: Home (status + three metric cards + network chip + sample counter + Start/Stop), Pairing, Consent, Saved-files / export; project-themed light and dark colour schemes from the DESIGN tokens; `strings.xml`; new launcher icon; app title "5G-NADS Collector" with the **same `applicationId`** | Owner request; F8 |
| Persistence | Append each row to the session file as it is collected (`SAVE CSV` becomes "finish & share") | F10 — avoid losing a session |
| Foreground service | Move the 3 s sampling loop into a foreground service with notification so collection survives screen-off/backgrounding | F10; replaces `T12-005` |
| Streaming | Add `INTERNET` permission; OkHttp WebSocket client + pairing call; hook after the row is added (one line), failures never touch collection | F11 |
| Debug networking | Debug-build-only network-security config permitting `ws://localhost` for `adb reverse`; release builds use `wss://` only | Avoids shipping a cleartext exception |
| Export | Add an Android share intent for the saved CSV | Replaces USB/ADB pulls |

**Unverified, must be checked before building:** foreground-service type and permission rules for `targetSdk = 37` (the earlier Android 16 research was for API 36); behaviour of Xiaomi/Redmi battery management with the service running; whether `ACCESS_FINE_LOCATION` is also needed while the screen is off for `requestCellInfoUpdate`.

**New guardrail G32:** the collector's CSV output for fixed inputs is byte-identical before and after the UI refactor (golden test), and the 18-column C1 header is unchanged.

---

## 7. Changes to existing v2 plan items

| Existing item | Status | Replacement |
|---|---|---|
| `T12-001` (Android settings) and `T12-006` (status strip) | Superseded | Phase 19 (Pairing/Consent/Home screens) |
| `T12-005` (foreground service) | Superseded | `T19-009` |
| `T13-010`…`T13-020` (Streamlit Live: live client, chip, pages, a11y, smoke tests) | Superseded | Phase 17 (React) |
| `T13-001`…`T13-009` (alert engine, channels, ack API) | **Kept** | — |
| `T15-002` (per-role tokens) | Superseded | C10 per-session tokens (`T18-002`) |
| `T14-001` (auth tests), `T14-004` (security doc), `T14-005` (privacy audit) | Kept; scope widened | Cover pairing, tickets, public mode (`T18-0xx`) |
| `T14-008` (latency benchmark) | Kept | Measure to the React client, hosted and local |
| Streamlit dashboard | Frozen | README labels it "v1 result"; no new features |
| `TECH_RULES_v2` G17–G26 | Kept | Add G27–G32 |
| `TECH_RULES_v2` "Frontend Architecture" and C8 auth | Replace | §4 and §5 here |

New contracts: **C10** pairing/session API, **C11** demo-bundle schema. C7 (ingest messages) and C8 event shapes are unchanged except for the browser auth handshake.

---

## 8. Corrections to earlier advice (from the inventories)

1. **Redmi row count.** Do **not** change the Redmi figure in `docs/eda_findings.md` to 3,760 everywhere. The dashboard's processed table uses 3,756; raw is 3,760. Write both ("3,760 raw / 3,756 after validation; 4 rows dropped") and check `preprocess_log.json` for the reasons.
2. **CSI availability** is 0% on **both** devices (dashboard Data Quality table). The EDA table's Redmi "100%" is wrong; the paragraph under it was right.
3. **Sentinel `-1`.** Samsung's missing SINR equals its `-1` count exactly (36). Together with the earlier neighbour analysis, treat the `-1` erasure as a real v1 limitation; record it, fix it in a separate v1 PR.
4. The inventory's "UI is decoupled from CSV generation" is only partly true (F9).

---

## 9. Open questions (record answers in `docs/decisions.md`)

1. Public demo: hashed cell IDs (my default) or raw? Time shown as-is or as relative offsets?
2. Single container serving SPA + API (simplest) or SPA on Pages/Vercel and API on Azure (needs CORS)? Default: single container for mode 2/3; Pages/Vercel for the static demo only.
3. Is the CSV-upload feature kept? It needs the backend pipeline; default: hosted mode only, off in the public deployment.
4. Does the hosted deployment accept sessions from anyone, or only people with an invite code? Default for v2.1: open but capped and rate-limited; revisit after a privacy review.
5. Charting library and CSS approach (decided by `T16-001`).
6. Android: Compose migration of the whole screen (default) or a minimal restyle of the existing Views (cheaper, less future-proof)?

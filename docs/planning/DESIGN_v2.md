# DESIGN v2.1 — 5G-NADS React Dashboard (Static Demo, Live Charts, Alerts, Pairing)

> **Builds on:** `docs/planning/DESIGN.md` (v1) and `docs/planning/V2_1_DELTA.md`. Everything in v1 DESIGN — philosophy, copy rules, tokens, typography, spacing, component conventions, accessibility — **still applies** unless overridden here.
> **Frontend Architecture:** Replaces Streamlit with a modern **React SPA (Vite + TypeScript)** across three deployment modes (1: Static Demo on GitHub Pages/Vercel, 2: Local Live, 3: Hosted Live). The v1 Streamlit dashboard is frozen as a historical baseline.
> **Requirements:** `PRD_v2.md` FR-12, FR-15, FR-16, FR-17, FR-18; Contracts C8, C9, C10, C11.
> **Accessibility & Performance:** Unlike Streamlit, React provides real client-side state management, native `aria-live="polite"` regions, zero-rerun sub-second chart updates via Canvas/SVG, and full responsive layout control.

---

## Design Philosophy

### Visual Style
- Unchanged: utilitarian, data-first, low chrome; one accent colour; semantic colours only for status.
- Live additions: **no flashing, no sound, no animation** beyond subtle UI spinners. "Live" is communicated by a **state label and a sample-age counter**, not by distracting motion.

### Branding Direction & Shell
- Single unified brand header (fixes the v1 duplicated sidebar branding).
- Mode label: **"5G-NADS · Static Demo"**, **"5G-NADS · Local Live"**, or **"5G-NADS · Hosted Live"** so users are never confused about data origin.
- Replay player: unified play / pause / speed (1×, 5×, 20×) / scrubber driving the overview. Replay and Live use the **exact same UI components** (only data source differs: bundle vs WebSocket).

### UX Goals (v1 goals retained; v2 adds)
1. *(v1)* Answer in 5 seconds: is the current sample normal? If not, what kind of event and why?
2. **Never show stale data as current.** Every live value is accompanied by its age; beyond a threshold the whole page switches to a STALE presentation.
3. **Say what is provisional.** An event still developing is labelled *Provisional* and its diagnosis is worded as such; it becomes *Final* only when the event closes.
4. **Alerts are rare and explainable.** Each alert shows the evidence that triggered it and, equally important, why ML-only flags did *not* alert.
5. **Connection problems are information, not errors.** A dropped link is displayed as a state with a cause and a suggested fix, not a stack trace.
6. *(v1)* Never present `UNKNOWN` as SA, or `NA` as zero.

### Content & Copy Rules (v1 table applies; additions)
| Do | Don't |
|---|---|
| "Live — last sample 2 s ago" | "Real-time" with no age shown |
| "Provisional: possible radio-quality degradation associated with a cell transition (event still open)" | Presenting an open event's diagnosis as final |
| "No data for 14 s — showing the last known values (STALE)" | Silently freezing the last value |
| "Streaming link lost. The phone is still logging to its CSV; missed samples will be re-sent when it reconnects." | "Data lost" (unless it is) |
| "Statistically unusual (score 0.71); no rule-based evidence — no alert sent" | Hiding ML-only flags, or alerting on them |
| "Edge score (advisory, on phone): 0.69 · Server score (authoritative): 0.71" | Showing the phone score as the result |

---

## Information Architecture

### Navigation Structure
Sidebar gains a **Mode** switch at the top. Replay mode is exactly v1's navigation. Live mode shows:

```
5G-NADS · Live
├── 1. Live Overview        (default in Live mode)
├── 2. Live Signals
├── 3. Live Cells & Network
├── 4. Live Events & Alerts
├── 5. Stream Health
├── 6. Data Quality         (reused from v1, reads the live session CSV)
└── 7. About & Limitations  (reused; v2 non-claims added)
Sidebar (Live): Mode [Live | Replay] · server status · session selector · window length (5 / 15 / 60 min) · alert filter
```

### Screen Hierarchy
- **Global context** (sidebar): mode, connection indicator, session, time window.
- **Live Overview** → summary → text hints to Events & Alerts.
- **Live Signals / Cells** → deep-dive charts, same semantics as v1 pages 2–3, now windowed and auto-refreshing.
- **Live Events & Alerts** → list → detail, plus alert history.
- **Stream Health** → trust in the pipeline itself.

### User Flow (ASCII)

```
Open app ──► Mode = Live ──► server reachable? ──no──► "Server not reachable" state (how to start: `make serve`; or switch to Replay)
                                   │yes
                                   ▼
                       any session / sample yet? ──no──► "Waiting for a phone to connect" (shows host:port, pairing hint; offers "Replay a recorded session")
                                   │yes
                                   ▼
             Live Overview: [connection: LIVE] status · score · provisional/final event · diagnosis · recommendation · active alert banner
                 ├── signals ───────► Live Signals
                 ├── cells ─────────► Live Cells & Network
                 ├── events/alerts ─► Live Events & Alerts (acknowledge alert)
                 ├── "is the data fresh / complete?" ► Stream Health
                 └── doubt ─────────► Data Quality / About
```

---

## Connection & Freshness Model (shared by all Live screens)

A single **connection state machine** drives every indicator. States (text label **and** icon **and** colour — never colour alone):

| State | Meaning | Trigger (defaults live in `ml/config.py`) | Colour token | Icon | Banner text |
|---|---|---|---|---|---|
| **LIVE** | Samples arriving on time | last sample age ≤ `STALE_AFTER_SECONDS` (proposed 10 s ≈ 3 sampling intervals) | Normal (`#15803D`) | ● filled circle | "LIVE · last sample 2 s ago" |
| **STALE** | Server up, but no new sample recently | age > `STALE_AFTER_SECONDS` and phone session still open | Warning (`#B45309`) | ◐ half circle | "STALE · no sample for 14 s — values shown are the last known" |
| **RECONNECTING** | Phone link dropped; server waiting; phone expected to resume | phone socket closed, session not yet expired | Warning | ◐ | "Phone disconnected — waiting for it to resume (re-sends buffered samples)" |
| **DISCONNECTED** | Dashboard cannot reach the server | dashboard↔server WebSocket/REST failing | Anomaly-red is **not** used (not an anomaly). Use Neutral 700 (`#334155`) | ○ empty circle | "Server not reachable — start it with `make serve` or switch to Replay" |
| **WAITING** | Server up, no phone/session yet | no active session | Info (`#0369A1`) | ◌ dotted | "Waiting for a phone to connect" |
| **REPLAY-SOURCE** | Data comes from `replay_stream.py`, not a phone | session metadata `source=replay` | Info | ▶ | "REPLAY (recorded data streamed at 5×) — not a live phone" |

Rules:
- A persistent **connection chip** sits at the top of every Live page (and in the sidebar) showing state + sample age. It is updated on every refresh tick.
- When state ≠ LIVE, the status banner of the Overview adds the line **"Showing last known values"** and de-emphasises (not removes) the cards.
- Red is reserved for **anomalies and failed alert channels**, not for connectivity, so a Wi-Fi blip is never visually confused with a radio anomaly.
- Refresh cadence: default **1 s** fragment refresh *(proposed)*; configurable 1–5 s. The chip's age counter uses the browser-independent server timestamp, not the refresh count.

---

## Screen Specifications

## Screen Specifications

### Screen L1 — Live / Replay Overview
- **Purpose:** the 5-second answer for *right now*, plus trust signals.
- **Components:**
  - **Connection chip** + sample age (top, full width): LIVE / STALE / RECONNECTING / DISCONNECTED / WAITING / REPLAY.
  - **Alert banner** (only when an unacknowledged alert exists): severity chip, one-line hedged summary, **Acknowledge** button, link to Events & Alerts.
  - **Status banner:** `NORMAL` (green) / `ANOMALY DETECTED` (red) with severity chip, plus a **Provisional** badge if the current event is open. ML-only flag without rule evidence shows as a distinct **ML-only (`STATISTICAL_ONLY`)** amber-bordered line: "Statistically unusual — no rule-based evidence (no alert)".
  - **Metric cards:** RSRP, RSRQ, SINR, PCI, NCI, NRARFCN. Values **never truncate** (cards wrap or shrink, tooltip displays full precision). Tiny age indicator when STALE.
  - **Network-state card:** Network type, Deployment mode (Unknown shown as "Unknown (not exposed by this device)"), Registered, Operator, Device, **Source** (Phone live / Replay). Caption explicitly omits "Real-time" (G24).
  - **Score block:** baseline z (flag) and IF score (flag) shown separately; **edge score** (advisory) shown as a third, visually secondary line only when edge inference is enabled.
  - **Detected event** label (v1 categories, `NORMAL`, or `STATISTICAL_ONLY` for ML-only flags) + status (**Provisional / Final**) + start time + duration so far. Times explicitly labelled **"device local time (no timezone recorded)"**, never `+00:00`.
  - **Diagnosis, Evidence, Recommendation** from agents (v1), prefixed "Provisional —" while the event is open.
  - **Sparkline:** last 60 samples of RSRP and SINR with anomaly markers.
- **Layout (12-col):** R0 chip (12) · R1 alert banner (12, conditional) · R2 status banner (12) · R3 network-state (4) + 6 metric cards 2×3 (8) · R4 score (4) + event/severity/status (8) · R5 diagnosis (8) + recommendation (4) · R6 sparkline (12, optional).
- **Interactions:** Replay scrubber (in Replay / Demo mode) or Pause/Resume live stream toggle; Acknowledge alert; hover on card shows delta.
- **Empty state:** WAITING state text with pairing code / QR modal launcher.
- **Error state:** DISCONNECTED text with troubleshooting steps; schema mismatch alert. No raw tracebacks.
- **Loading state:** Minimal skeleton placeholder during initial bundle fetch or WebSocket connection.
- **Responsive:** cards 2-col on tablet, 1-col on phone; chip + alert banner always on top.

### Screen L2 — Signal Explorer
- **Purpose:** RSRP/RSRQ/SINR over selected time window with anomaly markers (v1 Screen 2 semantics).
- **Session Presentation (Fixes F5):** **One session at a time** (session tabs + prev/next controls) with a thin all-sessions timeline strip. Prevents multi-session vertical clustering.
- **Components:** four stacked time-series panels (RSRP, RSRQ, SINR, IF score with 0.60 threshold line; shared x-axis, ~240 px each); anomaly markers (× red, with tooltip details); cell-change markers (grey vertical lines); flag overlay radio (both / baseline / IF / hide); rolling-mean toggle; one-sentence text summary above each chart.
- **Gap & NA Handling (Fixes F5):** Lines **strictly break at gaps and `NA` values**; lines never bridge gaps. A subtle grey band ("no data — n samples missing") marks gaps > `SESSION_GAP_SECONDS`.
- **Interactions:** Shared zoom/pan across all 4 panels; hover tooltip shows timestamp, metrics, flag state, edge score.
- **Accessibility:** Expandable data table view below charts (virtualised table).

### Screen L3 — Cells & Network
- **Purpose:** PCI/NCI changes and network-type transitions without implying anomaly (v1 Screen 3).
- **Components:**
  - Transitions table: precomputed transitions loaded directly from bundle/engine (Contract C11; fixes F4 view-computation defect).
  - Categorical step charts: PCI and NCI plotted as **discrete categorical/hashed step lines** (Fixes F5 linear 10-billion scale issue).
  - NRARFCN frequency channel line and network type status strip.
- **Copy rule (v1 retained):** "A cell change is normal network behaviour. It is highlighted here as an *event*, not as an anomaly."
- **Per-session View:** Scoped to the currently active session tab.

### Screen L4 — Events & Diagnosis
- **Purpose:** List events (open and closed) and alerts; show multi-agent evidence per event.
- **Components:**
  - **Events table:** Virtualised table (handling all 365+ events smoothly); columns: id, start, end, duration, type, severity, max score, **status (PROVISIONAL / FINAL)**, alerted reason. Times displayed as device-local (no timezone offset).
  - **Selected event detail cards:** Signal, Cell, Network agent columns, Synthesis Diagnosis, Action Recommendation, event-window mini chart, JSON download button.
  - **Alerts panel:** Table of alerts (timestamp, event, severity, delivery channel, acknowledged status).
  - **Channel health:** In-app, Phone, Webhook, Email status chips.

### Screen L5 — Stream Health
- **Purpose:** Transparent transport and pipeline telemetry.
- **Components:** Connection timeline, latency percentiles (p50/p95/max with "Measured in this setup" footnote), message completeness (gaps, resends, queue drops), clock skew estimate, model version and hash verification.

### Screens L6–L7 — Data Quality, About & Limitations
- Reused from v1 with F5/F6 corrections:
  - Data Quality: Shows raw (3,760) vs processed (3,756) row counts with 4 validation drops; CSI availability reported as 0% for both devices.
  - About: Displays 13 explicit non-claims, "Research prototype — not a real-world detector" notice, privacy architecture note, and confirmation that O-RAN, iOS, and SMS are not implemented.

---

## Alert Design

### Alert anatomy (in-app card, phone notification, webhook/email text share the same fields)
| Field | Content |
|---|---|
| Title | Severity + type, e.g. "MEDIUM · Persistent poor radio quality (possible)" |
| Body (≤ 2 lines) | Hedged summary: "SINR below −5 dB for 24 s while RSRQ also degraded; no cell change in window." |
| Evidence (in-app only, expandable) | Agent evidence bullets (v1 C5 `evidence`) |
| Recommendation | v1 recommendation text (monitoring/investigation wording only) |
| Meta | event id, session, time, **Provisional/Final**, source (phone/replay) |

Rules:
- Wording passes the v1 hedged-language tests ("possible", "associated with"; never "caused", never "fixed").
- Alerts are **never** colour-only: icon + severity word + colour.
- Notification push uses default notification priority; no alarming audio sirens.
- **Acknowledge** stops re-display, not logging.
- **Suppression is visible:** Events table always states why an event did not alert.

### Alert severity presentation
LOW = info-blue chip, MEDIUM = amber chip, HIGH = red chip; each chip contains the word. LOW severity does **not** push to phone/webhook/email by default (configurable).

---

## Android Companion UI (collector app — streaming additions only)

The collector's existing screens are out of scope except for these additions:

- **Streaming settings** (new section): Server host, Port, Pairing token (masked, paste/QR optional), Stream toggle, "Test connection" button (result inline: "Connected · model if_v1" or the specific failure: unreachable / unauthorised / version mismatch).
- **Status strip** on the logging screen: `Streaming: Connected | Reconnecting (queue 37) | Off`, last ack time, dropped-from-queue counter. Uses text + icon.
- **Edge score (only if edge module enabled):** small secondary line "Edge score (advisory): 0.69". Never labelled "anomaly detected".
- **Alert notifications:** standard Android local notification, title/body as in *Alert anatomy*; tapping opens the app's status screen.
- **Battery/background guidance:** a one-time dialog explaining that some manufacturers stop background apps and linking to the system battery settings; no dark patterns.
- **Touch targets:** ≥ 48 dp (Android guideline).

---

## Design System & Component Specifications

### Colours & Tokens
v1 tokens are reused unchanged via CSS variables (`--color-normal: #15803D`, `--color-warning: #B45309`, `--color-info: #0369A1`, `--color-neutral-700: #334155`). Light and dark theme palettes defined in CSS tokens.

### Component Implementation (React + CSS Tokens)
- **Connection chip:** Dedicated React component rendering icon + state label + age counter; bound to client WebSocket connection state.
- **Alert banner:** Accessible container with 4px severity accent border and `aria-live="polite"` region.
- **Charts:** Canvas/SVG charting library (selected via spike T16-001) supporting broken lines across gaps/NAs, zoom syncing across panels, and red × marker overlays.
- **Tables:** Virtualised table rendering for 365+ diagnosed events.
- **Modals:** Accessible pairing modal (displaying 8-character pairing code and QR code) and Consent dialog.

---

## Accessibility Requirements (WCAG 2.1 AA)

- **Native ARIA live regions:** Critical connection changes and alerts announce via `aria-live="polite"` to screen readers.
- **Keyboard Navigation:** All interactive elements, tabs, filters, and modal dialogs are fully keyboard-navigable with visible focus rings.
- **No Colour-Only Signalling:** All status indicators combine text labels, distinct icons, and colour tokens.
- **Motion:** Respects `prefers-reduced-motion` media queries; zero unrequested motion.
- **No colour-only signalling:** connection states and alert severities each carry an icon and a word.
- **Motion:** none; no auto-playing content; no flashing.
- **Keyboard:** all controls (Mode switch, Pause, Acknowledge, filters) Tab-reachable with visible focus; no keyboard traps.
- **Chart summaries:** one-sentence text summary above each live chart (updated each refresh).
- **Time:** all times shown with timezone label; a toggle for local vs UTC ⬜ (nice to have).

---

## Micro-interactions
- **Hover:** Interactive tooltip with timestamp, metrics, flag state; table row highlight.
- **State transitions:** connection chip text changes; smooth transition. Optional notification toast on LIVE→STALE and STALE→LIVE (debounced, max one per 30 s) so a flapping link does not spam.
- **New alert:** banner appears at the top of the page and an alert toast fires once per alert id.
- **Loading:** skeleton placeholder or spinner on initial bundle/stream connect only.
- **Success:** toast notification ("Phone connected", "Session saved").
- **Error:** accessible inline alert banner with cause + fix; never raw tracebacks.

---

## Mobile Responsiveness Strategy
- Breakpoints 1200 / 768 px as in v1; verified at 375, 768, 1280 px.
- Live Overview on a phone browser is a **supported but secondary** use (viewing from the same private network requires `NADS_ALLOW_REMOTE_VIEW`; default is laptop-only).
- Responsive chart heights (~260 px), legends below, touch-friendly zoom controls.
- Priority: laptop/desktop is primary (project demo); mobile remains responsive and usable.

---

## Design Acceptance Checklist (used by todo_v2 tasks)
- [ ] Every Live page shows the connection chip and sample age.
- [ ] STALE/RECONNECTING/DISCONNECTED/WAITING/REPLAY each have text + icon + colour and are reachable in tests via a mocked live state.
- [ ] Provisional and Final events are visually and textually distinct.
- [ ] No Live chart interpolates across gaps or `NA`.
- [ ] Events table states *why* an event did or did not alert.
- [ ] No alert text contains "caused" or "fixed" (automated check).
- [ ] About page lists the v2 non-claims.

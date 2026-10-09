# DESIGN v2 — 5G-NADS Live Dashboard (live charts, alerts, stream-connection indicators)

> **Builds on:** `docs/planning/DESIGN.md` (v1). Everything in v1 DESIGN — philosophy, copy rules, tokens, typography, spacing, component conventions, accessibility — **still applies** unless overridden here. This document adds the **Live mode**, **alerts**, and **connection/stream-health indicators**, and the Android-side status UI.
> **Requirements:** `PRD_v2.md` FR-12, FR-16, FR-17, FR-18.
> No external design reference was provided; style is derived from v1's rule "avoid excessive UI decoration; prioritise technical interpretability".
> **Tooling caveat:** Streamlit is a rerun-based framework with limited push/real-time support. The Live mode is built on **periodic refresh of a fragment** reading state that a background thread keeps up to date. **Verify the exact Streamlit APIs for fragments/auto-refresh, session state and app testing against the current Streamlit docs when implementing** — they change between versions. Where this document asks for something Streamlit cannot do (true push, ARIA live regions, sub-second smooth chart updates), the fallback is stated.

---

## Design Philosophy

### Visual Style
- Unchanged: utilitarian, data-first, low chrome; one accent colour; semantic colours only for status.
- Live additions: **no flashing, no sound, no animation** beyond Streamlit's default spinner. "Live" is communicated by a **state label and a sample-age counter**, not by motion.

### Branding Direction
- Unchanged name/subtitle. Live mode adds a mode label: **"5G-NADS · Live"** vs **"5G-NADS · Replay"** in the page header so a user can never confuse recorded and live data.

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

### Screen L1 — Live Overview
- **Purpose:** the 5-second answer for *right now*, plus trust signals.
- **Components:**
  - **Connection chip** + sample age (top, full width).
  - **Alert banner** (only when an unacknowledged alert exists): severity chip, one-line hedged summary, **Acknowledge** button, link to Events & Alerts.
  - **Status banner:** `NORMAL` (green) / `ANOMALY DETECTED` (red) with severity chip, plus a **Provisional** badge if the current event is open. ML-only flag without rule evidence shows as a separate amber-bordered line: "Statistically unusual — no rule-based evidence (no alert)".
  - **Metric cards:** RSRP, RSRQ, SINR, PCI, NCI, NRARFCN (v1), each with delta from previous sample and a tiny age indicator when STALE.
  - **Network-state card:** Network type, Deployment mode (Unknown shown as "Unknown (not exposed by this device)"), Registered, Operator, Device, **Source** (Phone live / Replay).
  - **Score block:** baseline z (flag) and IF score (flag) shown separately; **edge score** (advisory) shown as a third, visually secondary line only when edge inference is enabled.
  - **Detected event** label (v1 categories, `NORMAL`, or `STATISTICAL_ONLY` for ML-only flags) + status (**Provisional / Final**) + start time + duration so far.
  - **Diagnosis, Evidence, Recommendation** from agents (v1), prefixed "Provisional —" while the event is open.
  - **Sparkline:** last 60 samples of RSRP and SINR with anomaly markers.
- **Layout (12-col):** R0 chip (12) · R1 alert banner (12, conditional) · R2 status banner (12) · R3 network-state (4) + 6 metric cards 2×3 (8) · R4 score (4) + event/severity/status (8) · R5 diagnosis (8) + recommendation (4) · R6 sparkline (12, optional).
- **Interactions:** Pause/Resume auto-refresh toggle (freezes the view for reading; chip says "PAUSED — new data still arriving"); Acknowledge alert; hover on card shows delta. No replay slider in Live mode.
- **Empty state:** WAITING state text with `host:port` and the pairing-token hint (token itself is **never** displayed).
- **Error state:** DISCONNECTED text with fix instruction; schema/contract mismatch → "Server and dashboard speak different message versions (server v2.x, dashboard v2.y). Update one of them." No tracebacks.
- **Loading state:** `st.spinner("Connecting to server…")` only for the first connect; thereafter the chip communicates state.
- **Responsive:** cards 2-col on tablet, 1-col on phone; chip + alert banner always on top.

### Screen L2 — Live Signals
- **Purpose:** RSRP/RSRQ/SINR over the selected rolling window with anomaly markers (v1 Screen 2 semantics).
- **Components:** three stacked time-series (shared x-axis, ~260 px each); anomaly markers (× red, with text in tooltip); cell-change markers (grey vertical lines); score-over-time chart with the threshold line; toggle baseline / IF / both; **one-sentence text summary above each chart** (e.g. "SINR fell from +3 dB to −7 dB at 12:04:21; event open").
- **Data windowing:** show last N minutes (5 / 15 / 60). **Downsample for rendering only above ~5,000 points** (v1 performance rule; never for scoring).
- **Interactions:** zoom/pan are preserved across refreshes where Streamlit allows ⚠️ (verify: a full rerender may reset zoom — fallback: a "Freeze view" toggle and an explicit "Reset zoom"). Hover shows timestamp, all three values, flag state, edge score if present.
- **Gaps:** when samples are missing (seq gap or time gap > `SESSION_GAP_SECONDS`) the line is **broken**, never interpolated (G2/G18). A grey band labelled "no data (n samples missing)" marks the gap. `NA` values leave gaps too.
- **Empty/Error/Loading:** v1 wording plus "No samples in the last N minutes."
- **Accessibility:** "Show data table" expander under each chart (latest 200 rows).

### Screen L3 — Live Cells & Network
- **Purpose:** PCI/NCI changes and network-type transitions in the live window without implying anomaly (v1 Screen 3).
- **Components:** PCI step line; NCI as categorical step line; NRARFCN line; network-type strip; transitions table (time, from → to); markers linking to open/closed anomaly events.
- **Copy rule (v1, retained):** "A cell change is normal network behaviour. It is highlighted here as an *event*, not as an anomaly."
- **States:** as L2.

### Screen L4 — Live Events & Alerts
- **Purpose:** list events (open and closed) and alerts; show agent evidence per event.
- **Components:**
  - **Events table:** id, start, end (or "open"), duration, type, severity, max score, **status (PROVISIONAL/FINAL)**, **alerted? (yes / no — reason)**. Reason values are fixed strings: `ML-only (no rule evidence)` (event type `STATISTICAL_ONLY`), `cell/network change only`, `below persistence/severity threshold`, `cooldown`, `alerted`.
  - **Event detail** (v1 layout): Signal / Cell / Network agent columns, Diagnosis, Recommendation, window chart, "Download event JSON".
  - **Alerts panel:** table of alerts (time, event, severity, channel(s) and delivery status, acknowledged by/at). Filter by severity/channel/ack.
  - **Alert channel status:** one row per channel (In-app, Phone, Webhook, Email) with `enabled / disabled` and last delivery result. A failed channel shows red text + icon + message ("Webhook timed out after 5 s") — red is appropriate here because it is a failure of the system's own output.
- **Interactions:** row select; Acknowledge; filter; download JSON.
- **Empty state:** "No events in this session yet. This does not guarantee the network is healthy." (v1 wording retained.)
- **Error state:** "Cannot load events from the server (HTTP 5xx / timeout). The live view of samples may still work — check Stream Health."
- **Responsive:** agent columns stack; alert table scrolls horizontally.

### Screen L5 — Stream Health
- **Purpose:** make the pipeline's own limitations visible (v1 Data Quality principle applied to the transport).
- **Components (all numbers computed by the server and shown as received):**
  - Connection timeline (state changes over the session).
  - **Latency:** p50 / p95 / max for *phone→server* (device timestamp vs server receipt; **caveat shown: depends on clock agreement**) and *server receipt→published*; sparkline.
  - **Completeness:** samples received, duplicates ignored, **sequence gaps** (count and ranges), samples re-sent after reconnect, samples dropped by the phone's queue (reported by the phone in `hello`/`ping`).
  - **Queue depth** on the phone (last reported) and dashboard subscriber queue drops.
  - **Clock skew** estimate with a warning if > `CLOCK_SKEW_WARN_SECONDS`.
  - **Model:** `model_version`, feature-order hash, whether edge model hash matches.
  - **Edge divergence** (if edge enabled): count of samples where |edge − server| > tolerance.
  - Session source (phone/replay), link type if reported.
- **Copy rule:** latency figures carry the footnote "Measured in this setup. No latency guarantee."
- **States:** as L2.

### Screens L6–L7 — Data Quality, About & Limitations
- Reused from v1. Additions to **About**: the full v2 non-claims list (PRD_v2 §Explicit Non-Claims), the "what is provisional" explanation, alert policy summary (what does *not* alert), and the statement that O-RAN integration, iOS collection and SMS alerts are **not implemented**.
- Data Quality note: "Live samples are saved as a C1 CSV; this page reads that file."

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
- No sound/vibration pattern is defined by the dashboard; the phone's local notification uses the platform default channel with **normal** importance. (A high-importance heads-up channel is a deliberate non-default.)
- **Acknowledge** stops re-display, not logging.
- **Suppression is visible:** Events table always states why an event did not alert.

### Alert severity presentation
LOW = info-blue chip, MEDIUM = amber chip, HIGH = red chip; each chip contains the word. LOW severity does **not** push to phone/webhook/email by default (configurable) *(proposed)*.

---

## Android Companion UI (collector app — streaming additions only)

The collector's existing screens are out of scope except for these additions:

- **Streaming settings** (new section): Server host, Port, Pairing token (masked, paste/QR optional ⬜), Stream toggle, "Test connection" button (result inline: "Connected · model if_v1" or the specific failure: unreachable / unauthorised / version mismatch).
- **Status strip** on the logging screen: `Streaming: Connected | Reconnecting (queue 37) | Off`, last ack time, dropped-from-queue counter. Uses text + icon.
- **Edge score (only if edge module enabled):** small secondary line "Edge score (advisory): 0.69". Never labelled "anomaly detected".
- **Alert notifications:** standard Android local notification, title/body as in *Alert anatomy*; tapping opens the app's status screen.
- **Battery/background guidance:** a one-time dialog explaining that some manufacturers stop background apps and linking to the system battery settings; no dark patterns.
- **Touch targets:** ≥ 48 dp (Android guideline; v1 used 44 px for custom web controls).
- **Out of scope:** redesigning the existing collector UI.

---

## Design System (v1 tokens reused; additions)

### Colours
v1 tokens are reused unchanged. New *semantic aliases* only (no new hues):

| Role | Token | Hex | Used for |
|---|---|---|---|
| State · LIVE | Normal | `#15803D` | LIVE chip |
| State · STALE / RECONNECTING | Warning | `#B45309` | STALE chip, ML-only line |
| State · WAITING / REPLAY | Info | `#0369A1` | WAITING, REPLAY-SOURCE |
| State · DISCONNECTED | Neutral 700 | `#334155` | Server unreachable |
| Badge · PROVISIONAL | Warning text on tint | `#B45309` on `#FFFBEB` | Event status badge |
| Badge · FINAL | Neutral text on tint | `#334155` on `#F1F5F9` | Event status badge |
| Chart · gap band | Slate 200 | `#E2E8F0` | "no data" band |
| Chart · edge score line | Slate 500, dashed | `#64748B` | Advisory edge score |

**Contrast check (WCAG 2.x relative-luminance formula, computed while writing this document):**

| Pair | Ratio | AA text (4.5) |
|---|---|---|
| `#0F172A` on white | 17.85 | pass |
| `#334155` on white | 10.35 | pass |
| `#64748B` on white | 4.76 | pass (just) |
| `#2563EB` on white | 5.17 | pass |
| `#15803D` on white | 5.02 | pass |
| `#B91C1C` on white | 6.47 | pass |
| `#B45309` on white | 5.02 | pass |
| `#0369A1` on white | 5.93 | pass |
| `#B45309` on `#FFFBEB` | 4.84 | pass |
| `#334155` on `#F1F5F9` | 9.45 | pass |
| `#64748B` on `#F8FAFC` (muted text on page bg) | 4.55 | pass (very narrow margin) |

> Note: several ratios printed in v1 DESIGN differ from these (e.g. v1 lists `#0F172A` as 15.6:1; the standard formula gives 17.85). All v1 tokens still pass AA, so nothing is invalidated — but **use the numbers above**, and re-check them with a contrast tool before relying on them, since the tint hex values (`#FFFBEB`, `#F1F5F9`) are Tailwind-palette values I used from memory. Muted text (`#64748B`) on the `#F8FAFC` page background has almost no margin; prefer `#475569` for important small text.

### Typography / Spacing / Grid
Unchanged from v1. Live numbers (age counters, latency) use the monospace stack so digits do not jitter horizontally.

### Component Library additions (Streamlit-native wherever possible)
- **Connection chip:** `st.markdown` with inline-styled span (icon + label + age); the *only* custom HTML. ⚠️ Verify `unsafe_allow_html` behaviour/security guidance in current Streamlit docs; fallback: `st.caption` with emoji icon and text.
- **Alert banner:** `st.container(border=True)` with 4 px left border in severity colour (v1 status-card pattern), plus `st.button("Acknowledge")`.
- **Badges:** text spans styled as small chips; fallback `st.caption("[PROVISIONAL]")`.
- **Auto-refresh region:** a Streamlit fragment with a run interval; everything inside re-reads shared live state. Static content (sidebar, About) lives outside it. ⚠️ Verify fragment API.
- **Toasts:** `st.toast` for "Phone connected", "Session saved to data/live/…", "Alert acknowledged". Persistent issues use `st.warning`/`st.error` with cause + fix.
- **Tables:** `st.dataframe`; IDs in monospace; null shown as `—` with tooltip "missing (NA)".

---

## Accessibility Requirements (v1 retained; additions)

- **WCAG target:** 2.1 AA for what Streamlit lets us control.
- **Live updates and screen readers:** Streamlit does not offer ARIA live-region control for auto-refreshing content ⚠️ (verify). Fallbacks: (a) a **Pause auto-refresh** toggle so assistive-tech users can read a stable page; (b) alerts and state changes also use `st.toast`/banners with text; (c) the Events and Alerts tables contain the same information as the charts.
- **No colour-only signalling:** connection states and alert severities each carry an icon and a word.
- **Motion:** none; no auto-playing content; no flashing.
- **Keyboard:** all controls (Mode switch, Pause, Acknowledge, filters) Tab-reachable with visible focus; no keyboard traps.
- **Chart summaries:** one-sentence text summary above each live chart (updated each refresh).
- **Time:** all times shown with timezone label; a toggle for local vs UTC ⬜ (nice to have).

---

## Micro-interactions
- **Hover:** Plotly tooltip with timestamp, metrics, flag state; table row highlight.
- **State transitions:** connection chip text changes; no animation. Optional single `st.toast` on LIVE→STALE and STALE→LIVE (debounced, max one per 30 s) so a flapping link does not spam.
- **New alert:** banner appears at the top of the page and a toast fires once per alert id.
- **Loading:** spinner on first connect only.
- **Success:** `st.toast("Phone connected")`, `st.toast("Session saved")`.
- **Error:** inline `st.error` with cause + fix; never tracebacks.

---

## Mobile Responsiveness Strategy (Streamlit dashboard)
- Breakpoints 1200 / 768 as in v1; verify manually at 375, 768, 1280 px.
- Live Overview on a phone browser is a **supported but secondary** use (viewing from the same private network requires `NADS_ALLOW_REMOTE_VIEW`; default is laptop-only).
- Charts ~260 px high, legends below, scroll-zoom disabled on touch.
- Priority: laptop/desktop is primary (project demo); mobile must remain *usable*.

---

## Design Acceptance Checklist (used by todo_v2 tasks)
- [ ] Every Live page shows the connection chip and sample age.
- [ ] STALE/RECONNECTING/DISCONNECTED/WAITING/REPLAY each have text + icon + colour and are reachable in tests via a mocked live state.
- [ ] Provisional and Final events are visually and textually distinct.
- [ ] No Live chart interpolates across gaps or `NA`.
- [ ] Events table states *why* an event did or did not alert.
- [ ] No alert text contains "caused" or "fixed" (automated check).
- [ ] About page lists the v2 non-claims.

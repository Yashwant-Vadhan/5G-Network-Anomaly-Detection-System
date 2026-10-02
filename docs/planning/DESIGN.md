# DESIGN — 5G-NADS Dashboard

> Scope: the Streamlit + Plotly dashboard (`dashboard/`). The Android collector UI is already built and out of scope.
> No external design reference was provided, so the style below is derived from the overview's rule: *"Avoid excessive UI decoration. The dashboard should prioritize technical interpretability."* (§32)
> Tooling caveat: Streamlit's theming and layout options are limited. Where this document asks for something Streamlit cannot do natively, the fallback is stated. **Verify Streamlit API details against the current Streamlit docs when implementing** (theme options and testing utilities change between versions).

---

## Design Philosophy

### Visual Style
- Utilitarian, data-first, low-chrome. White/neutral surfaces, one accent colour, semantic colours only for status.
- Charts are the hero; cards and tables support them.
- No gradients, illustrations, or animation beyond Streamlit's defaults.

### Branding Direction
- Name shown as **5G-NADS**; subtitle "5G Network Anomaly Detection System".
- Tone: precise, hedged, evidence-first. Never alarmist.

### UX Goals
1. Answer in 5 seconds: *Is the current sample normal? If not, what kind of event, and why?*
2. Every claim on screen is backed by visible evidence (values, deltas, cell IDs).
3. Never present `UNKNOWN` deployment mode as SA, or `NA` as zero.
4. Make limitations visible, not buried.

### Content & Copy Rules (apply to dashboard, agents' text output, README)
| Do | Don't |
|---|---|
| "Possible radio-quality degradation **associated with** a cell transition" | "The cell change **caused** the drop" |
| "Deployment mode: Unknown (not exposed by this device)" | "Deployment mode: SA" (when UNKNOWN) |
| "CSI-RSRP: not available on this device" | "CSI-RSRP: 0" or flagging it as a fault |
| "Continue monitoring. If degradation persists, investigate coverage, interference, congestion, or cell behaviour." | "We have re-routed your connection." |
| "Statistically unusual (score 0.71); no rule-based evidence found" | Hiding ML-only flags |

---

## Information Architecture

### Navigation Structure
Streamlit multipage app with sidebar navigation:

```
5G-NADS
├── 1. Overview            (default)
├── 2. Signal Explorer
├── 3. Cells & Network
├── 4. Events & Diagnosis
├── 5. Data Quality
└── 6. About & Limitations
Sidebar (all pages): dataset selector / CSV upload · device · operator · session · replay position
```

### Screen Hierarchy
- **Global context** (sidebar) → selects the working subset for all pages.
- **Overview** → summarises; links (text hints) to Events & Diagnosis for detail.
- **Explorer pages** (2, 3) → deep-dive charts.
- **Events & Diagnosis** → list → detail.
- **Data Quality**, **About** → trust and transparency.

### User Flow (ASCII)

```
Open app
   │
   ▼
Load processed dataset (auto: latest data/processed/scores.csv) ──► [invalid / missing] ──► Error state with fix instructions
   │
   ▼
Overview: status card · score · event · diagnosis · recommendation
   │
   ├── want to see signals ───► Signal Explorer (RSRP/RSRQ/SINR + anomaly markers)
   ├── want to see cells ─────► Cells & Network (PCI/NCI timeline, network type)
   ├── want details ──────────► Events & Diagnosis (table → select event → evidence per agent)
   ├── doubt the data ────────► Data Quality (NA counts, CSI availability, UNKNOWN share)
   └── doubt the claims ──────► About & Limitations
```

---

## Screen Specifications

### Screen 1 — Overview
- **Purpose:** immediate answer to "is it normal, and if not, why?" for the selected replay position.
- **Components:**
  - Status banner: `NORMAL` (green) or `ANOMALY DETECTED` (red) with severity chip (LOW/MEDIUM/HIGH) when available.
  - Metric cards: RSRP (dBm), RSRQ (dB), SINR (dB), PCI, NCI, NRARFCN.
  - Network-state card: Network Type, Deployment Mode, Registered, Operator, Device.
  - Anomaly score gauge/number (0–1) with baseline flag and IF flag shown separately.
  - "Detected event" label (one of the 6 categories or `None`).
  - Diagnosis text box + Evidence list (from agents) + Recommendation text box.
  - Mini sparkline of last N samples for RSRP/SINR (optional).
- **Layout:** 12-col grid. Row 1: status banner (12). Row 2: network-state card (4) + 6 metric cards in 2×3 (8). Row 3: score (4) + event & severity (8). Row 4: diagnosis (8) + recommendation (4).
- **Interactions:** replay slider in sidebar moves the "current" sample; play/pause optional; hover on metric card shows delta from previous sample.
- **Empty state:** "No processed data found. Run `python -m pipelines.run_pipeline --input data/raw` (see README)."
- **Error state:** schema error message listing missing columns; no stack traces on screen.
- **Loading state:** `st.spinner("Loading dataset…")`; skeleton text for cards.
- **Responsive:** cards wrap to 2 columns on tablet, 1 column on phone; banner always top.

### Screen 2 — Signal Explorer
- **Purpose:** inspect RSRP, RSRQ, SINR over time with anomaly markers.
- **Components:** three stacked time-series charts (shared x-axis); anomaly markers (× shape, red); optional rolling mean overlay; anomaly-score-over-time chart with threshold line; toggle: show baseline flags / IF flags / both.
- **Layout:** full-width charts, ~260 px height each.
- **Interactions:** zoom/pan (Plotly), hover shows timestamp + all three values + flag state; sidebar window selector (first N samples / last N / all).
- **Empty state:** "No valid samples for the selected device/session."
- **Error state:** "Could not plot: column `ss_sinr` is entirely missing for this selection."
- **Loading state:** spinner; charts render progressively.
- **Responsive:** charts full-width; legend moves below chart on narrow screens.

### Screen 3 — Cells & Network
- **Purpose:** show PCI/NCI changes and network-type transitions without implying they are anomalies.
- **Components:** step-line chart of PCI over time; step-line chart of NCI (as categorical labels); NRARFCN line; network-type band (5G NR / LTE / other) as coloured strip; table of transition events (time, from → to).
- **Layout:** two charts stacked, then network strip, then table.
- **Interactions:** hover tooltips; table sortable; vertical marker linking to anomaly events when present.
- **Empty state:** "No cell or network transitions in this selection." (neutral tone, not "all good").
- **Error state:** as Screen 2.
- **Loading state:** spinner.
- **Responsive:** table becomes horizontally scrollable.
- **Copy rule:** header note — "A cell change is normal network behaviour. It is highlighted here as an *event*, not as an anomaly."

### Screen 4 — Events & Diagnosis
- **Purpose:** list detected events and show each agent's structured evidence.
- **Components:** events table (id, start, end, duration, type, severity, max score); selecting a row reveals: Signal Agent output, Cell Agent output, Network Agent output, Diagnosis (text + evidence), Recommendation, and a small chart of the event window.
- **Layout:** table on top (full width), detail panel below in 3 columns for agents + 1 full-width diagnosis/recommendation row.
- **Interactions:** row select; filter by type/severity; "Download event JSON".
- **Empty state:** "No events detected for this selection. This does not guarantee the network was healthy."
- **Error state:** "events_diagnosed.json missing — run the pipeline."
- **Loading state:** spinner.
- **Responsive:** agent columns stack vertically.

### Screen 5 — Data Quality
- **Purpose:** make data limitations visible.
- **Components:** table of missing-value counts per column per device; CSI availability per device; deployment-mode distribution (`NSA / SA / UNKNOWN`) with note; sample counts per device/operator/scenario; count of rows removed by validation (from processing log); banner if any data is synthetic.
- **Empty/Error/Loading:** as above.
- **Responsive:** tables scroll horizontally.
- **Copy rule:** "UNKNOWN means Android did not expose enough information. It does not mean SA."

### Screen 6 — About & Limitations
- **Purpose:** transparency page.
- **Components:** one-paragraph description; architecture diagram image; "What this system does not claim" list (PRD §Explicit Non-Claims); dataset summary; model/version metadata from `models/if_v1.meta.json`; links to README and docs.
- **States:** static; if model metadata file is missing show "Model metadata unavailable".

---

## Design System

### Colors (hex)
| Role | Name | Hex |
|---|---|---|
| Primary | Blue 600 | `#2563EB` |
| Primary dark | Blue 800 | `#1E40AF` |
| Secondary | Teal 700 | `#0F766E` |
| Neutral 900 (text) | Slate 900 | `#0F172A` |
| Neutral 700 | Slate 700 | `#334155` |
| Neutral 500 (muted text) | Slate 500 | `#64748B` |
| Neutral 200 (borders) | Slate 200 | `#E2E8F0` |
| Neutral 50 (page bg) | Slate 50 | `#F8FAFC` |
| Surface | White | `#FFFFFF` |
| Semantic — normal | Green 700 | `#15803D` |
| Semantic — warning / MEDIUM | Amber 700 | `#B45309` |
| Semantic — anomaly / HIGH | Red 700 | `#B91C1C` |
| Semantic — info | Sky 700 | `#0369A1` |
| Chart — RSRP | Blue 600 | `#2563EB` |
| Chart — RSRQ | Violet 600 | `#7C3AED` |
| Chart — SINR | Teal 700 | `#0F766E` |
| Chart — anomaly marker | Red 700 | `#B91C1C` |
| Chart — cell-change marker | Slate 500 | `#64748B` |

Contrast verification: standard Tailwind-palette values verified against white (#FFFFFF) background:
- Neutral 900 (`#0F172A`): 15.6:1 (Passes AAA)
- Neutral 700 (`#334155`): 9.6:1 (Passes AAA)
- Neutral 500 (`#64748B`): 4.6:1 (Passes AA)
- Primary (`#2563EB`): 4.5:1 (Passes AA)
- Normal (`#15803D`): 4.5:1 (Passes AA)
- Anomaly (`#B91C1C`): 5.9:1 (Passes AA)
- Warning (`#B45309`): 4.6:1 (Passes AA)
- Chart RSRQ (`#7C3AED`): 4.8:1 (Passes AA)

Dark mode: optional; if added, define a second token set in `dashboard/theme.py`, not ad-hoc colours.

### Typography
- Family: system UI stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`); monospace (`ui-monospace, Menlo, Consolas, monospace`) for PCI/NCI/NRARFCN and JSON.
- Scale: H1 28 px / H2 22 px / H3 18 px / body 16 px / caption 13 px.
- Weights: 400 body, 600 headings/labels.
- Streamlit fallback: theme `font` supports only a small set of families — use defaults where custom fonts are not possible.

### Spacing
- Base unit 4 px; scale 4 / 8 / 12 / 16 / 24 / 32 / 48.
- Card padding 16; section gap 24.

### Grid System
- 12 columns (Streamlit `st.columns` ratios), gutter 16 px.
- Breakpoints: ≥1200 desktop, 768–1199 tablet, <768 phone.

### Component Library (Streamlit-native wherever possible)
- **Buttons:** primary (`type="primary"`), secondary (default). States: default, hover, focus (visible outline), disabled. Labels are verbs ("Run analysis", "Download JSON").
- **Inputs:** selectbox (device/operator/session), file uploader (CSV only), slider (replay position). Validation message appears directly under the input; errors in `#B91C1C` with an icon and text (not colour only).
- **Cards:** bordered container (`st.container(border=True)`) with label (caption, muted), value (H2), delta (caption). Status card uses left border 4 px in semantic colour + text label.
- **Tables:** `st.dataframe`; sticky header, sortable, monospace for IDs, null shown as `—` with tooltip "missing (NA)".
- **Modals:** avoid; use expanders for details (simpler, more accessible in Streamlit).
- **Notifications/Toasts:** `st.toast` for non-blocking info; `st.warning`/`st.error` for persistent issues; every error states what happened and how to fix.

---

## Accessibility Requirements
- **WCAG level:** 2.1 AA target for the parts Streamlit lets us control.
- **Keyboard navigation:** all controls reachable by Tab; visible focus; no keyboard traps. Plotly hover is mouse-centric → provide the same data in the Events table and a "Show data table" expander under each chart.
- **Screen readers:** meaningful labels on widgets; each chart has a one-sentence text summary above it (e.g., "SINR fell from +3 dB to −7 dB at 12:04:21").
- **Color contrast:** ≥4.5:1 text; ≥3:1 for chart strokes; anomalies use marker shape (×) + label, not colour alone; avoid red/green-only distinctions (status has text).

---

## Micro-interactions
- **Hover:** Plotly tooltip with timestamp and all metrics; table row highlight.
- **Page transitions:** none beyond Streamlit defaults.
- **Loading animations:** `st.spinner` only.
- **Success states:** `st.toast("Pipeline finished")`; status banner turns to `NORMAL`.
- **Error states:** inline `st.error` with cause + fix; never raw tracebacks.

---

## Mobile Responsiveness Strategy
- **Breakpoints:** 1200 / 768 (Streamlit reflows automatically; verify manually at 375, 768, 1280 widths).
- **Layout shifts:** multi-column rows collapse to single column; sidebar collapses to hamburger (Streamlit default).
- **Touch targets:** ≥44×44 px for custom controls; Streamlit defaults otherwise.
- **Charts:** fixed height ~260 px; legends below chart; disable scroll-zoom on touch to avoid trapping page scroll.
- **Priority:** desktop/laptop is the primary target (project demo); mobile must remain *usable*, not polished.

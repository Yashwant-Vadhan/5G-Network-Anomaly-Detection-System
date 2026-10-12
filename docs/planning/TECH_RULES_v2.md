# TECH_RULES v2 — 5G-NADS Real-Time Extension

> **Builds on:** `docs/planning/TECH_RULES.md` (v1). All v1 rules remain binding unless this document amends them. Binding for humans **and** AI coding agents.
> **Requirements:** `PRD_v2.md`. **Design:** `DESIGN_v2.md`. **Agent contracts:** `agent_architecture.md` (C6 — **unchanged**).
> Version pins, library behaviours and Android/React/FastAPI API details below are *design intent*. **Verify exact versions and APIs against current official docs at implementation time.** Where I am unsure of an API, the text says so.

---

## 0. What Changes vs v1 (read first)

| Area | v1 | v2 |
|---|---|---|
| Execution model | Batch pipeline, files, no server | Batch pipeline **plus** a long-running local server (`streaming/`) |
| Authentication | N/A by design | **Required** (pairing token) for any non-loopback binding (amends v1 Security Rules) |
| G1 | Collector ≠ ML pipeline | **Amended** (below): measurement path stays ML-free; optional edge module is isolated and advisory |
| Contracts | C1–C6 | C1–C6 unchanged; **C7–C9 added** |
| Guardrails | G1–G16 | G1 amended, G2–G16 unchanged, **G17–G26 added** |
| Agents | Run on completed events in batch | Same code, run on event open/change/close; **no agent code changes** |
| LLM | Optional, off by default (G13) | Unchanged; must have **no effect** on the live path when off and none on flags when on |
| Storage | `data/raw|processed|sample`, `models/` | Adds `data/live/` (append-only live captures, alert log) |

Overview amendments A1–A3 (PRD_v2) must be merged before Phase 11 starts.

---

## Architecture Overview

### Frontend Architecture
- **React SPA (Vite + TypeScript)** with Tailwind/vanilla CSS tokens matching `DESIGN_v2`. Replaces Streamlit for all v2.1 interfaces; v1 Streamlit remains frozen as a batch baseline record.
- **Shared code for Replay and Live:** Overview, Signal Explorer, Cells & Network, Events & Diagnosis, and Data Quality use identical visualization components; only the data adapter differs (bundle vs WebSocket).
- **Rule (carried over, G30):** The frontend contains **no ML, threshold, or diagnostic logic**. All scores, flags, groupings, and diagnoses are computed server-side or precomputed in the demo bundle.
- **Rule (carried over):** The dashboard never opens the ingest endpoint and never holds the phone's ingest token; it accesses telemetry via viewer tickets and cookies (C10).
- **Accessibility:** Native ARIA live regions (`aria-live="polite"`) for alerts and status changes; WCAG 2.1 AA compliant semantic HTML and keyboard navigation.

### Backend Architecture
```
Android collector ──(C7 over WebSocket)──► streaming/server.py (FastAPI + uvicorn)
                                              │  auth · validate · dedupe · ack
                                              ▼
                                   streaming/session_manager.py   (per client_id+session buffers)
                                              ▼
                                   streaming/engine.py            (calls ml/* — same code as batch)
                                              ▼
                       ml.preprocessing ► ml.feature_engineering ► ml.anomaly_detection ► ml.anomaly_analysis
                                              ▼
                                   streaming/event_tracker.py     (open / update / close, PROVISIONAL|FINAL)
                                              ▼
                                   agents/orchestrator.py         (unchanged: Signal·Cell·Network → Diagnosis → Recommendation)
                                              ▼
                      ┌───────────────────────┼─────────────────────────┐
                      ▼                       ▼                         ▼
        streaming/hub.py (pub/sub)   streaming/alerts/ (policy,   streaming/store.py
        → WS /api/v1/live + REST       dispatch, channels)         data/live/*.csv, alerts.jsonl
                      ▼
              React SPA dashboard (Live mode)
```
- The server is **one process, one event loop**. CPU-bound scoring is tiny at ~1 sample/3 s; if profiling ever shows blocking, run the engine call in a thread executor — do **not** add a message broker.
- **Agents remain plain deterministic Python.** No agent framework, no LLM in the core path (v1 Decision Record stands).

### Database Architecture
- Still **no database**. Live state is in memory (bounded), durable state is append-only files:
  - `data/live/<client>_<session>_<YYYYMMDD>_<HHMM>.csv` — C1-format capture, appended per sample, `fsync` on session close.
  - `data/live/<…>.meta.json` — session metadata (`source`: `phone|replay`, app version, model version, status `OPEN|CLOSED|INCOMPLETE`, sha256 on close).
  - `data/live/alerts.jsonl` — one C9 record per line, append-only.
- `data/live/` is git-ignored. `scripts/promote_live_session.py` is the only path from `data/live/` to `data/raw/` (copies, never moves; adds manifest line) — G7/G22.
- Rationale unchanged: prototype scale; files keep reproducibility simple.

### Deployment Architecture
- Local: `make serve` (server), `make dashboard` (Streamlit), `make replay CSV=…` (replay tool), `make demo-live` (all three with a bundled sample). CI runs lint + tests (+ streaming tests) only; **no deployment step**.
- Phone ↔ laptop link options, in order of preference for measurement hygiene (⚠️ to be validated by `T12-009`):
  1. **USB with `adb reverse tcp:<port> tcp:<port>`** — phone connects to `127.0.0.1:<port>`; no LAN exposure; no Wi-Fi needed. *(Verify `adb reverse` works on both test phones.)*
  2. **Private Wi-Fi / laptop hotspot** — server binds the LAN address with a token.
  3. **Cellular to a remote server — not supported** in v2 (perturbs the measured radio; would also require TLS and a public endpoint).
- Docker/cloud: **not in v2.**

---

## Decision Record — Real-Time Transport and Dashboard

| Question | Decision | Alternatives considered | Why |
|---|---|---|---|
| Phone→server transport | **WebSocket** (JSON text frames) | HTTP POST per sample; MQTT; gRPC streaming; Server-Sent Events | The requirement names WebSocket (`limitations…` §2.2). Bidirectional (acks, `alert` push to phone), simple on Android with a mainstream HTTP client, no broker. MQTT would add a broker dependency; gRPC adds build complexity for ~1 msg/3 s. |
| Fallback when WebSocket is blocked | `POST /api/v1/ingest/batch` (same C7 `sample` objects, array body) | none | Lets the phone flush its queue over plain HTTPS/HTTP if a network blocks upgrades; same validation path. *(Should Have.)* |
| Server framework | **FastAPI + uvicorn** | Starlette only; Flask-SocketIO; aiohttp | Native async WebSocket + pydantic validation for wire schemas; widely used. *(Verify current versions.)* |
| Wire schema library | **pydantic models at the boundary**, internal `dataclasses` (C6 unchanged) | dataclasses only; JSON Schema by hand | Validation errors are explicit and testable; JSON Schema can be exported for golden-file contract tests. |
| Dashboard live updates | **React SPA (Vite + TS)** (v2.1) | Stay on Streamlit; Dash; Grafana | Native client state and direct WebSocket handling; v1 Streamlit preserved frozen for batch replay. |
| Server→dashboard push | `WS /api/v1/live` consumed natively by browser WebSocket client; REST for initial sync/backfill | Long polling REST only | Push keeps latency low; REST gives a deterministic resync after any reconnect. |
| Edge model format | **Decided by spike `T12-011`**: (a) export trees + scaler params to JSON and implement path-length traversal in Kotlin, or (b) ONNX | TFLite (not applicable to sklearn trees) | (a) has no runtime dependency but needs custom code and a parity test; (b) may be less code if the converter supports `IsolationForest` — **I have not verified this; check the current `skl2onnx` supported-operators list.** |
| Online learning / retraining | **No** | Incremental IF, periodic retrain | Model is pinned (`if_v1`); retraining would break parity and evaluation validity. |

---

## Tech Stack (additions only; v1 table still applies)

| Layer | Technology | Purpose | Why Chosen | Alternatives Considered |
|---|---|---|---|---|
| Server | FastAPI, uvicorn (with a WebSocket implementation) | Ingest + live API | See Decision Record | Starlette, aiohttp |
| Wire schema | pydantic (v2 line — *verify*) | Validate C7–C9 | Comes with FastAPI stack; explicit errors | hand-rolled validation |
| HTTP client (tests, webhook) | httpx | Webhook channel, API tests | Sync+async, timeouts, test transport | requests |
| WS client (Python) | `websockets` (verify) | `scripts/replay_stream.py`, tests | Small, async | `websocket-client` |
| Email alerts | stdlib `smtplib`/`email` | Optional email channel | No new dependency | third-party mail APIs |
| Android WebSocket | OkHttp WebSocket (verify current version) | `StreamClient` | Widely used on Android | Ktor client, Java-WebSocket |
| Android queue | Room (SQLite) **or** append-only file (decide in `T12-003`) | Unacked sample buffer | Survives process death | in-memory only (loses data) |
| Android secrets | EncryptedSharedPreferences / Keystore-backed storage (verify current AndroidX API status) | Token storage | Avoids plaintext token | plain SharedPreferences |
| Android service | Foreground service (type per current Android requirements — **verify**) | Keep logging/streaming alive | Required by modern Android background limits | WorkManager (not suited to continuous work) |
| Edge | Custom Kotlin scorer (default plan) or ONNX Runtime Mobile | On-device IF score | See spike | — |
| Load/soak | pytest + `scripts/replay_stream.py` | Latency, soak, recovery | No new tooling | Locust (unnecessary) |

---

## Folder Structure (additions marked `+`)

```
5G-NADS/
├── android-collector/
│   ├── 5GNetworkTester/                # existing app; + streaming package (StreamClient, SampleQueue, StreamSettings)
│   └── edge-inference/                 # + OPTIONAL separate Gradle module (G1 amended)
├── streaming/                          # + new Python package
│   ├── schema.py                       #   C7–C9 pydantic models + version constant
│   ├── server.py                       #   FastAPI app, routes, auth dependency
│   ├── session_manager.py              #   buffers, seq/dedupe, rollover
│   ├── engine.py                       #   calls ml/* per sample
│   ├── event_tracker.py                #   open/update/close, PROVISIONAL|FINAL
│   ├── hub.py                          #   bounded pub/sub to live subscribers
│   ├── store.py                        #   data/live writers, sha256 finalise
│   ├── metrics.py                      #   latency/gap counters
│   └── alerts/
│       ├── policy.py                   #   pure function: event state → alert decision
│       ├── dispatcher.py               #   cooldown, dedupe, fan-out, failure isolation
│       └── channels/{in_app,phone,webhook,email}.py
├── ml/                                 # unchanged API; may gain small pure helpers needed for incremental use
├── agents/                             # UNCHANGED
├── dashboard/
│   ├── live_client.py                  # + background consumer + connection state machine
│   └── pages/ (existing) + live_*.py   # + Live pages
├── data/live/                          # + git-ignored
├── scripts/
│   ├── replay_stream.py                # +
│   ├── promote_live_session.py         # +
│   └── export_contract_examples.py     # + writes JSON Schema / golden examples
├── tests/
│   ├── streaming/                      # + unit, integration, parity, soak, security
│   ├── fixtures/stream/                # + golden C7/C8/C9 JSON, edge parity vectors
│   └── test_guardrails_v2.py           # + G17–G26
├── models/ if_v1.joblib, if_v1.meta.json, if_v1.edge.json (+ optional)
└── docs/ streaming_architecture.md, streaming_protocol.md, streaming_security.md, edge_inference.md (if built), results_v2.md, decisions.md, …
```

---

## Data Contracts (new): C7, C8, C9

> C1–C6 unchanged. Same change rule as v1: a contract changes only by a PR that updates this section, `streaming/schema.py`, the golden examples in `tests/fixtures/stream/`, and affected tests. **`schema_version` is an integer; start at `2`.** Any incompatible change increments it; the server rejects mismatched clients with `error.code = "VERSION_MISMATCH"`.

### C7 — Ingest protocol (phone ⇄ server), JSON over WebSocket `ws://<host>:<port>/api/v1/ingest`

**Connection:** HTTP upgrade with header `Authorization: Bearer <token>`. Missing/invalid token → upgrade refused (HTTP 401) or close code `4401`.

**Client → server messages** (all have `"type"` and `"schema_version"`):

`hello` — first message after connect
```json
{
  "type": "hello", "schema_version": 2,
  "client_id": "b1e2c3d4-…",            // random UUID generated at install; no hardware identifiers
  "session_label": "redmi-walk-01",       // free text, no PII, no precise location
  "device": "Redmi 13 5G", "manufacturer": "Xiaomi", "android": "14",
  "operator": "Airtel", "app_version": "1.3.0",
  "resume_from_seq": 118,                 // next seq the phone will send; omit/0 for a new session
  "queue_depth": 0, "dropped_from_queue": 0,
  "edge": {"enabled": false, "model_version": null, "feature_hash": null}
}
```
`sample` — one per measurement
```json
{
  "type": "sample", "schema_version": 2,
  "seq": 119,                             // strictly increasing integer within (client_id, session)
  "sent_at": "2026-10-09T10:15:03.412+05:30",
  "payload": {                            // exactly the C1 columns; null/\"NA\" = NA; sentinels sent as-is
    "timestamp": "28-09-26 22:42:06", "device": "…", "manufacturer": "…", "android": "…", "operator": "…",
    "network_type": "5G NR", "deployment_mode": "UNKNOWN", "display_override": "…", "registered": true,
    "ss_rsrp": -97, "ss_rsrq": -11, "ss_sinr": 3,
    "csi_rsrp": null, "csi_rsrq": null, "csi_sinr": null,
    "pci": 336, "nci": 123456789, "nrarfcn": 631392
  },
  "edge": {"if_score": 0.69, "model_version": "if_v1", "feature_hash": "…"}   // optional, advisory
}
```
`ping` `{ "type":"ping", "queue_depth": n, "dropped_from_queue": m }` · `bye` `{ "type":"bye", "reason":"user_stopped" }`

> **Timestamp (resolved by v1 EDA, Open Question 1):** `payload.timestamp` is the collector's CSV string — `dd-MM-yy HH:mm:ss`, device-local, **no UTC offset** (ISO-8601 also occurs in v1 data). The server parses it with the existing `parse_timestamps` (`format="mixed"`, `dayfirst=True`); do not invent a second format. Because it carries no timezone, **latency and clock-skew are computed only from `sent_at`** (ISO-8601 with offset) versus server receipt, never from `payload.timestamp`.

**Server → client messages**

| type | fields | meaning |
|---|---|---|
| `hello_ack` | `session_id`, `server_time`, `last_seq_acked`, `model_version`, `schema_version`, `limits{max_message_bytes, max_msgs_per_min}` | Accepts the session; tells the phone where to resume |
| `ack` | `seq` (cumulative: everything ≤ seq is stored) | Phone may delete queued items ≤ seq |
| `error` | `code`, `message`, `fatal` (bool), `seq?` | See error codes |
| `alert` | C9 object (compact) | Server → phone push for local notification |
| `pong` | `server_time` | Heartbeat reply |

**Rules**
1. **Idempotent:** a `sample` with `seq ≤ last_seq_acked` is acknowledged again and **not** reprocessed.
2. **Gaps:** `seq` jumping forward is accepted but recorded as a **sequence gap** (count and range) in metrics; the engine treats the time gap per the normal session-gap rule. **Never interpolate or synthesise missing samples (G18).**
3. **Ack cadence:** cumulative `ack` at least every 5 samples or every 5 s, whichever first *(proposed)*.
4. **Heartbeat:** phone sends `ping` every 15 s if no sample sent; server closes silent connections after 45 s *(proposed)*. The **session** survives a closed connection for `SESSION_RESUME_WINDOW_SECONDS` *(proposed 600 s)*.
5. **Limits:** max message size `MAX_MESSAGE_BYTES` (proposed 8 KiB); max `MAX_MSGS_PER_MIN` per client (proposed 120; normal rate is ~20/min plus backlog flush — flush is paced by acks, so allow burst via a token-bucket with a documented burst size).
6. **Backpressure:** phone sends at most `W` unacked samples in flight (proposed W = 50).
7. **Validation:** payload is converted to a one-row DataFrame and passed through the **same** `ml.schema` validation and the v1 preprocessing functions (`coerce_numeric`, `flag_invalid`, `add_missing_flags`) as batch: the `NA` token and every `SENTINEL_INTS` value (`2147483647`, `-1`, `99`, `999` per EDA) → missing; `deployment_mode ∈ {NSA, SA, UNKNOWN}`; unexpected/missing keys rejected. ⚠️ Whether `-1`/`99` are applied per column is checked in `T10-015`.

**Error codes**

| code | fatal | cause |
|---|---|---|
| `UNAUTHORIZED` (close 4401) | yes | bad/missing token |
| `VERSION_MISMATCH` (close 4426) | yes | `schema_version` unsupported |
| `BAD_MESSAGE` | no | JSON/pydantic validation failure (message names the field, never echoes the token) |
| `SCHEMA_ERROR` | no | C1 validation failed (maps to `ml.schema.SchemaError`) |
| `RATE_LIMITED` | no | too many messages |
| `TOO_LARGE` (close 1009) | yes | message exceeds cap |
| `SESSION_CONFLICT` | yes | another live connection owns this `client_id` session |
| `INTERNAL` | no/yes | unexpected server fault (logged with correlation id; no traceback sent) |

### C8 — Live API (server ⇄ dashboard)

**Loopback-only by default; configurable via CORS/Origin allow-lists in hosted mode.**
Authentication is enforced per-session (Contract C10). REST endpoints require either `Authorization: Bearer <token>` or the session `HttpOnly` viewer cookie. Because browser WebSocket clients cannot set custom headers, `WS /api/v1/live` authenticates via a first-frame message `{"type": "auth", "ticket": "…"}` sent within 5 seconds of connection. The ticket is obtained via `POST /api/v1/live-sessions/{id}/ticket` (single-use, 30 s TTL); **tickets are never passed as query parameters in URLs**, preventing leakage into access/proxy logs.

`WS /api/v1/live` — server → dashboard events, each with `type`, `schema_version`, `server_time`, `session_id`:

| type | payload |
|---|---|
| `snapshot` | on connect: latest sample, state, open events, last N alerts |
| `sample` | one `ScoredSample` (all C4 columns for the row **plus** `seq`, `received_at`, `scored_at`, `published_at`, `edge_if_score?`, `edge_divergence?`, `model_eligible`) |
| `event_open` / `event_update` / `event_closed` | C5-compatible event + `"status": "PROVISIONAL"\|"FINAL"` + `"alert_decision": {"alerted": bool, "reason": "…"}` |
| `alert` | C9 |
| `connection` | `{state: LIVE\|STALE\|RECONNECTING\|WAITING, last_sample_age_s, source: phone\|replay}` (server-side authoritative state; the dashboard adds DISCONNECTED when *it* cannot reach the server) |
| `dropped` | `{count}` — this subscriber's queue overflowed; client must resync via REST |
| `heartbeat` | every 5 s |

REST (JSON; all paginated, hard cap `MAX_PAGE=1000`):

| Method & path | Returns |
|---|---|
| `GET /healthz` | `{status, version, uptime_s}` — no token, no sensitive data |
| `GET /api/v1/sessions` | session list with `source`, status, counts |
| `GET /api/v1/sessions/{id}/samples?since_seq=&limit=` | `ScoredSample[]` |
| `GET /api/v1/sessions/{id}/events` | events (C5-compatible + status) |
| `GET /api/v1/alerts?since=&ack=` | C9 list |
| `POST /api/v1/alerts/{alert_id}/ack` | marks acknowledged (idempotent) |
| `GET /api/v1/model` | `model_version`, feature list/hash, thresholds in force |
| `GET /api/v1/metrics` | latency percentiles, gaps, drops, skew, queue stats |

Status codes: `200`, `400` (bad parameter), `401`, `404`, `409` (conflict), `429`, `500` (generic body, correlation id). Error body: `{"error": {"code": "…", "message": "…", "correlation_id": "…"}}`. Never include stack traces.

**Versioning:** URL prefix `/api/v1`; payload `schema_version`. Additive fields are allowed within a version; clients must ignore unknown fields. Removing/renaming a field or changing a meaning ⇒ new `schema_version`.

### C9 — Alert record (`alerts.jsonl`, `alert` messages, webhook body)
```json
{
  "alert_id": "al-000017", "created_at": "2026-10-09T10:15:41+05:30",
  "event_id": "redmi-1-e003", "session_id": "redmi-1", "source": "phone",
  "kind": "NEW",                         // NEW | ESCALATION | RESOLVED
  "severity": "MEDIUM", "anomaly_type": "PERSISTENT_POOR_QUALITY",
  "event_status": "PROVISIONAL",
  "title": "MEDIUM · Persistent poor radio quality (possible)",
  "body": "SINR below the configured poor-quality level for 24 s; RSRQ also degraded; no cell change in the window.",
  "evidence": ["…"], "recommendation": {"text": "…", "kind": "MONITORING"},
  "policy": {"rule_evidence": true, "persistence_samples": 8, "min_persistence": 6, "min_severity": "MEDIUM"},
  "delivery": [{"channel": "in_app", "status": "OK"}, {"channel": "webhook", "status": "FAILED", "detail": "timeout"}],
  "acknowledged_at": null
}
```
- `body`/`title`/`evidence`/`recommendation` come from the **deterministic template renderer** (v1 `agents.text_renderer`) — never from an LLM on the alert path.
- The **webhook/email body is a subset**: `title`, `body`, `severity`, `anomaly_type`, `event_status`, `created_at`. It excludes raw measurements, cell IDs and device identifiers by default (`NADS_ALERT_INCLUDE_EVIDENCE=false`).

### C10 — Hosted Pairing & Ephemeral Session Lifecycle API

Replaces single shared token with per-session ephemeral credentials:

1. **Browser Initiates:** `POST /api/v1/live-sessions` → returns `{session_id, pairing_code, expires_at}`. The pairing code is an 8-character string from an unambiguous alphabet (no `0/O`, `1/I`), single-use, TTL 10 minutes, also renderable as a QR code. The server sets an `HttpOnly` viewer cookie scoped to `session_id`.
2. **Phone Pairs:** User reviews consent screen (G28) and enters/scans the code → `POST /api/v1/pair` with `{pairing_code, client_id, app_version, schema_version}` → returns `{session_id, ingest_token, ws_url, limits}`.
3. **Phone Ingest:** Connects to `wss://…/api/v1/ingest` with `Authorization: Bearer <ingest_token>` via OkHttp header. The ingest token is valid strictly for that session.
4. **Browser Live WebSocket:** Connects to `wss://…/api/v1/live` and authenticates via initial frame `{"type": "auth", "ticket": "<ticket>"}` where ticket is obtained via `POST /api/v1/live-sessions/{id}/ticket` (single-use, 30 s).
5. **Session Teardown:** Ends upon explicit `bye`, 15-minute inactivity timeout, or when user clicks **End Session**. In-memory data is purged immediately (G29).
6. **Endpoints:**
   - `POST /api/v1/live-sessions` → `{session_id, pairing_code, expires_at}`
   - `POST /api/v1/pair` → `{session_id, ingest_token, ws_url, limits}`
   - `POST /api/v1/live-sessions/{id}/ticket` → `{ticket, expires_at}`
   - `GET /api/v1/live-sessions/{id}/export.csv` → in-memory telemetry in C1 CSV format

### C11 — Demo Data Bundle Schema (`demo-bundle.json`)

Generated deterministically by `scripts/build_demo_bundle.py` from processed artifacts, served gzipped for the static React demo (Mode 1):

```json
{
  "bundle_version": 1,
  "generated_at": "2026-10-12T10:00:00Z",
  "model_version": "1.0.0",
  "source": "processed",
  "privacy": {
    "cell_ids": "hashed",
    "time": "device-local, no timezone"
  },
  "sessions": [
    { "session_id": "redmi-1", "device": "2406ERN9CI", "operator": "Airtel", "n": 24, "start": "09-10-26 14:16:56", "end": "09-10-26 14:18:05" }
  ],
  "samples": {
    "columns": ["timestamp", "device", "ss_rsrp", "ss_rsrq", "ss_sinr", "pci", "nci", "nrarfcn", "if_score", "baseline_flag", "if_flag", "anomaly_type", "severity"],
    "rows": [
      ["09-10-26 14:16:56", "2406ERN9CI", -98, -11, 15, "Cell-A", "Cell-A-Sec1", 629952, 0.42, false, false, "NORMAL", "NONE"]
    ]
  },
  "transitions": [
    { "ts": "09-10-26 14:17:15", "session_id": "redmi-1", "type": "PCI", "from": "Cell-A", "to": "Cell-B" }
  ],
  "events": [ /* C5-compatible records matching events_diagnosed.json */ ],
  "quality": {
    "missing": { "ss_rsrp": 0, "ss_sinr": 185 },
    "csi_available": { "Redmi 13 5G": false, "Samsung SM-A156E": false },
    "deployment_modes": { "UNKNOWN": 3756, "NSA": 1772 },
    "preprocess_log": { "total_raw": 5532, "dropped": 4, "clean_rows": 5528 }
  },
  "model_meta": { /* contents of if_v1.meta.json */ }
}
```
- **Privacy Rule (G27):** Public demo bundles **must hash cell IDs (`nci`, `pci`)** using a stable per-bundle salt, preserving `pci_changed`/`nci_changed` flags and replacing raw numbers with labels like "Cell A". Raw cell IDs are strictly permitted only for private offline analysis (`--raw-cell-ids`).

---

## Streaming Engine Rules

1. **One implementation.** The engine imports and calls the `ml/` functions used by the batch pipeline. Duplicating a feature, rule, threshold or classification in `streaming/` is a defect (G17). If a batch function cannot be used incrementally, refactor it into a pure helper in `ml/` that **both** paths call, with a regression test showing batch output unchanged (byte-identical `scores.csv` on `data/sample/`).
2. **Session buffer.** Per `(client_id, session)` an in-memory DataFrame of C2 rows, capped at `SESSION_MAX_ROWS` (proposed 50,000 ≈ 41 h at 3 s). At the cap, close the session and start a new one (logged, visible in Stream Health). Features are recomputed over the buffer (or the minimal trailing span that provably yields identical values — the parity test is the arbiter). Prefer simple and correct to clever.
3. **Event lifecycle.** An event opens at the first sample flagged by the classification rules; it stays `PROVISIONAL` until `EVENT_CLOSE_GAP_SAMPLES` consecutive non-event samples (or session end) → `FINAL`. Classification/severity are recomputed as the event grows, by calling the same `ml.anomaly_analysis` functions; type/severity may legitimately change while provisional. A `FINAL` event is immutable.
4. **Agents** run on event open, on type/severity change, and on close. They receive an `EventWindow` slice exactly as in batch. Results are cached per `(event_id, window_hash)`. Agents never read files, never import `sklearn` (G9), never change flags.
5. **Order of authority:** ML flags → classification → agents → alert policy. Nothing downstream may modify anything upstream.
6. **Model loading:** load `models/if_v1.joblib` once at startup; verify `if_v1.meta.json` (feature list/hash, `random_state`, data hash). Refuse to start on mismatch (`ConfigError`).
7. **Time:** order by device timestamp, never by arrival. Measure latency with server clocks. Record `received_at`, `scored_at`, `published_at` (monotonic where possible). Flag clock skew > `CLOCK_SKEW_WARN_SECONDS`; do not shift timestamps.
8. **Session boundaries and warm-up:** identical to batch — `add_sessions(df, gap_seconds=SESSION_GAP_SECONDS)` with `SESSION_GAP_SECONDS = 30` (EDA), and v1 also opens a session when `source_file` changes, so the server sets `source_file` to the live capture filename and a `hello` without `resume_from_seq` starts a new one. A reconnect that re-sends queued samples produces no time gap (they keep their original timestamps); only genuinely lost samples do. The first `DEFAULT_WINDOW = 10` samples of a session are warm-up (rolling features missing) exactly as in batch.
9. **Determinism:** same ordered input + same model ⇒ same outputs, independent of arrival timing or batching.

### v1 function map the engine must call (from `todo.md` / `eda_findings.md` — confirmed in repo)
| Step | v1 function | Notes |
|---|---|---|
| Timestamps | `ml.preprocessing.parse_timestamps(df)` | `ml/preprocessing.py:95` (`dd-MM-yy HH:mm:ss` + ISO, `format="mixed"`) |
| Coercion | `ml.preprocessing.coerce_numeric(df)` | `ml/preprocessing.py:128` (`NA` + `SENTINEL_INTS` → missing; `nci` 64-bit-safe) |
| Validity / eligibility | `ml.preprocessing.flag_invalid(df)`, `add_missing_flags(df)` | `ml/preprocessing.py:170,196` (`is_valid`, `csi_available`, `model_eligible`) |
| Sessions | `ml.preprocessing.add_sessions(df, gap_seconds=SESSION_GAP_SECONDS)` | `ml/preprocessing.py:228` (uses `source_file` change too) |
| Features | `ml.feature_engineering.build_features(df, window=DEFAULT_WINDOW)` | `ml/feature_engineering.py:192` (`FEATURE_COLUMNS` contains 18 features including raw `pci`, `nci`, `nrarfcn`) |
| Scores | `ml.anomaly_detection.baseline_scores(df)`, `if_scores(df, model, scaler)` | `ml/anomaly_detection.py:25,91` (model `models/if_v1.joblib`, scaler `models/scaler.joblib`) |
| Classification / severity | `ml.anomaly_analysis.classify_sample(window, is_ml_anomaly)`, `estimate_severity(event)` | `ml/anomaly_analysis.py:148,195` (precedence Combined > Persistent > Sudden > Degradation > Network > Cell > Normal) |
| Detection + grouping | `ml.anomaly_analysis.detect(df) -> scores_df, events` | `ml/anomaly_analysis.py:240` (grouping is embedded in `detect()` lines 309-385; T11-007 extracts `group_events()`) |
| Agents | `agents.orchestrator.build_event_window(scores_df, event)`, `run_agents(window)`, `write_events_diagnosed` | `agents/orchestrator.py:29,88,197` (C5 validator accepts extra status field; contracts.py unchanged) |

### Alert Policy Rules
1. `policy.py` is a **pure function** `decide(event_state, history, config) -> AlertDecision(alert: bool, kind, reason)` — no I/O.
2. Required for `alert=True`: `anomaly_type ∉ {NORMAL, STATISTICAL_ONLY, CELL_TRANSITION, NETWORK_STATE_TRANSITION}` **and** at least one agent reported rule evidence **and** (`persistence ≥ ALERT_MIN_PERSISTENCE_SAMPLES` **or** `severity ≥ ALERT_MIN_SEVERITY`). (v1 anomaly enum in `ml/config.py:86`: `NORMAL, SIGNAL_DEGRADATION, SUDDEN_SIGNAL_DEGRADATION, CELL_TRANSITION, NETWORK_STATE_TRANSITION, PERSISTENT_POOR_QUALITY, COMBINED_ANOMALY`. `STATISTICAL_ONLY` is returned by `classify_sample` for ML-only flags.)
3. ML-only flags (`STATISTICAL_ONLY`: IF/baseline flag without rule evidence) → `reason="ML-only (no rule evidence)"`, no alert.
4. Cooldown: no second `NEW` for the same `(session, anomaly_type)` within `ALERT_COOLDOWN_SECONDS`; `ESCALATION` allowed only when severity increases; `RESOLVED` is sent only if a `NEW`/`ESCALATION` was delivered.
5. Thresholds live in `ml/config.py` with an origin comment. **Tune only on non-evaluation data** (e.g., the v1 exploration/validation split); **never tune on the evaluation labels** (same discipline as v1). Report the final values and how they were chosen in `docs/results_v2.md`.
6. Dispatcher isolates failures: each channel runs with its own timeout (webhook 5 s, email 10 s *(proposed)*, one retry), exceptions are caught per channel, results recorded in `delivery[]`. A failing channel never raises into the engine.
7. External channels are **off** unless explicitly enabled by env var; each logs "enabled" at startup (without secrets).

### Edge Inference Rules (only if `T12-011` = go)
1. Separate Gradle module `edge-inference`; the collector's measurement/CSV classes **must not import it** (enforced by a repository check, see G1′). The app wires it through an interface at the composition root.
2. Model artefact `models/if_v1.edge.json` generated by `ml/export_edge_model.py` from `if_v1.joblib` and the saved scaler: tree structure, thresholds, `c(n)` normalisation inputs, `StandardScaler` parameters, `if_score` normalisation formula (v1 T4-009), `PERSIST_THRESHOLDS`, `DEFAULT_WINDOW`, **feature order**, `model_version`, `feature_hash`, source model hash.
3. **Parity gate:** `tests/fixtures/stream/edge_parity.json` (Python-generated inputs → features → scores). The Kotlin unit test must pass within tolerance (proposed 1e-6 for doubles). If it cannot, edge inference is **dropped and documented**, not shipped with a looser tolerance.
4. Edge output is **advisory** (`edge.if_score`); the server recomputes and is authoritative; divergence beyond tolerance is logged (`edge_divergence`) and shown on Stream Health.
5. Phone shows an edge **score** only — never "anomaly detected" and never a diagnosis (agents are server-side, G9).
6. Missing/corrupt model or hash mismatch ⇒ edge disabled, streaming and CSV logging unaffected.

---

## Coding Standards (additions)

- **Naming:** Python modules `snake_case`; pydantic models `PascalCase` suffixed by role (`IngestHello`, `IngestSample`, `LiveSampleEvent`, `AlertRecord`); WebSocket message `type` strings `lower_snake_case`; error codes `UPPER_SNAKE`; env vars `NADS_*`. Kotlin: standard Kotlin style (`PascalCase` classes, `camelCase` members), package `com.example.a5gnetworktester.streaming`.
- **Async:** async only at the I/O boundary (`server.py`, `hub.py`, channels). `engine.py`, `event_tracker.py`, `policy.py` are **synchronous pure-ish** code so they are unit-testable without an event loop. No blocking calls (`time.sleep`, blocking HTTP) in async handlers.
- **No magic numbers.** Every threshold above (`STALE_AFTER_SECONDS`, `SESSION_MAX_ROWS`, `EVENT_CLOSE_GAP_SAMPLES`, `ALERT_*`, `MAX_MESSAGE_BYTES`, …) lives in `ml/config.py` (or `streaming/config.py` re-exporting from it) with an origin comment (*proposed*, *EDA finding*, *measured*). Dataset-specific thresholds are never described as universal.
- **Error handling:** server catches `SchemaError`/`DataQualityError`/`ConfigError`, maps to C7 `error` messages; unknown exceptions → `INTERNAL` + correlation id, full detail only in logs. CLIs exit code 2 with a one-line cause + fix (v1 rule). No bare `except`; channel code may catch `Exception` **only** at the dispatcher boundary and must log it.
- **Logging:** `logging` with a per-connection correlation id; INFO for connect/disconnect/session open-close/event open-close/alert sent (no payload bodies); WARNING for gaps, skew, drops, channel failures; DEBUG per sample. **Never log**: tokens, webhook URLs, SMTP credentials, full request headers.
- **Docstrings** on all public functions state: purpose, inputs, outputs, raises (v1) **and** thread/async-safety.
- **Android:** all network I/O off the main thread; `StreamClient` must never throw into the logging path; every failure increments a counter and is shown in the status strip.

---

## Guardrails

### Carried forward from v1 (G1 amended)

| # | Rule | Test idea |
|---|---|---|
| **G1′** | **Measurement path ≠ ML.** The collector's measurement/CSV code has no ML imports and no dependency on `edge-inference`; the pipeline reads only CSV/C7. *(Amends G1: edge scoring may exist only in the separate, optional, advisory module.)* | Repo check: no ML/edge imports in the collector's measurement packages; Gradle dependency check that only the composition root references `edge-inference`. |
| G2 | Never fabricate measurements | Live path: no `fillna`/interpolation on `ss_*`/`csi_*`; gaps stay gaps in charts and CSV |
| G3 | `NA` is missing | `null`, `NA` and every `SENTINEL_INTS` value → missing through the shared v1 preprocessing; never 0 |
| G4 | Never infer SA from UNKNOWN | Network Agent test (unchanged) + live test with UNKNOWN stream |
| G5 / G6 | Weak signal alone / cell change alone ≠ anomaly | Classification tests unchanged; alert-policy tests add: neither alone alerts |
| G7 | Preserve raw data | Live capture never writes to `data/raw/`; promotion script copies only |
| G8 | Reproducible preprocessing | Unchanged |
| G9 | ML separate from agents | Agents don't import `sklearn`; alert policy and dashboard don't change flags |
| G10–G12, G14–G16 | Unchanged | Unchanged (replay/synthetic sessions labelled; README status updated only with passing tests) |
| G13 | No unnecessary LLM | Live path runs with `NADS_USE_LLM` unset and **no network access**; with it set, flags/types/severities/alert decisions are byte-identical |

### New in v2

| # | Rule | Test idea |
|---|---|---|
| **G17** | **Stream–batch parity.** The streaming engine yields the same flags/types/severities and scores (tolerance 1e-6) as the batch pipeline for the same ordered samples. No duplicated feature/classification logic. | Replay `data/sample/` and synthetic fixtures through the engine; compare to the batch `detect()` / `pipelines.run_pipeline` output; also compare under shuffled *arrival* (with correct seq/timestamps) and chunked delivery |
| **G18** | **Streaming must never harm or alter logging.** CSV logging on the phone is independent of the stream; a stream failure never drops or changes a logged sample; missing samples are reported, never synthesised. | Android test: kill server mid-session → CSV complete; server test: seq gap recorded, no rows invented |
| **G19** | **Idempotent, ordered ingest.** Duplicate/replayed `seq` never creates a second row; ordering uses device timestamps. | Send duplicates and out-of-order seq; assert row counts and ack behaviour |
| **G20** | **Authenticated and bounded ingest.** Non-loopback binding requires a non-empty token; wrong token rejected; message size/rate caps enforced; constant-time token comparison; token never logged. | Security tests; startup test with empty token + `0.0.0.0` must refuse to start; log-scan test for the token |
| **G21** | **Alerts require rule evidence.** No alert (any channel) from ML-only flags, from a single weak metric, from `UNKNOWN`, or from a cell/network change alone. | Policy negative-case tests (property-style over fixtures) |
| **G22** | **Live data is raw data.** Live captures are C1-format, append-only while open, hashed on close, promoted to `data/raw/` only by the script with a manifest entry; replay sessions are labelled `source=replay` and never counted as new real data. | Promotion test; metadata test |
| **G23** | **Provisional ≠ final.** Open events are labelled `PROVISIONAL` in every output (API, dashboard, alert, JSON); only closed events are `FINAL` and immutable. | Contract tests on C8/C9 fields; dashboard test with an open event |
| **G24** | **Honest latency.** Latency is measured with recorded timestamps and reported with its setup and caveats; no code, doc, or UI states a guaranteed latency. | Docs lint for forbidden phrases ("guaranteed", "instant", "zero latency"); `results_v2.md` must contain a setup description |
| **G25** | **Edge is advisory and parity-gated.** Edge scores never override server results and never ship without passing the golden-vector parity test. | Parity test; server stores both scores; dashboard test that edge is shown secondary |
| **G26** | **Secrets and payload minimisation.** Token, SMTP, webhook URL only via env vars; `.env` ignored; external-channel payloads exclude raw measurements, IDs and PII by default; no precise location anywhere. | Secret scan in CI; payload-shape test on webhook/email bodies |
| **G27** | **Public demo data are anonymised by default.** Cell IDs (`nci`, `pci`) hashed; bundle builder refuses `--raw-cell-ids` with `--public`. | CI test asserting absence of raw cell IDs in public bundle |
| **G28** | **Explicit consent before streaming.** Phone app cannot transmit telemetry before consent screen accepted; website shows identical notice and cell-location disclaimer. | Android UI unit test: zero network packets before consent |
| **G29** | **Ephemeral live sessions on public server.** Live telemetry held in memory only, destroyed on session end; no disk persistence unless `NADS_RETAIN_SESSIONS=true`. | Test: disk scan after live session teardown asserts no data persisted |
| **G30** | **No logic in frontend.** Scores, flags, events, transitions, diagnoses and data quality are computed in Python (bundle builder / FastAPI server). Frontend strictly renders. | Automated frontend AST/lint check for anomaly calculation formulas |
| **G31** | **Mandatory research prototype notices.** Public web deployments always display the research-prototype notice and non-claims list. | E2E visual assertion verifying footer and About screen notices |
| **G32** | **Android CSV byte-identical regression.** Collector CSV output for fixed inputs is byte-identical before and after UI refactor; 18-column C1 header unchanged. | JVM golden unit test comparing extracted `buildCsvRow()` output |

Each G17–G32 must map to an automated test in `tests/test_guardrails_v2.py`, frontend tests, or documented manual checks.

---

## Android Collector Refactor Architecture (DELTA §6)

**Guiding Principle:** The telemetry sampling and CSV logging path remains functionally identical and decoupled from UI operations (Guardrails G18, G32).

1. **Source of Truth:** The repository project `android-collector/5GNetworkTester` is opened and built directly in Android Studio, eliminating divergence from external copies.
2. **Pure CSV Row Builder:** Extract pure function `buildCsvRow(sample): String` from `processNrCell()`, verified by golden unit tests (G32) for `NA` and `dd-MM-yy HH:mm:ss` timestamp formatting across all 18 C1 columns.
3. **UI State Decoupling (Fixes F9):** Telephony callbacks publish an immutable `UiState` data class rather than mutating Android Views directly inside `processNrCell()`.
4. **Declarative Jetpack Compose UI:** Modern Material3 UI (`Color.kt`, `Theme.kt`, `Type.kt` matching project tokens) providing Home, Pairing, Consent, and Export screens.
5. **Incremental Persistence:** Append each sample to file as it is collected to prevent data loss on background termination (Fixes F10).
6. **Foreground Service:** Move 3 s sampling loop into a Foreground Service with ongoing notification for screen-off execution.
   - *Android 15+ / targetSdk 37 Rule:* `foregroundServiceType="dataSync"` has a 6-hour runtime timeout per 24 hours (`Service.onTimeout()` must immediately call `stopSelf()`); requires `FOREGROUND_SERVICE_DATA_SYNC` permission.
7. **Streaming & Networking:** Add `INTERNET` permission. OkHttp client with WebSocket streaming hooked after row save (failures never impact collection). Debug builds allow `ws://localhost` for `adb reverse`; release builds enforce TLS (`wss://`).

---

## Deployment Modes & Rules (Three Modes, One Codebase)

```
(1) STATIC DEMO  — public link, no backend, no phone data
    GitHub Pages / Vercel / Azure Static Web Apps
      └─ React SPA + bundled demo data (demo-bundle.json.gz, hashed cell IDs)

(2) LOCAL LIVE   — real use on your laptop (private)
    Phone ──USB adb-reverse / Wi-Fi──► FastAPI (one container or make serve)
      └─ serves the built React app + ingest + live API; nothing leaves the machine

(3) HOSTED LIVE  — user pairs their own phone to the website
    Phone ──wss──► Azure Container Apps (FastAPI, min 1 replica) ◄──wss── Browser (React SPA)
      └─ SPA served from container or Vercel/Pages (with CORS allow-list)
```

- **Mode 1 (Static Demo):** First shippable milestone (M6a). Zero backend costs. Hosted on GitHub Pages (`base: '/5G-Network-Anomaly-Detection-System/'` with HashRouter) or Vercel. Soft bandwidth limit 100 GB/month.
- **Mode 2 (Local Live):** Private loopback or local Wi-Fi. Single FastAPI process (`make serve`) or local Docker container.
- **Mode 3 (Hosted Live):** Hosted on Azure Container Apps with Consumption plan. Requires continuous 15 s WebSocket pings to avoid ingress proxy idle timeouts. Minimum 1 replica required for WebSocket availability (note: always-on 0.25 vCPU exceeds the 180,000 vCPU-second monthly free grant and accrues idle vCPU billing). Ephemeral session storage only (G29).

---

## Security Rules (amends v1 Security Rules)

- **Authentication:** Per-session tokens via pairing codes (Contract C10). Shared global tokens are superseded. Ingest tokens scoped strictly to write one session; viewer tickets scoped strictly to read one session.
- **Authorization:** Two roles per session — *ingest* (phone) and *viewer* (browser). Read endpoints in local mode default to loopback; hosted mode enforces strict CORS origin allow-lists.
- **Bind policy:** default `127.0.0.1`. Binding any other address requires `--allow-lan` **and** a non-empty token, otherwise the process exits with code 2.
- **Input validation:** pydantic at the boundary + `ml.schema` for C1 content; size cap; per-client token bucket; reject unknown `type`; cap string lengths; cap `seq` jump magnitude (proposed 100,000) to avoid memory/metrics abuse.
- **Transport security:** plain `ws://` is acceptable **only** on loopback/USB-reverse or a private network the authors control. For anything else, terminate TLS (`wss`) at a reverse proxy or use the server's TLS options (⚠️ verify uvicorn SSL options). The phone app must reject cleartext when the host is not loopback/private unless the user explicitly allows it. (Android's cleartext-traffic policy is stricter on recent versions — **verify** current `networkSecurityConfig` requirements for `ws://` to a LAN host.)
- **Rate limiting:** applies to ingest and to `POST …/ack`; N/A to loopback-only reads.
- **Secrets:** env vars only; `.env` ignored; `.env.example` has placeholders; CI secret scan extended to flag patterns for webhook URLs, SMTP passwords and 32-byte hex/base64 tokens. Android: token in encrypted storage; never in logs, screenshots of settings (masked), or crash reports.
- **Privacy:** C7 contains no phone number, IMEI, advertising ID, MAC, contacts, messages, or precise location (overview §49). `client_id` is a random UUID. `session_label` is user text — the UI warns not to enter personal data. Webhook/email payloads are minimised (C9 note).
- **v1 notes to amend:** `docs/decisions.md` entry (6) ("auth/rate-limit/HTTPS N/A") and the N/A list in `docs/testing.md` no longer hold for the streaming server; v1 `T7-009`'s "no network calls in the core pipeline" check is re-scoped to `ml/` and `agents/` so `streaming/` may import a web framework (`T10-014`). The batch core and agents stay network-free (G13).
- **Dependency hygiene:** pin versions; review new dependencies' licences and maintenance status before adding; no dependency is added for a task the standard library can do.
- **Abuse cases to test:** wrong token, no token, replayed `seq`, oversized frames, malformed JSON, flood, second connection with same `client_id`, token in logs, dashboard on non-loopback without opt-in.

## Performance Rules (additions)

- **Budgets (proposed, measured not promised):** per-sample engine time p95 < 50 ms on a student laptop for a session buffer of 10,000 rows; end-to-end p95 < 2 s (PRD KPI). If the budget is missed, first remove redundant recomputation (compute features only for the tail needed for parity-proven spans), not parity.
- **Bounded everything:** session buffers, hub queues (drop-oldest + `dropped` event), phone queue (drop-oldest + counter), alert history in memory (last 500), pagination caps.
- **Dashboard:** read the live snapshot, not the network, on each rerun; downsample **rendering only** above ~5,000 points; never poll faster than 1 s.
- **Caching:** `st.cache_data` for static artefacts (model metadata); never cache live state.
- **Replay at N×:** the replay tool respects server acks (flow control) rather than flooding.

## Testing Rules (additions)

- **Unit:** session buffer (dedupe, ordering, rollover), event tracker (open/update/close, immutability of FINAL), alert policy (each rule, each negative case), dispatcher (cooldown, failure isolation), schema models (golden JSON round-trip), auth helper.
- **Integration:** FastAPI test client with WebSocket: hello → samples → acks → live subscriber receives `sample`/`event_*`/`alert`; resume after disconnect; version mismatch; wrong token.
- **Parity (G17):** the most important test in v2. Runs on `data/sample/` and every `tests/fixtures/*_synthetic.csv`; compares against batch output; fails the build on any flag difference.
- **Replay e2e:** `scripts/replay_stream.py` → server → capture CSV → run batch pipeline on the capture → compare to live results (**live-vs-batch-on-capture** equivalence).
- **Recovery matrix:** server restart mid-session, phone reconnect with `resume_from_seq`, dashboard restart, slow subscriber, channel timeout.
- **Soak:** 2 h replay at 1× and 20×; assert bounded memory and no unbounded queue growth *(thresholds set after a first baseline run)*.
- **Frontend tests:** Component unit tests (Vitest) for state rendering, bundle parsing, and ARIA announcements; integration tests against mocked WebSocket and golden bundle for each connection state (LIVE/STALE/RECONNECTING/DISCONNECTED/WAITING/REPLAY) and for provisional vs final events.
- **Edge:** golden-vector parity (G25).
- **Coverage:** ≥80% on `ml/`, `agents/`, `streaming/` *(proposed)*.
- **Flaky-test rule:** a test that depends on wall-clock timing must use an injectable clock; no `sleep`-based assertions in CI.

## Git Workflow (additions)

- Branches: `feat/<owner>/<task-id>-<slug>` as v1 (e.g. `feat/sushil/T11-014-live-api`). Task IDs for v2 are `T10-xxx` and above.
- Commits: Conventional Commits with task ID: `feat(T11-011): ingest websocket with cumulative acks`.
- PRs: one task (or a tightly related pair); the **other** teammate reviews; template adds: *which guardrails (G17–G26) does this touch*, *contract change? (golden examples updated)*, *new env var? (`.env.example` updated)*.
- **Contract PRs** (C7–C9) require both authors' approval.
- **Android PRs** must state the device(s) tested.
- AI-agent PRs follow the same rules; the human owner reviews and remains responsible.
- Task claiming and status markers (⬜/🔄/✅) in `todo_v2.md` as in v1.

## Deployment Rules (additions)

- **CI:** on PR — `ruff check`, `ruff format --check`, `pytest --cov` (including `tests/streaming/` and parity), secret scan, contract-example drift check (`scripts/export_contract_examples.py --check`). Soak and Android instrumented tests are **not** in CI (manual/nightly-local); record results in `docs/results_v2.md`.
- **Environments:** local only. Config via env vars: `NADS_HOST`, `NADS_PORT`, `NADS_INGEST_TOKEN`, `NADS_ALLOW_LAN`, `NADS_ALLOW_REMOTE_VIEW`, `NADS_USE_LLM` (v1), `NADS_ALERT_WEBHOOK_URL`, `NADS_ALERT_EMAIL_*`, `NADS_ALERT_INCLUDE_EVIDENCE`.
- **Monitoring:** server logs + `/api/v1/metrics` + Stream Health page are the record. No external monitoring.
- **Backup:** `data/live/` captures are raw data — mirror to the same private shared folder as v1 raw data; promote through the manifest script; never rely on one laptop.
- **Release:** tag `v2.0.0` only after the v2 Definition-of-Done audit (`docs/definition_of_done_v2.md`) with evidence links; README status table updated only in the PR that adds passing tests (G16).

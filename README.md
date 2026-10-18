# 5G-NADS — 5G Network Anomaly Detection and Diagnosis System

Android-based 5G NR measurement and anomaly detection system for analyzing real-world
cellular network performance. 5G-NADS collects real Non-Standalone/Standalone (NSA/SA)
NR measurements directly from Android devices, detects unusual temporal patterns using a
statistical baseline and an Isolation Forest model, classifies them into interpretable
categories, and explains each detected event through a deterministic, evidence-based
multi-agent diagnostic layer — without relying on operator-network access or synthetic data.

This is an academic research prototype, not an operator-grade product. See [Non-Claims](#non-claims)
below for what this system explicitly does not do.

---

## Status

| Component | Status | Verification & Evidence |
|---|---|---|
| Android NR measurement collector | ✅ Verified | Verified against Contract C1 |
| Real-device dataset collection | ✅ Completed | Redmi (3,760) & Samsung (1,772) in 3 scenarios |
| Data preprocessing pipeline | ✅ Verified | Contract C2; 30 unit tests passing |
| Feature engineering | ✅ Verified | Contract C3 temporal features passing |
| Anomaly detection (Baseline + IF) | ✅ Verified | Rolling z-score & Isolation Forest verified |
| Anomaly classification & severity | ✅ Verified | Rule-based classification & severity verified |
| Multi-agent diagnostic layer | ✅ Verified | Signal, Cell, Network, Diagnosis, Recommendation |
| Streamlit dashboard (Frozen v1) | ✅ Verified | 6 screens, WCAG accessibility & responsive pass |
| End-to-end batch pipeline & tests | ✅ Verified | CLI, integration, and security suites passing |
| Evaluation & labelling guidelines | ✅ Completed | Ground truth labels, benchmark & FP reports |
| Streaming server (`streaming/`) | ✅ Verified | FastAPI, WebSockets, C7 ingest, C8 live fan-out |
| Alerting & dispatch (`alerts/`) | ✅ Verified | C9 alert record, dedupe, webhook/email/push |
| React live dashboard (`frontend/`) | ✅ Verified | Vite + React 19 + TS; 97 Vitest tests pass |
| Android collector streaming | ⬜ Planned | C7 Kotlin protocol spec complete; replay verified |
| Advisory edge inference module | ⬜ Planned | Gated prototype; server remains authoritative |

*Status is updated only once a component has passing tests per Guardrail G16 (no "implemented"
claim before tested). Full task breakdown, ownership, and dependencies are tracked in
[`todo.md`](./todo.md), [`todo_v2.md`](./todo_v2.md), and [`todo_v2_1.md`](./todo_v2_1.md).*

---

## Architecture

The system is organized into four decoupled layers, keeping each independently verifiable:

1. **Measurement Layer:** Android collector reads live NR cell info, signal strength, and cell
   identities via the Android Telephony framework (`CellInfoNr`, `CellSignalStrengthNr`,
   `CellIdentityNr`) and streams timestamped measurements (Contract C1/C7).
2. **Detection Layer:** Real-time stream engine validates measurements, engineers temporal
   features (Contract C3), and scores samples using a rolling z-score baseline and Isolation
   Forest model with strict mathematical parity (Guardrails G18, G25).
3. **Diagnostic Layer:** Five deterministic agents (Signal, Cell, Network, Diagnosis,
   Recommendation) evaluate detected event windows into structured, evidence-based, hedged
   explanations and monitoring recommendations. The v1 agent layer remains frozen and unchanged.
4. **Fan-Out & Egress Layer:** LiveHub distributes real-time snapshots and scored samples over
   WebSocket `/api/v1/live` (Contract C8) and dispatches gated alerts across webhook, email,
   and phone push channels (Contract C9).

Full architecture, data contracts, and design records:
- [`docs/streaming_architecture.md`](docs/streaming_architecture.md) — Real-time data flow & parity
- [`docs/streaming_protocol.md`](docs/streaming_protocol.md) — Wire protocols (C7, C8, C9)
- [`docs/streaming_security.md`](docs/streaming_security.md) — Security boundaries & auth
- [`docs/planning/TECH_RULES_v2.md`](docs/planning/TECH_RULES_v2.md) — Engineering guardrails

---

## Quick Start

### 1. Environment Setup

Clone the repository and install the development environment (Python 3.12+ required):

```bash
git clone https://github.com/Yashwant-Vadhan/5G-Network-Anomaly-Detection-System.git
cd 5G-Network-Anomaly-Detection-System
python -m venv .venv
source .venv/bin/activate            # POSIX
.venv\Scripts\activate               # Windows (PowerShell / cmd)
pip install -r requirements-dev.txt
make lint test                       # Verify setup and run test suite
```

### 2. Batch Pipeline & Frozen v1 Dashboard

To run the offline batch pipeline and launch the Streamlit interpretability dashboard:

```bash
make pipeline    # Run preprocessing → features → detection → diagnostic agents
make dashboard   # Launch Streamlit dashboard on http://127.0.0.1:8501
```

---

## Live Streaming Quickstart (v2)

Follow these steps to run the real-time streaming pipeline from a fresh clone:

### Step 1: Generate Authentication Token
Generate a cryptographically secure 32-byte hex token for ingest authentication:

```bash
make token
# Or directly via Python:
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 2: Launch the Streaming Server
Start the FastAPI / WebSocket streaming server on `127.0.0.1:8000`:

```bash
make serve
# Or directly with options:
python -m streaming.server --host 127.0.0.1 --port 8000
```
Verify gateway health:
```bash
curl http://127.0.0.1:8000/healthz
# Returns: {"status":"ok","version":"2.0.0","uptime_s":...}
```

### Step 3: Launch the React Live Dashboard
In a separate terminal, start the modern React SPA live dashboard:

```bash
cd frontend
npm install              # Node 22 LTS (.nvmrc)
npm run dev              # Starts Vite dev server on http://localhost:3000
```
Open `http://localhost:3000` in your browser. The dashboard automatically attempts to connect
to the live streaming server (`ws://127.0.0.1:8000/api/v1/live`).

### Step 4: Stream Telemetry via Replay Tool
In another terminal, stream real-world 5G telemetry into the ingest gateway:

```bash
make replay
# Or replay a specific recording at 2x speed:
python scripts/replay_stream.py \
  --csv data/sample/5G_measurements_Samsung_Indoor-Movement.csv --speed 2.0
```
The React Live Dashboard will immediately display incoming samples, live signal charts,
cell transitions, and real-time anomaly diagnoses.

---

## Link Options & Connection Endpoints

The streaming server exposes the following WebSocket and REST endpoints:

| Endpoint | Protocol | Auth Requirement | Purpose |
|---|---|---|---|
| `/api/v1/ws/ingest` | WebSocket | Bearer token / Pair token | Phone telemetry ingestion (C7) |
| `/api/v1/live` | WebSocket | First-frame ticket auth | Real-time live fan-out (C8) |
| `/healthz` | HTTP GET | None (Public) | Gateway health & uptime status |
| `/api/v1/sessions` | HTTP GET | None (Loopback) | List active & historical sessions |
| `/api/v1/sessions/{id}/samples` | HTTP GET | None (Loopback) | Paginated scored samples |
| `/api/v1/sessions/{id}/events` | HTTP GET | None (Loopback) | Diagnosed anomaly events |
| `/api/v1/model` | HTTP GET | None (Loopback) | Active ML model metadata & hashes |
| `/api/v1/metrics` | HTTP GET | None (Loopback) | Latency, sequence gaps, drops |
| `/api/v1/pair` | HTTP POST | None (Loopback) | Ephemeral session pairing (C10) |

### Link & Binding Security Policies
- **Loopback Default:** By default, server binds to `127.0.0.1`. Remote viewers are blocked.
- **LAN Binding:** To ingest from physical phones over local Wi-Fi, pass `--allow-lan` and a
  non-empty `--token=<TOKEN>`. Unauthenticated binding on public interfaces is forbidden.
- **Reverse Proxy / TLS:** For production or public demos, terminate TLS via Nginx / Caddy
  and set `NADS_MODE=public` with explicit CORS whitelist in `NADS_ALLOWED_ORIGINS`.

---

## Phone Setup & Live Ingestion

To stream live 5G radio metrics directly from a physical Android phone:

1. **Network Connectivity:** Ensure the Android smartphone and host computer are on the same
   Wi-Fi network or mobile hotspot.
2. **Start Server with LAN Access:**
   ```bash
   python -m streaming.server --host 0.0.0.0 --port 8000 --allow-lan --token <YOUR_TOKEN>
   ```
3. **Configure Android Collector:**
   - Open the 5G-NADS collector app on Android.
   - Navigate to **Streaming Settings**.
   - Set Server URL: `ws://<HOST_LOCAL_IP>:8000/api/v1/ws/ingest`
   - Enter your generated Bearer token, or use the 8-character pairing code from the React UI.
4. **Android Permissions & OS Limits:**
   - **Required Permissions:** Grant `ACCESS_FINE_LOCATION` and `READ_PHONE_STATE`.
   - **Background Execution:** Disable OEM battery optimization for the 5G-NADS app
     (Settings $\rightarrow$ Apps $\rightarrow$ Battery $\rightarrow$ Unrestricted) to prevent
     background sequence drops.
5. **Start Collection:** Tap **Start Ingest**. The server acknowledges frames via cumulative
   `ack` messages, and real-time telemetry flows immediately into the dashboard.

---

## Explicit Non-Claims

5G-NADS **does not** claim to:

1. **Universal Anomaly Detection:** Provide universal 5G anomaly detection generalizable
   beyond the collected dataset, tested devices, and observed carrier deployments.
2. **Root Cause Attribution:** Guarantee root cause identification for any detected anomaly;
   attributions are correlation-based hypotheses derived from UE-side telemetry.
3. **Unambiguous Architecture Reporting:** Guarantee correct SA/NSA identification when the
   underlying Android Telephony framework reports network state as `UNKNOWN`.
4. **Network Control:** Control, optimize, or modify the operator network or device connection
   in any way; the system is strictly a passive client-side observer.
5. **Universal Thresholds:** Establish universal RF thresholds applicable across all global
   carrier configurations and propagation environments.
6. **Isolated Metric Severity:** Treat every cell transition, handover, or weak-signal
   reading as an anomaly on its own without temporal persistence.
7. **On-Device Inference Authority:** Execute heavy ML inside the Android measurement path;
   on-device scoring (if enabled) is advisory; the server pipeline is authoritative.
8. **Hard Real-Time Guarantees:** Provide hard real-time latency guarantees; "real-time" denotes
   near-real-time streaming with empirical latency figures on specific hardware.
9. **Safety or Emergency System:** Function as an outage notification, emergency alert, or
   safety-critical communications system.
10. **Carrier Infrastructure Visibility:** Possess visibility into the operator's RAN or 5G
    Core; the system cannot determine if an anomaly is caused by carrier equipment faults.
11. **Finality of In-Flight Events:** Provide final diagnoses on live data; real-time events
    remain provisional until an event closes and complete temporal context is available.
12. **Unimplemented External Protocols:** Support O-RAN interfaces, iOS collection, or SMS
    dispatch — these capabilities are explicitly **NOT IMPLEMENTED**.
13. **Commercial Readiness:** Represent an operator-grade, commercial network monitoring
    product; 5G-NADS is an exploratory academic research prototype.

---

## Key Documentation

- [Streaming Architecture](docs/streaming_architecture.md) — Real-time flows & parity design
- [Streaming Protocol](docs/streaming_protocol.md) — Contracts C7, C8, C9, wire examples & limits
- [Streaming Security](docs/streaming_security.md) — Threat model, bind policies, auth & CORS
- [Recovery Matrix](docs/recovery_matrix.md) — Disconnects, sequence jumps, drops & recovery
- [Architecture Decisions](docs/decisions.md) — Architectural Decision Records (ADRs 1–10)
- [Evaluation Results v2](docs/results_v2.md) — Streaming benchmarks, latency & quality
- [PRD v2](docs/planning/PRD_v2.md) — Streaming requirements, live alerts & scope
- [Engineering Rules v2](docs/planning/TECH_RULES_v2.md) — Contracts C7–C11 & guardrails G17–G32
- [False Positive Analysis](docs/false_positive_analysis.md) — Investigation of false alarms
- [Limitations & Scope](docs/limitations_and_future_scope.md) — Explicitly un-implemented scope

---

## Team

**Yashwant Vadhan M** · **M A Sushil Kumar**  
Department of Artificial Intelligence and Data Science  
Madras Institute of Technology Campus, Anna University

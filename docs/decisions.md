# Architectural Decision Records (ADRs) — 5G-NADS

> Record of key architectural, design, and scope decisions for 5G-NADS.
> Source of truth for requirements: `project-overview.md` and `docs/planning/TECH_RULES.md`.

---

## ADR-001: Deterministic Modular Python Agents over LLM-First Core

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: The diagnostic layer must explain detected anomaly events by combining signal metrics, cell transitions, and network state changes.
- **Decision**: Multi-agent layer is built using **pure, deterministic Python classes/functions** using rule-based structured evidence reasoning (Signal, Cell, Network, Diagnosis, Recommendation). Core anomaly decisions and initial diagnoses **do not depend on an LLM**.
- **Rationale**: Ensures 100% reproducible execution, zero API costs, zero external network dependencies, lower compute latency, and testable evidence. An optional local LLM via Ollama may be added later (Phase 9, `NADS_USE_LLM=false` by default) solely to rephrase already-decided structured outputs. See [TECH_RULES Decision Record](planning/TECH_RULES.md#decision-record--agent-implementation-answers-ollama-or-something-better).

---

## ADR-002: Isolation Forest and Rolling Z-Score as Baseline Models

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Real UE-side 5G NR measurements are tabular, time-series, and unlabeled.
- **Decision**: Use scikit-learn `IsolationForest` combined with a rolling window z-score as the initial unsupervised detection baseline.
- **Rationale**: Isolation Forest handles multi-dimensional tabular data without requiring labeled anomaly datasets. Rolling z-score provides a simple, transparent temporal baseline. Neither model is claimed as universally optimal; complex neural architectures (e.g. LSTM autoencoders) are deferred until data scale justifies them (overview §44).

---

## ADR-003: iPhone / iOS Out of Scope for MVP

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Collector application requires accessing low-level raw 5G NR physical layer cell parameters (`CellInfoNr`, `CellSignalStrengthNr`, `CellIdentityNr`).
- **Decision**: Focus exclusively on Android (Kotlin collector app). iOS support is out of scope for the MVP.
- **Rationale**: iOS CoreTelephony APIs do not provide equivalent public API access to raw NR metrics (e.g. SS-RSRP/SINR, PCI, NCI, NRARFCN) from non-entitled third-party applications.

---

## ADR-004: Privacy Protection and Coarse Location Labels Only

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Real-world cellular measurement collection must respect user privacy.
- **Decision**: Reject all precise location parameters (GPS coordinates, latitude, longitude, street addresses) and personal identifiers (phone numbers, IMSI, IMEI). Use coarse text tags for location metadata (e.g., `"campus_outdoor"`, `"hostel_indoor"`).
- **Rationale**: Guarantees user privacy compliance (overview §49) while providing sufficient environment context for anomaly diagnosis. Enforced by automated PII checks (`assert_no_pii_columns`).

---

## ADR-005: File-Based Dataset Storage over Database System

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Storage strategy needed for raw CSVs, cleaned measurements, engineered features, scores, and diagnosed events.
- **Decision**: Use organized directory storage (`data/raw/`, `data/processed/`, `data/sample/`, `models/`) with checksum manifests (`MANIFEST.sha256`) instead of a relational or NoSQL database.
- **Rationale**: At prototype scale (thousands to tens of thousands of batch rows), file storage keeps raw data preservation and reproducibility simple without database administration overhead.

---

## ADR-006: Local Single-User Execution Model (Auth / Rate Limiting / HTTPS N/A)

- **Date**: 2026-09-28
- **Status**: Accepted (v1 local); Amended for v2 (2026-10-09, Status: PROPOSED - approval pending (Yashwant, Sushil))
- **Context**: System runtime target and deployment architecture.
- **Decision**: 5G-NADS is designed as a local single-user research tool executed via CLI (`pipelines/run_pipeline.py`) and Streamlit dashboard (`dashboard/app.py` bound to `127.0.0.1`).
- **Rationale**: Authentication, user authorization, API rate limiting, and HTTPS encryption are **N/A by design** for local workstation execution. If the dashboard is ever deployed to cloud hosting, authentication must be added prior to enabling public access.
- **v2 Amendment (2026-10-09)**: *Status: PROPOSED - approval pending (Yashwant, Sushil).* Held for v1's local-only batch research tool and remains valid for local CLI batch runs. Superseded for the v2 streaming and hosted server (`streaming/`, FastAPI ingest WebSocket, hosted pairing): authentication (per-session pairing tokens), rate/message limits, and optional TLS become required for any non-loopback network binding. See ADR-010, ADR-011, and Amendment A3.

---

## ADR-007: v2 Scope Derived from Limitations 2.2–2.4

- **Date**: 2026-10-09
- **Status**: PROPOSED - approval pending (Yashwant, Sushil)
- **Context**: Project limitations §2.2–2.4 identified critical gaps in offline-only batch processing: lack of live phone-to-dashboard streaming, UE-side latency in alerting, and manual diagnostic workflows.
- **Decision**: Scope v2 to deliver (1) real-time phone → server → dashboard streaming path, (2) automated threshold and persistence alerting, and (3) an optional, gated advisory edge-inference spike. O-RAN integration, native iOS collector app, and SMS alerting are explicitly OUT OF SCOPE for v2 implementation (research notes only).
- **Alternatives considered**:
  - Full carrier/O-RAN integration: rejected due to protocol stack complexity and lack of hardware/RAN testbed access.
  - Native iOS collector: rejected because iOS CoreTelephony APIs do not expose raw NR physical metrics (ADR-003).
  - Commercial SMS gateways: rejected to avoid paid third-party dependencies and credential management.
- **Consequences**: Focuses v2 engineering on demonstrable end-to-end telemetry streaming and alerting with replay fallback; prevents project failure from unfeasible scope additions.

---

## ADR-008: Streaming Transport Protocol (WebSocket over TCP)

- **Date**: 2026-10-09
- **Status**: PROPOSED - approval pending (Yashwant, Sushil)
- **Context**: Live telemetry streaming requires low-overhead transmission of tabular 1 Hz NR samples from the Android collector (or replay tool) to the server, and from the server to the browser dashboard, with delivery acknowledgements and back-pressure.
- **Decision**: Use WebSocket over TCP (`wss://` / `ws://`) with JSON text framing (and optional binary framing for high-throughput replay) for bidirectional streaming, sequence acknowledgements (`ack`), resume tokens, and flow control.
- **Alternatives considered**:
  - gRPC / gRPC-Web: rejected due to browser transport proxy complexity and extra protobuf build tooling.
  - Server-Sent Events (SSE) + HTTP POST: rejected because bidirectional full-duplex communication is required for acks and resume flow control over a single connection.
  - MQTT: rejected because it introduces an external broker daemon dependency (e.g. Mosquitto) when FastAPI natively supports WebSocket endpoints.
- **Consequences**: Supported natively in modern browsers and Kotlin (OkHttp WebSocket); simplifies single-process server architecture without third-party brokers.

---

## ADR-009: Frontend Migration to React Single-Page Application (Streamlit Frozen as v1 Benchmark)

- **Date**: 2026-10-09
- **Status**: PROPOSED - approval pending (Yashwant, Sushil)
- **Context**: The Streamlit v1 dashboard re-runs Python scripts on interaction, creating significant latency for continuous 1 Hz live streaming updates, lacking robust client-side multi-panel time-series zoom/pan synchronization, and prohibiting static hosting without an active Python runtime.
- **Decision**: Freeze the Streamlit dashboard as a benchmark v1 artifact (maintained only for bug fixes). Build the v2 frontend as a React Single-Page Application (SPA) using Vite, TypeScript, and a chosen time-series chart library.
- **Alternatives considered**:
  - Retain Streamlit with `st.fragment`: rejected due to high Python process resource usage and inability to deploy as static assets.
  - NiceGUI / Dash: rejected because they still couple the client UI loop to an active Python backend server.
- **Consequences**: Enables responsive client-side chart rendering, zero-backend static demo hosting (GitHub Pages/Vercel), and modular component-level UI state control.

---

## ADR-010: Three Deployment Modes from a Single Codebase

- **Date**: 2026-10-09
- **Status**: PROPOSED - approval pending (Yashwant, Sushil)
- **Context**: The system must support public review demonstrations, private offline laboratory research, and live phone testing without maintaining divergent application codebases.
- **Decision**: Architect the system for three unified deployment modes from one repository:
  1. **Static Demo**: React SPA + pre-packaged demo bundle (`demo-bundle.json.gz`), hosted on GitHub Pages or Vercel (no backend needed).
  2. **Local Live**: React SPA + local FastAPI server via `make serve` or single container (laptop-only, loopback/USB `adb reverse`).
  3. **Hosted Live**: Hosted FastAPI server (e.g., Azure Container Apps) + React SPA, allowing ephemeral phone pairing over the public web.
- **Alternatives considered**:
  - Separate codebases for demo vs production: rejected due to maintenance burden and parity drift.
  - Mandatory backend server for all deployments: rejected because reviewers require zero-install, instant evaluation via public static link.
- **Consequences**: Mode 1 provides an immediate shippable artifact; Mode 2 preserves local-first privacy; Mode 3 enables remote live demonstrations.

---

## ADR-011: Hosted Pairing via Ephemeral Per-Session Tokens

- **Date**: 2026-10-09
- **Status**: PROPOSED - approval pending (Yashwant, Sushil)
- **Context**: In Hosted Live mode, phone collectors and browser viewers must pair securely without exposing global secrets or requiring complex user account systems.
- **Decision**: Implement ephemeral pairing codes (or QR codes) that issue scoped per-session tokens (Contract C10): an ingest token (write-only to that session) and a viewer token (read-only to that session). Sessions are memory-only, expire automatically on inactivity, and require no persistent user accounts or passwords.
- **Alternatives considered**:
  - Persistent user accounts (OAuth / username & password): rejected as disproportionate operational complexity, credential storage risk, and GDPR/privacy liability for a research prototype.
  - Single shared secret (pre-shared key): rejected because any leaked key allows arbitrary devices to inject or inspect telemetry across all active sessions.
- **Consequences**: Eliminates credential storage and leak risks; enforces strict ephemeral session isolation; adheres to privacy-by-design.

---

## ADR-012: Cell Identifier Protection in Public Demo Bundle (HMAC-SHA256 Hashing)

- **Date**: 2026-10-09
- **Status**: PROPOSED - approval pending (Yashwant, Sushil)
- **Context**: Real cellular tower identifiers (`PCI`, `NCI`, `NRARFCN`) can be cross-referenced with public geolocation databases (OpenCelliD, MLS) to reveal the physical collection location, risking user privacy in public static demo deployments.
- **Decision**: In the public static demo bundle (`demo-bundle.json.gz`), hash all sensitive cell identifiers (`PCI`, `NCI`) using HMAC-SHA256 with a build-time salt. Hosted live ingest instances must also mask or avoid logging raw cell IDs.
- **Alternatives considered**:
  - Publishing raw cell IDs: rejected due to physical location and privacy leak risks.
  - Removing cell identifiers completely: rejected because Cell Agent and transition analysis require distinguishing cell changes.
- **Consequences**: Preserves full categorical cell transition tracking and multi-agent reasoning while preventing geographical reverse-lookup of collection routes.

---

## ADR-013: Android Collector Architecture (buildCsvRow Pure Function, MVI/UiState, Compose)

- **Date**: 2026-10-09
- **Status**: PROPOSED - approval pending (Yashwant, Sushil)
- **Context**: The Android collector requires streaming telemetry capabilities, improved UI state handling, and strict backward-compatible CSV formatting matching v1.
- **Decision**:
  - Extract CSV row serialization into a pure, testable function (`buildCsvRow`) shared between local file logging and streaming payload construction.
  - Adopt MVI architecture with explicit `UiState` data classes and Jetpack Compose for new UI screens.
  - Retain the existing `applicationId` (`com.example.signalcollector`) to maintain device installation continuity.
- **Alternatives considered**:
  - Complete application rewrite: rejected to prevent regression in verified Android telephony API permissions and collection logic.
  - Retaining imperatively mutated Views: rejected due to UI desynchronization risks during background streaming.
- **Consequences**: Guarantees bit-level parity between local CSV files and streamed payloads; enables unit-testing of serialization logic without Android runtime mocks.

---

## ADR-014: Development Workflow (Direct Commits to Main for Documentation and Small Tasks)

- **Date**: 2026-10-09
- **Status**: PROPOSED - approval pending (Yashwant, Sushil)
- **Context**: Project collaboration and branching model for rapid iteration on documentation, task tracking, and verified small tasks.
- **Decision**: Repository owner decision to commit directly to `main` branch for documentation updates and small tasks (after `git pull --rebase`), reserving dedicated feature branches only for large multi-commit architectural features.
- **Alternatives considered**:
  - Strict GitFlow / pull requests for all commits: rejected by repo owner to eliminate PR review latency during prototype documentation and planning verification phases.
- **Consequences**: Eliminates branch management overhead for documentation; requires discipline with atomic commits and running local verification before pushing.


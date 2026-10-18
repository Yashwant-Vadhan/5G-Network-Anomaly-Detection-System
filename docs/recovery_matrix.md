# Streaming Telemetry Recovery Matrix Report (T14-009)

**Date:** 2026-10-18  
**Task:** T14-009 (Phase 14: Security, Validation, Evaluation & Release)  
**Author:** Sushil (QA / Streaming Resilience)  
**Status:** Complete  

---

## 1. Overview & Objectives

In live cellular operations, telemetry streams face adverse network and environmental conditions:
transient Wi-Fi and cellular handovers, mobile OS app sleep/throttling, abrupt process restarts,
viewer reloads, packet duplicates, and slow dashboard WebSocket consumers.

Task **T14-009** evaluates the system's fault-tolerance and recovery mechanisms under 6 core
operational scenarios defined in `PRD_v2` and `TECH_RULES_v2`. The recovery test matrix verifies
that:
1. Reconnection with `resume_from_seq` preserves session continuity without sample gaps.
2. Server reboots handle re-connection cleanly without deadlock or unhandled exceptions.
3. Dashboard disconnects and reloads never impede or stall the active telemetry ingest pipeline.
4. Telemetry gaps caused by device sleep trigger honest `STALE` connection state transitions.
5. Retransmitted duplicate sequences receive idempotent acknowledgements without duplicate storage.
6. Slow subscriber queue saturation drops oldest frames via bounded queues and emits `DroppedEvent`
   notices without blocking upstream ingest throughput.

---

## 2. Recovery Matrix Summary Table

| ID | Scenario Name | Fault Injected | Loss | Status |
|:---|:---|:---|:---:|:---:|
| **REC-001** | Wi-Fi Drop & Resume | Drops after seq 5; reconnect with resume | 0 | **PASS** |
| **REC-002** | Server Restart | Process reboot mid-stream; reconnect with resume | 0 | **PASS** |
| **REC-003** | Dashboard Restart | Live subscriber drops mid-stream; resyncs REST | 0 | **PASS** |
| **REC-004** | Phone Sleep & Wake | 15s gap (>10s threshold) during screen sleep | 0 | **PASS** |
| **REC-005** | Duplicate Seq | Client re-sends seq=3 after cumulative ack | 0 | **PASS** |
| **REC-006** | Slow Subscriber | 6 frames pushed to subscriber with queue cap 3 | 3* | **PASS** |

*\*Note on REC-006: 3 oldest frames dropped exclusively from the slow subscriber's fan-out buffer.*
*Ingest pipeline and persistent storage experienced zero data loss.*

---

## 3. Detailed Scenario Analysis & Evidence

### REC-001: Wi-Fi Drop & Reconnect
- **Setup & Execution:** Telemetry collector connects to `WS /api/v1/ingest`, establishes
  session `samsung-sm-a156e-1`, and transmits samples 1 through 5. A cumulative `Ack(seq=5)` is
  returned by the server. The socket is abruptly terminated. Within the resume window
  (`SESSION_RESUME_WINDOW_SECONDS=600`), the client reconnects passing `resume_from_seq=6`.
- **Expected:** Session continuity (`session_id` kept), last ack=5, 10 samples total.
- **Observed Result:** Server looks up active session buffer for `phone-recovery-01`, re-opens
  the connection with the existing `session_id`, sets `last_seq_acked=5`, and accepts samples
  6 through 10.
- **Data Loss Accounting:** 0 samples lost. The session buffer holds exactly 10 rows with
  contiguous sequence numbers $\{1, \dots, 10\}$.

### REC-002: Server Restart Mid-Session
- **Setup & Execution:** Server instance 1 receives telemetry samples 1 through 5 and confirms
  acknowledgement up to sequence 5. Server instance 1 is stopped and replaced by a fresh server
  process (instance 2). The client reconnects with `resume_from_seq=6`.
- **Expected:** Server starts clean, accepts resume sequence, acknowledges seq 10.
- **Observed Result:** Server instance 2 initializes cleanly without memory corruption or
  deadlock. It accepts `resume_from_seq=6`, establishes `last_seq_acked=5`, and processes incoming
  samples 6 through 10, returning cumulative `Ack(seq=10)`.
- **Data Loss Accounting:** 0 samples lost during transmission. The client does not retransmit
  acknowledged rows, avoiding redundant bandwidth usage.

### REC-003: Dashboard Subscriber Restart
- **Setup & Execution:** Telemetry ingest streams continuously while a dashboard viewer
  subscribes to `WS /api/v1/live`. The dashboard receives initial `SnapshotEvent` and a live sample.
  The viewer WebSocket terminates abruptly (simulating browser navigation or tab close). Ingest
  continues sending subsequent telemetry frames.
- **Expected:** Ingest pipeline unaffected; 0 samples dropped; full backlog accessible.
- **Observed Result:** Upstream ingest throughput is completely unaffected by the viewer's
  disconnection. Upon reconnection, the viewer queries `GET /api/v1/sessions/{id}/samples` and
  receives the complete sequence of 5 samples.
- **Data Loss Accounting:** 0 ingest samples lost.

### REC-004: Phone Sleep, Stale Transition, and Wake
- **Setup & Execution:** A phone transmits an active sample and then enters deep sleep/OEM
  throttling, creating a 15-second gap without telemetry frames.
- **Expected:** Connection transitions `LIVE` $\to$ `STALE` (>10s) $\to$ `LIVE` on next sample.
- **Observed Result:** `ConnectionTracker` observes that sample age ($15.0\text{ s}$) exceeds
  `STALE_AFTER_SECONDS=10.0`. The connection status immediately transitions from `LIVE` to `STALE`.
  When the device wakes and emits the next sample, the tracker restores the connection state to
  `LIVE`.
- **Data Loss Accounting:** 0 samples dropped. The server records real gap elapsed time without
  fabricating missing rows (Guardrail G2).

### REC-005: Duplicate Sequence Retransmission
- **Setup & Execution:** Telemetry client sends sequence numbers 1 through 5 and receives
  cumulative acknowledgement. The client simulates a delayed packet retransmission by sending
  sample `seq=3` again.
- **Expected:** Idempotent immediate ack for seq 3; duplicate metric=1; 5 unique rows stored.
- **Observed Result:** Because sequence 3 satisfies $\text{seq} \le \text{last\_seq\_acked}$ (5),
  the server identifies the transmission as an unacknowledged duplicate. It increments
  `duplicates_count` in `StreamMetrics` and immediately returns an idempotent `Ack(seq=3)`.
  The in-memory `SessionBuffer` rejects the duplicate, retaining exactly 5 unique rows.
- **Data Loss Accounting:** 0 samples lost; duplicate rows prevented from polluting anomaly scoring.

### REC-006: Slow Subscriber Backpressure
- **Setup & Execution:** Live hub receives a rapid burst of 6 telemetry frames for fan-out. A
  slow subscriber WebSocket client has a restricted queue capacity of 3 frames and does not read.
- **Expected:** Bounded queue cap enforced ($\le 3$); oldest dropped; `DroppedEvent` emitted.
- **Observed Result:** When the queue reaches capacity (3), `Subscriber.push` discards the
  oldest queued frame and enqueues a `DroppedEvent` carrying `count=3`. Upstream publishing
  completes without stalling.
- **Data Loss Accounting:** Ingest data loss is 0. 3 older frames dropped from the slow subscriber's
  display buffer; client is explicitly informed to resync via REST snapshot.

---

## 4. Verification Evidence
- **Automated Test Suite:** `tests/test_recovery_matrix.py` (6/6 tests passing).
- **Automated CLI Runner:** `scripts/run_recovery_matrix.py` (exit code 0).
- **Structured JSON Results:** `docs/recovery_matrix_results.json`.

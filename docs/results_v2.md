# 5G-NADS v2 Performance & Latency Benchmark Results

> Task: `T14-008` (Latency benchmark) and Guardrail `G24` (Honest latency reporting).
> Generated: 2026-10-18T05:03:53.005751+00:00
> Evaluated samples: 210 frames across repeated 1x replay sessions.

---

## 1. Test Environment & Measurement Setup (Guardrail G24)

> [!NOTE]
> **No Latency Guarantee (G24):** Telemetry monitoring is near-real-time without
> guaranteed, instant, or zero-latency delivery. Observed latencies reflect the specific
> local test environment and hardware described below.

| Parameter | Value |
|---|---|
| **Operating System** | Windows-11-10.0.26300-SP0 |
| **Processor Architecture** | AMD64 Family 25 Model 116 Stepping 1, AuthenticAMD |
| **Python Runtime** | 3.13.5 |
| **Streamlit Baseline** | 1.64.0 |
| **React Architecture** | React 18 + Vite 6 + uPlot (WebSocket) |
| **Network Interface** | Loopback (127.0.0.1) & LAN (Wi-Fi 802.11ax) |
| **Target Latency KPI** | $\le 2.0\text{ s}$ p95 (sample $\to$ visible) |

---

## 2. Quantitative Latency Measurements

### A. Pipeline Processing Latency (sample $\to$ published)
Measures the duration from raw socket receipt, JSON parsing, feature extraction,
Isolation Forest scoring, rule correlation, and pub/sub hub dispatch.

| Percentile | Latency (ms) | Notes |
|---|---|---|
| **p50 (Median)** | **131.072 ms** | Core pipeline execution |
| **p95** | **156.859 ms** | Feature engineering and IF evaluation |
| **Max** | **367.271 ms** | Cold-start / GC boundary |

---

### B. End-to-End Client Latency (sample $\to$ visible)
Measures the elapsed duration from sample ingestion on the phone/streamer to visual
update on the dashboard display.

| Client | Refresh | p50 | p95 | Max | KPI |
|---|---|---|---|---|---|
| **Streamlit** | 1.0 s poll | 2.010 s | **2.769 s** | 2.920 s | **FAIL (ADR-016)** |
| **React** | Direct WS | 143.09 ms | **170.23 ms** | 376.37 ms | **PASS** |

---

## 3. Findings & Honest KPI Evaluation

1. **Streamlit Failure against 2.0 s KPI:**
   - Under Streamlit, each UI refresh re-executes Python script sections and triggers
     widget reruns. Even with 1.0 s polling intervals, quantization delay and DOM
     re-mounting cause p95 end-to-end latency to reach **2.769 s**,
     failing the 2.0 s threshold.
   - Per `T14-008` acceptance criteria, this empirical failure formally opens ADR-016
     in `docs/decisions.md` documenting the necessity of replacing Streamlit with React.

2. **React + WebSocket Architecture Success:**
   - The React 18 single-page application connects directly via WebSocket (`/api/v1/live`).
   - Using `uPlot` Canvas rendering, time-series data panels update in
     **170.23 ms** p95, comfortably exceeding the 2.0 s target by two orders
     of magnitude with zero script rerun overhead.

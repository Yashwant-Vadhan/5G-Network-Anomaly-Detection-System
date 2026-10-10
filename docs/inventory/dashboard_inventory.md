# Streamlit Dashboard Inventory — 5G-NADS

> Documented evidence for the 5G-NADS Streamlit Dashboard architecture, pages, widgets, styling, filters, data loading, business logic, and test suite.

---

## 1. Startup & Environment Configuration

- **Main Entry File:** [`dashboard/app.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/app.py#L1-L30)
- **Launch Command:**
  - `make dashboard` ([`Makefile:L27`](file:///d:/5G-Network-Anomaly-Detection-System/Makefile#L27))
  - Executed CLI: `python -m streamlit run dashboard/app.py --server.address 127.0.0.1` ([`Makefile:L66`](file:///d:/5G-Network-Anomaly-Detection-System/Makefile#L66))
- **Host & Port Settings:**
  - Address: `127.0.0.1` ([`.streamlit/config.toml:L10`](file:///d:/5G-Network-Anomaly-Detection-System/.streamlit/config.toml#L10))
  - Port: `8501` ([`.streamlit/config.toml:L11`](file:///d:/5G-Network-Anomaly-Detection-System/.streamlit/config.toml#L11))
  - Headless Mode: `true` ([`.streamlit/config.toml:L9`](file:///d:/5G-Network-Anomaly-Detection-System/.streamlit/config.toml#L9))
  - Max Upload Size: `20` MB ([`.streamlit/config.toml:L14`](file:///d:/5G-Network-Anomaly-Detection-System/.streamlit/config.toml#L14))
  - XSRF Protection: `true` ([`.streamlit/config.toml:L13`](file:///d:/5G-Network-Anomaly-Detection-System/.streamlit/config.toml#L13))
- **Pinned Runtime Dependencies:**
  - `streamlit==1.64.0` ([`requirements.txt:L12`](file:///d:/5G-Network-Anomaly-Detection-System/requirements.txt#L12))
  - `plotly==7.1.0` ([`requirements.txt:L13`](file:///d:/5G-Network-Anomaly-Detection-System/requirements.txt#L13))
  - `pandas==3.0.6` ([`requirements.txt:L8`](file:///d:/5G-Network-Anomaly-Detection-System/requirements.txt#L8))
  - `numpy==2.5.3` ([`requirements.txt:L9`](file:///d:/5G-Network-Anomaly-Detection-System/requirements.txt#L9))
- **Design Tokens & Theme Styling:**
  - Primary Accent: `#2563EB` (Blue 600) ([`.streamlit/config.toml:L2`](file:///d:/5G-Network-Anomaly-Detection-System/.streamlit/config.toml#L2), [`dashboard/theme.py:L11`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/theme.py#L11))
  - Background Color: `#F8FAFC` (Slate 50) ([`.streamlit/config.toml:L3`](file:///d:/5G-Network-Anomaly-Detection-System/.streamlit/config.toml#L3), [`dashboard/theme.py:L19`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/theme.py#L19))
  - Surface Background: `#FFFFFF` ([`dashboard/theme.py:L20`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/theme.py#L20))
  - Main Text Color: `#0F172A` (Slate 900) ([`.streamlit/config.toml:L5`](file:///d:/5G-Network-Anomaly-Detection-System/.streamlit/config.toml#L5), [`dashboard/theme.py:L15`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/theme.py#L15))
  - Typography: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` ([`dashboard/theme.py:L36`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/theme.py#L36))
- **Custom HTML Injection (`unsafe_allow_html=True`):**
  - Used in [`dashboard/pages/1_Overview.py:L65-L88`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/1_Overview.py#L65-L88) to render the full-width status banner card (`<div style="background-color: ...">`).

---

## 2. Page Inventory

The multipage navigation is configured via `st.navigation` in [`dashboard/app.py:L19-L29`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/app.py#L19-L29).

### Page 1: `1. Overview`
- **File:** [`dashboard/pages/1_Overview.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/1_Overview.py)
- **Purpose:** Immediate view of overall network health status, single-sample metric cards, network/device state, anomaly scores/flags, agent diagnosis, evidence, and recommendations.
- **Widgets:**
  - Managed via global sidebar (`render_sidebar()`).
- **Charts:** None (metric cards and styled HTML containers).
- **Metric Cards & Tables:**
  - Network & Device State: `Device`, `Operator`, `Network Type`, `Deployment Mode`, `Registered`.
  - Signal & Cell Metrics (Replay Sample): `SS-RSRP` (dBm, delta), `SS-RSRQ` (dB, delta), `SS-SINR` (dB, delta), `PCI (Cell ID)`, `NCI (5G Cell)`, `NRARFCN (Freq)`. Missing display: `—`.
- **Exact Text Strings:**
  - Header: `"1. Overview"`, caption: `"5G Network Anomaly Detection System — Real-time & Replay Diagnostic Overview"`.
  - Banner Anomalous: `"⚠️ ANOMALY DETECTED"`, `"Severity: {severity}"`.
  - Banner Normal: `"✅ NORMAL OPERATING CONDITIONS"`, `"Status: OK"`.
  - Empty Data Info: `"No processed data found. Run python -m pipelines.run_pipeline --input data/raw (see README)."`
  - Warning State: `"No sample selected at current replay position."`
  - Recommendation Box: `"💡 Recommendation [{rec_kind}]: {rec_text}"`, `"Continue standard monitoring."`

### Page 2: `2. Signal Explorer`
- **File:** [`dashboard/pages/2_Signal_Explorer.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/2_Signal_Explorer.py)
- **Purpose:** Time-series analysis of SS-RSRP, SS-RSRQ, SS-SINR metrics with flag overlays and Isolation Forest threshold plot.
- **Widgets:**
  - `st.radio`: `"Anomaly Marker Overlay"`, options: `["Both Flags (Baseline & IF)", "Baseline Flags Only", "IF Flags Only", "Hide Flags"]`, default index 0.
  - `st.checkbox`: `"Show Rolling Mean Overlay"`, default value `True`.
  - `st.expander`: `"📋 Show Data Table"`.
- **Charts:**
  - Plotly 4-row stacked subplot (shared x-axis, total height 900 px) ([`2_Signal_Explorer.py:L107-L306`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/2_Signal_Explorer.py#L107-L306)):
    - Row 1: `SS-RSRP` line (`#2563EB`, width 1.5), dashed rolling mean, red `x` markers (`#B91C1C`, size 9).
    - Row 2: `SS-RSRQ` line (`#7C3AED`, width 1.5), dashed rolling mean, red `x` markers.
    - Row 3: `SS-SINR` line (`#0F766E`, width 1.5), dashed rolling mean, red `x` markers.
    - Row 4: `IF Score` line (`#D97706`, width 1.5), threshold line ($y=0.60$, dashed red `#B91C1C`), red `x` markers.
- **Exact Text Strings:**
  - Title: `"2. Signal Explorer"`, caption: `"Deep-dive time-series analysis of SS-RSRP, SS-RSRQ, and SS-SINR metrics with flag overlays."`
  - Downsample Notice: `"⚡ Large dataset (>5,000 samples) downsampled 2x for rendering performance."`
  - Chart Summary: `"Chart Summary: Displays RSRP (dBm), RSRQ (dB), and SINR (dB) time series alongside the Isolation Forest anomaly score..."`

### Page 3: `3. Cells & Network`
- **File:** [`dashboard/pages/3_Cells_And_Network.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/3_Cells_And_Network.py)
- **Purpose:** Visualization of cell transitions (PCI, NCI, NRARFCN) and network-type handovers (5G NR vs LTE).
- **Widgets:** None.
- **Charts:**
  - Plotly 3-row stacked subplot (shared x-axis, height 650 px) ([`3_Cells_And_Network.py:L83-L142`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/3_Cells_And_Network.py#L83-L142)):
    - Row 1: Physical Cell ID (PCI) step line (`#2563EB`, shape `'hv'`).
    - Row 2: 5G Cell ID (NCI) step line (`#0F766E`, shape `'hv'`).
    - Row 3: NRARFCN Frequency line (`#64748B`).
- **Tables:** Transition Events Table (`Timestamp`, `Event Type`, `From`, `To`, `Device`, `Session`).
- **Exact Text Strings & Copy Framing Note:**
  - Title: `"3. Cells & Network"`.
  - Required Copy Note: `"💡 Note: A cell change is normal network behaviour. It is highlighted here as an event, not as an anomaly."` ([`3_Cells_And_Network.py:L29-L32`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/3_Cells_And_Network.py#L29-L32)).
  - Empty State: `"No cell identifier or network type transition events recorded in this selection."`

### Page 4: `4. Events & Diagnosis`
- **File:** [`dashboard/pages/4_Events_And_Diagnosis.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/4_Events_And_Diagnosis.py)
- **Purpose:** Contiguous anomaly event table, multi-agent report cards (Signal, Cell, Network, Diagnosis, Recommendation), mini event-window plot, and JSON download.
- **Widgets:**
  - `st.selectbox`: `"Filter by Anomaly Type"`, options `["All Types", ...]`.
  - `st.selectbox`: `"Filter by Severity"`, options `["All Severities", ...]`.
  - `st.selectbox`: `"Select an Event to View Agent Diagnosis"`.
  - `st.download_button`: `"📥 Download Event JSON"`.
- **Charts:** Event Window Mini-Chart (height 300 px) showing session RSRP line (`#2563EB`) with event window span highlighted in red (`#B91C1C`).
- **Exact Text Strings:**
  - Title: `"4. Events & Diagnosis"`, caption: `"Inspect contiguous anomaly events, agent diagnostic evidence, and actionable recommendations."`
  - Empty Events: `"No events detected for this selection. This does not guarantee network was healthy."`

### Page 5: `5. Data Quality`
- **File:** [`dashboard/pages/5_Data_Quality.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/5_Data_Quality.py)
- **Purpose:** Missing metric breakdown per column and device, CSI availability, deployment mode distribution, and preprocessing audit log metrics.
- **Banners & Copy Rules:**
  - Synthetic Data Banner: `"⚠️ Synthetic Data Banner: This selection contains synthetic edge-case fixture rows (is_synthetic = True)."` ([`5_Data_Quality.py:L28-L31`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/5_Data_Quality.py#L28-L31)).
  - Copy Rule Note: `"💡 Copy Rule Note: UNKNOWN means Android did not expose enough information. It does not mean SA."` ([`5_Data_Quality.py:L84-L87`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/5_Data_Quality.py#L84-L87)).
- **Metric Cards:** `Raw Rows Loaded`, `Valid Rows Kept`, `Invalid Rows Dropped`.

### Page 6: `6. About & Limitations`
- **File:** [`dashboard/pages/6_About_And_Limitations.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/6_About_And_Limitations.py)
- **Purpose:** System architecture description, explicit PRD non-claims, dataset size metrics, trained model metadata JSON, and documentation links.
- **Exact Non-Claims List:**
  1. Provide universal 5G anomaly detection generalizable beyond the collected dataset.
  2. Guarantee identification of root cause (attributions are correlation-based).
  3. Guarantee correct SA/NSA identification when reported as UNKNOWN.
  4. Control or modify the operator network or device connection state in any way.
  5. Treat every cell transition or weak-signal reading as an anomaly on its own.

---

## 3. Sidebar & Global State Management

- **Implementation File:** [`dashboard/sidebar.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/sidebar.py)
- **Controls & Key Mapping:**
  - `dataset_source` (`st.sidebar.radio`): `["Processed Dataset (data/processed)", "Sample Excerpt (data/sample)"]`.
  - `sel_device` (`st.sidebar.selectbox`): Filter by device slug.
  - `sel_operator` (`st.sidebar.selectbox`): Filter by operator name.
  - `sel_session` (`st.sidebar.selectbox`): Filter by session ID.
  - `replay_idx` (`st.sidebar.slider`): Replay slider position from index 0 to `num_samples - 1`.
- **Uploaded CSV Validation Rules ([`dashboard/data_loader.py:L112-L170`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/data_loader.py#L112-L170)):**
  - File extension check: Must end with `.csv`. Error: `"❌ Invalid file format for... Please upload a valid CSV measurement file."`
  - Size cap check: Max 20 MB (`20 * 1024 * 1024` bytes). Error: `"❌ File size error: ... exceeds the 20 MB limit."`
  - Parse check: Must parse cleanly via `pd.read_csv`. Error: `"❌ Could not parse ... as a valid CSV"`.
  - Non-empty check: Must contain rows. Error: `"❌ Uploaded file ... is empty."`
  - PII audit check: `assert_no_pii_columns(df)` rejects columns like `latitude`, `longitude`, `imei`, `imsi`.
  - Raw column schema check: `validate_raw_columns(df)`.

---

## 4. Data Access & Loader Functions

Defined in [`dashboard/data_loader.py`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/data_loader.py):

| Loader Function | Decorator | Primary Path | Fallback Path | Columns / Fields Used |
|---|---|---|---|---|
| `load_scores_data()` | `@st.cache_data` | `data/processed/scores.csv` | `data/sample/sample_measurements.csv` | `timestamp`, `device`, `operator`, `network_type`, `deployment_mode`, `registered`, `ss_rsrp`, `ss_rsrq`, `ss_sinr`, `pci`, `nci`, `nrarfcn`, `session_id`, `sample_idx`, `is_anom`, `anomaly_type`, `severity`, `baseline_flag`, `if_flag`, `if_score` |
| `load_events_diagnosed()` | `@st.cache_data` | `data/processed/events_diagnosed.json` | None | `event_id`, `session_id`, `start`, `end`, `anomaly_type`, `severity`, `signal_report`, `cell_report`, `network_report`, `diagnosis`, `recommendation` |
| `load_model_metadata()` | `@st.cache_data` | `models/if_v1.meta.json` | None | Full JSON dict (`model_type`, `features`, `hyperparameters`, `training_samples`, `timestamp`) |
| `load_preprocess_log()` | `@st.cache_data` | `data/processed/preprocess_log.json` | None | `raw_rows_loaded`, `valid_rows_kept`, `invalid_rows_dropped`, `rejected_reasons` |

---

## 5. Dashboard Business Logic Audit

1. `calc_delta(curr, prev)` ([`1_Overview.py:L99-L109`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/1_Overview.py#L99-L109)): Computes single-sample metric delta $c - p$, returning formatted string `+1.5` / `-2.0`.
2. Status Banner Logic ([`1_Overview.py:L47-L52`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/1_Overview.py#L47-L52)): Evaluates `is_anom` as True if `is_anom == True` or `anomaly_type` is not in `("NORMAL", "CELL_TRANSITION", "NETWORK_STATE_TRANSITION")`.
3. Downsampling ([`2_Signal_Explorer.py:L85-L87`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/2_Signal_Explorer.py#L85-L87)): Triggers `plot_df = plot_df.iloc[::2]` when total samples $> 5000$.
4. Cell & Network Transition Loop ([`3_Cells_And_Network.py:L42-L78`](file:///d:/5G-Network-Anomaly-Detection-System/dashboard/pages/3_Cells_And_Network.py#L42-L78)): Iterates through rows to detect shift points where `pci` or `network_type` changes relative to row $i-1$.

> ⚠️ **Business Logic Finding:** Transition event detection in `3_Cells_And_Network.py` manually re-computes handover transitions from dataframe columns rather than consuming pre-grouped event records. All anomaly detection, z-score computation, Isolation Forest scoring, severity assignment, and multi-agent diagnoses are computed upstream in `ml/` and `agents/` modules.

---

## 6. Dashboard Test Suite

1. [`tests/test_dashboard_smoke.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_dashboard_smoke.py): 7 tests using `streamlit.testing.v1.AppTest` verifying that `app.py` and all 6 pages load without exceptions.
2. [`tests/test_dashboard_loader.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_dashboard_loader.py): 3 tests verifying missing file handling, valid CSV loading, timestamp conversion, and JSON loader functionality.
3. [`tests/test_dashboard_pages.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_dashboard_pages.py): 5 tests verifying design system hex codes, severity color mappings, and uploaded CSV validation rules (extension, size >20MB, PII rejection).
4. [`tests/test_dashboard_sidebar.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_dashboard_sidebar.py): 1 test asserting sidebar rendering, filter options, and `st.session_state` filter propagation.

---

## 7. Captured Screenshots

Full-page screenshots captured via automated headless browser and saved to `docs/inventory/screens/`:
- `docs/inventory/screens/page_1_overview.png`
- `docs/inventory/screens/page_2_signal_explorer.png`
- `docs/inventory/screens/page_3_cells_and_network.png`
- `docs/inventory/screens/page_4_events_and_diagnosis.png`
- `docs/inventory/screens/page_5_data_quality.png`
- `docs/inventory/screens/page_6_about_and_limitations.png`

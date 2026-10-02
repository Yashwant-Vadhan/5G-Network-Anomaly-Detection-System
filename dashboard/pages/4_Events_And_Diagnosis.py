"""4. Events & Diagnosis Page for 5G-NADS Dashboard (T6-007).

Provides event list table, filters by type and severity, multi-agent structured reports
(Signal, Cell, Network, Diagnosis, Recommendation), event-window visualization, and JSON download.
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import load_events_diagnosed
from dashboard.sidebar import render_sidebar
from dashboard.theme import CHART_ANOMALY_MARKER, CHART_RSRP, get_plotly_layout_defaults

st.set_page_config(page_title="4. Events & Diagnosis - 5G-NADS", layout="wide")

df, filter_state = render_sidebar()

st.title("4. Events & Diagnosis")
st.caption(
    "Inspect contiguous anomaly events, agent diagnostic evidence, and actionable recommendations."
)

events = load_events_diagnosed()

if events is None:
    st.info("`events_diagnosed.json` missing — run pipeline (`python -m pipelines.run_pipeline`).")
    st.stop()

if len(events) == 0:
    st.info("No events detected for this selection. This does not guarantee network was healthy.")
    st.stop()

# Convert events to DataFrame for filtering and table display
events_df = pd.DataFrame(events)

# Filter controls
col_f1, col_f2 = st.columns(2)
with col_f1:
    all_types = ["All Types"] + sorted(events_df["anomaly_type"].dropna().unique().tolist())
    sel_type = st.selectbox("Filter by Anomaly Type", options=all_types, index=0)

with col_f2:
    all_sevs = ["All Severities"] + sorted(events_df["max_severity"].dropna().unique().tolist())
    sel_sev = st.selectbox("Filter by Severity", options=all_sevs, index=0)

filtered_events = events_df.copy()
if sel_type != "All Types":
    filtered_events = filtered_events[filtered_events["anomaly_type"] == sel_type]
if sel_sev != "All Severities":
    filtered_events = filtered_events[filtered_events["max_severity"] == sel_sev]

st.markdown(f"### Events List ({len(filtered_events)} matched)")

if filtered_events.empty:
    st.info("No events match the selected filters.")
    st.stop()

# Select event row
display_cols = [
    c
    for c in [
        "event_id",
        "session_id",
        "device",
        "start_time",
        "end_time",
        "sample_count",
        "anomaly_type",
        "max_severity",
    ]
    if c in filtered_events.columns
]

selected_event_id = st.selectbox(
    "Select an Event to View Agent Diagnosis",
    options=filtered_events["event_id"].tolist(),
    index=0,
)

st.dataframe(filtered_events[display_cols], use_container_width=True)

# Selected event details
selected_evt = next((e for e in events if e.get("event_id") == selected_event_id), None)

if selected_evt:
    st.markdown("---")
    st.markdown(f"## Event Detail: `{selected_evt.get('event_id')}`")

    # JSON Download button (Contract C5)
    evt_json_str = json.dumps(selected_evt, indent=2)
    st.download_button(
        label="📥 Download Event JSON",
        data=evt_json_str,
        file_name=f"{selected_evt.get('event_id')}_diagnosed.json",
        mime="application/json",
    )

    # 3-column layout for Agent Reports
    col_sig, col_cell, col_net = st.columns(3)

    sig_report = selected_evt.get("signal_report", {})
    cell_report = selected_evt.get("cell_report", {})
    net_report = selected_evt.get("network_report", {})

    with col_sig:
        with st.container(border=True):
            st.markdown("### 📶 Signal Agent")
            st.markdown(f"**Condition:** `{sig_report.get('signal_condition', 'unknown')}`")
            st.markdown("**Evidence:**")
            for ev in sig_report.get("evidence", []):
                st.markdown(f"- {ev}")

    with col_cell:
        with st.container(border=True):
            st.markdown("### 🗼 Cell Agent")
            st.markdown(f"**Cell Event:** `{cell_report.get('cell_event', 'NONE')}`")
            st.markdown("**Evidence:**")
            for ev in cell_report.get("evidence", []):
                st.markdown(f"- {ev}")

    with col_net:
        with st.container(border=True):
            st.markdown("### 🌐 Network Agent")
            st.markdown(f"**State:** `{net_report.get('network_state', 'stable')}`")
            st.markdown(f"**Deployment:** `{net_report.get('deployment_mode', 'UNKNOWN')}`")
            st.markdown("**Evidence:**")
            for ev in net_report.get("evidence", []):
                st.markdown(f"- {ev}")

    # Diagnosis & Recommendation Row
    col_diag, col_rec = st.columns([7, 5])
    diagnosis_data = selected_evt.get("diagnosis", {})
    recommendation_data = selected_evt.get("recommendation", {})

    with col_diag:
        with st.container(border=True):
            st.markdown("### 🧠 Diagnosis Agent")
            st.markdown(f"**Summary:** {diagnosis_data.get('summary', '—')}")
            st.markdown(f"**Confidence Note:** *{diagnosis_data.get('confidence_note', '—')}*")
            st.markdown("**Aggregated Evidence:**")
            for ev in diagnosis_data.get("evidence", []):
                st.markdown(f"- {ev}")

    with col_rec:
        with st.container(border=True):
            st.markdown("### 💡 Recommendation Agent")
            kind = recommendation_data.get("kind", "MONITORING")
            st.markdown(f"**Kind:** `{kind}`")
            st.info(recommendation_data.get("text", "No recommendation provided."))

    # Event Window Mini-Chart
    if df is not None and not df.empty:
        st.markdown("### Event Window Telemetry")
        start_t = selected_evt.get("start_time")
        end_t = selected_evt.get("end_time")
        sess = selected_evt.get("session_id")

        window_df = df.copy()
        if "session_id" in window_df.columns and sess:
            window_df = window_df[window_df["session_id"] == sess]

        if "timestamp" in window_df.columns and start_t and end_t:
            w_start = pd.to_datetime(start_t)
            w_end = pd.to_datetime(end_t)
            evt_mask = (window_df["timestamp"] >= w_start) & (window_df["timestamp"] <= w_end)
            evt_slice = window_df[evt_mask]

            if not evt_slice.empty:
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=window_df["timestamp"],
                        y=window_df["ss_rsrp"],
                        mode="lines",
                        name="RSRP (Session Context)",
                        line=dict(color=CHART_RSRP, width=1.5),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=evt_slice["timestamp"],
                        y=evt_slice["ss_rsrp"],
                        mode="lines+markers",
                        name="Event Span",
                        line=dict(color=CHART_ANOMALY_MARKER, width=3),
                        marker=dict(symbol="x", size=8),
                    )
                )
                layout = get_plotly_layout_defaults()
                layout["height"] = 300
                fig.update_layout(**layout)
                st.plotly_chart(fig, use_container_width=True)

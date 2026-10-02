"""2. Signal Explorer Page for 5G-NADS Dashboard (T6-004).

Provides stacked Plotly time-series charts for RSRP, RSRQ, SINR with red anomaly markers,
flag filter toggles, text summaries, and an interactive data table.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.sidebar import render_sidebar
from dashboard.theme import (
    CHART_ANOMALY_MARKER,
    CHART_RSRP,
    CHART_RSRQ,
    CHART_SINR,
    get_plotly_layout_defaults,
)

st.set_page_config(page_title="2. Signal Explorer - 5G-NADS", layout="wide")

df, filter_state = render_sidebar()

st.title("2. Signal Explorer")
st.caption(
    "Deep-dive time-series analysis of SS-RSRP, SS-RSRQ, and SS-SINR metrics with flag overlays."
)

if df is None or df.empty:
    st.info("No valid samples for the selected device/session.")
    st.stop()

# Check column presence
missing_cols = [c for c in ["ss_rsrp", "ss_rsrq", "ss_sinr"] if c not in df.columns]
if missing_cols:
    st.error(f"Could not plot: column `{missing_cols[0]}` is entirely missing for this selection.")
    st.stop()

# Flag selection toggles
col_t1, col_t2 = st.columns([4, 4])
with col_t1:
    flag_opts = [
        "Both Flags (Baseline & IF)",
        "Baseline Flags Only",
        "IF Flags Only",
        "Hide Flags",
    ]
    flag_toggle = st.radio(
        "Anomaly Marker Overlay",
        options=flag_opts,
        index=0,
        horizontal=True,
    )
with col_t2:
    show_rolling = st.checkbox("Show Rolling Mean Overlay", value=True)

# Filter flagged samples based on selection
if flag_toggle == "Both Flags (Baseline & IF)":
    base_f = df.get("baseline_flag", False)
    if_f = df.get("if_flag", False)
    anom_mask = (base_f == True) | (if_f == True)  # noqa: E712
elif flag_toggle == "Baseline Flags Only":
    anom_mask = df.get("baseline_flag", False) == True  # noqa: E712
elif flag_toggle == "IF Flags Only":
    anom_mask = df.get("if_flag", False) == True  # noqa: E712
else:
    anom_mask = pd.Series(False, index=df.index)

anom_df = df[anom_mask]

# Downsampling for performance if > 5000 points
plot_df = df.copy()
if len(plot_df) > 5000:
    st.caption("⚡ Large dataset (>5,000 samples) downsampled 2x for rendering performance.")
    plot_df = plot_df.iloc[::2]


# Text Summaries above charts
def summarize_metric(series: pd.Series, name: str, unit: str) -> str:
    valid = series.dropna()
    if valid.empty:
        return f"**{name}:** No valid measurements available in window."
    min_v, max_v, mean_v = valid.min(), valid.max(), valid.mean()
    return f"**{name}:** min {min_v:.1f} {unit}, max {max_v:.1f} {unit}, mean {mean_v:.1f} {unit}."


st.markdown("### Signal Summary")
st.markdown(
    f"- {summarize_metric(df['ss_rsrp'], 'SS-RSRP', 'dBm')}\n"
    f"- {summarize_metric(df['ss_rsrq'], 'SS-RSRQ', 'dB')}\n"
    f"- {summarize_metric(df['ss_sinr'], 'SS-SINR', 'dB')}"
)

# Plotly Stacked Subplots (3 rows, 1 col, shared x axis)
fig = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.06,
    subplot_titles=("SS-RSRP (dBm)", "SS-RSRQ (dB)", "SS-SINR (dB)"),
)

# 1. RSRP
fig.add_trace(
    go.Scatter(
        x=plot_df["timestamp"],
        y=plot_df["ss_rsrp"],
        mode="lines",
        name="RSRP",
        line=dict(color=CHART_RSRP, width=1.5),
        hovertemplate="Time: %{x}<br>RSRP: %{y:.1f} dBm<extra></extra>",
    ),
    row=1,
    col=1,
)
if show_rolling and "rolling_mean_ss_rsrp" in plot_df.columns:
    fig.add_trace(
        go.Scatter(
            x=plot_df["timestamp"],
            y=plot_df["rolling_mean_ss_rsrp"],
            mode="lines",
            name="RSRP Rolling Mean",
            line=dict(color=CHART_RSRP, width=1.0, dash="dash"),
        ),
        row=1,
        col=1,
    )
if not anom_df.empty and "ss_rsrp" in anom_df.columns:
    fig.add_trace(
        go.Scatter(
            x=anom_df["timestamp"],
            y=anom_df["ss_rsrp"],
            mode="markers",
            name="Anomaly Flagged",
            marker=dict(symbol="x", size=9, color=CHART_ANOMALY_MARKER, linewidth=2),
            hovertemplate="Anomaly Flagged<br>Time: %{x}<br>RSRP: %{y:.1f} dBm<extra></extra>",
        ),
        row=1,
        col=1,
    )

# 2. RSRQ
fig.add_trace(
    go.Scatter(
        x=plot_df["timestamp"],
        y=plot_df["ss_rsrq"],
        mode="lines",
        name="RSRQ",
        line=dict(color=CHART_RSRQ, width=1.5),
        hovertemplate="Time: %{x}<br>RSRQ: %{y:.1f} dB<extra></extra>",
    ),
    row=2,
    col=1,
)
if show_rolling and "rolling_mean_ss_rsrq" in plot_df.columns:
    fig.add_trace(
        go.Scatter(
            x=plot_df["timestamp"],
            y=plot_df["rolling_mean_ss_rsrq"],
            mode="lines",
            name="RSRQ Rolling Mean",
            line=dict(color=CHART_RSRQ, width=1.0, dash="dash"),
        ),
        row=2,
        col=1,
    )
if not anom_df.empty and "ss_rsrq" in anom_df.columns:
    fig.add_trace(
        go.Scatter(
            x=anom_df["timestamp"],
            y=anom_df["ss_rsrq"],
            mode="markers",
            name="Anomaly Flagged",
            marker=dict(symbol="x", size=9, color=CHART_ANOMALY_MARKER, linewidth=2),
            showlegend=False,
            hovertemplate="Anomaly Flagged<br>Time: %{x}<br>RSRQ: %{y:.1f} dB<extra></extra>",
        ),
        row=2,
        col=1,
    )

# 3. SINR
fig.add_trace(
    go.Scatter(
        x=plot_df["timestamp"],
        y=plot_df["ss_sinr"],
        mode="lines",
        name="SINR",
        line=dict(color=CHART_SINR, width=1.5),
        hovertemplate="Time: %{x}<br>SINR: %{y:.1f} dB<extra></extra>",
    ),
    row=3,
    col=1,
)
if show_rolling and "rolling_mean_ss_sinr" in plot_df.columns:
    fig.add_trace(
        go.Scatter(
            x=plot_df["timestamp"],
            y=plot_df["rolling_mean_ss_sinr"],
            mode="lines",
            name="SINR Rolling Mean",
            line=dict(color=CHART_SINR, width=1.0, dash="dash"),
        ),
        row=3,
        col=1,
    )
if not anom_df.empty and "ss_sinr" in anom_df.columns:
    fig.add_trace(
        go.Scatter(
            x=anom_df["timestamp"],
            y=anom_df["ss_sinr"],
            mode="markers",
            name="Anomaly Flagged",
            marker=dict(symbol="x", size=9, color=CHART_ANOMALY_MARKER, linewidth=2),
            showlegend=False,
            hovertemplate="Anomaly Flagged<br>Time: %{x}<br>SINR: %{y:.1f} dB<extra></extra>",
        ),
        row=3,
        col=1,
    )

# Apply Plotly layout defaults
layout_defaults = get_plotly_layout_defaults()
layout_defaults["height"] = 700
fig.update_layout(**layout_defaults)

st.plotly_chart(fig, use_container_width=True)

# Data Table Expander
with st.expander("📋 Show Data Table"):
    display_cols = [
        c
        for c in [
            "timestamp",
            "device",
            "operator",
            "ss_rsrp",
            "ss_rsrq",
            "ss_sinr",
            "pci",
            "nci",
            "baseline_flag",
            "if_flag",
            "anomaly_type",
            "severity",
        ]
        if c in df.columns
    ]
    st.dataframe(df[display_cols].fillna("—"), use_container_width=True)

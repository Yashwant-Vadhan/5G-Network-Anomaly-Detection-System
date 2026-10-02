"""3. Cells & Network Page for 5G-NADS Dashboard (T6-005).

Provides visualization of cell transitions (PCI, NCI, NRARFCN) and network-type
changes (5G NR vs LTE) with transition event tables and neutral copy framing.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.sidebar import render_sidebar
from dashboard.theme import (
    CHART_CELL_MARKER,
    CHART_RSRP,
    CHART_SINR,
    get_plotly_layout_defaults,
)

st.set_page_config(page_title="3. Cells & Network - 5G-NADS", layout="wide")

df, filter_state = render_sidebar()

st.title("3. Cells & Network")

# Required copy rule header note (DESIGN.md §Screen 3)
st.info(
    "💡 **Note:** A cell change is normal network behaviour. "
    "It is highlighted here as an *event*, not as an anomaly."
)

if df is None or df.empty:
    st.info("No cell or network transitions in this selection.")
    st.stop()

# Detect cell & network transition events
transitions = []

# PCI transitions
if "pci" in df.columns:
    pci_series = df["pci"].dropna()
    pci_shifts = df[df["pci"] != df["pci"].shift(1)]
    for idx, row in pci_shifts.iterrows():
        if idx > df.index[0]:
            prev_pci = df.loc[idx - 1, "pci"] if (idx - 1) in df.index else "Unknown"
            curr_pci = row["pci"]
            if pd.notna(prev_pci) and pd.notna(curr_pci) and prev_pci != curr_pci:
                transitions.append(
                    {
                        "Timestamp": str(row["timestamp"]),
                        "Event Type": "PCI Transition",
                        "From": str(prev_pci),
                        "To": str(curr_pci),
                        "Device": str(row.get("device", "—")),
                        "Session": str(row.get("session_id", "—")),
                    }
                )

# Network Type transitions
if "network_type" in df.columns:
    net_shifts = df[df["network_type"] != df["network_type"].shift(1)]
    for idx, row in net_shifts.iterrows():
        if idx > df.index[0]:
            prev_net = df.loc[idx - 1, "network_type"] if (idx - 1) in df.index else "Unknown"
            curr_net = row["network_type"]
            if pd.notna(prev_net) and pd.notna(curr_net) and prev_net != curr_net:
                transitions.append(
                    {
                        "Timestamp": str(row["timestamp"]),
                        "Event Type": "Network Type Change",
                        "From": str(prev_net),
                        "To": str(curr_net),
                        "Device": str(row.get("device", "—")),
                        "Session": str(row.get("session_id", "—")),
                    }
                )

# Charts Section
st.markdown("### Cell & Frequency Timeline")

fig = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.06,
    subplot_titles=("Physical Cell ID (PCI)", "5G Cell ID (NCI)", "NRARFCN Frequency"),
)

# 1. PCI Step Line
if "pci" in df.columns:
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["pci"],
            mode="lines+markers",
            line=dict(shape="hv", color=CHART_RSRP, width=2),
            marker=dict(symbol="circle", size=5),
            name="PCI",
            hovertemplate="Time: %{x}<br>PCI: %{y}<extra></extra>",
        ),
        row=1,
        col=1,
    )

# 2. NCI Step Line / Categorical
if "nci" in df.columns:
    nci_str = df["nci"].astype(str).replace("nan", "—")
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=nci_str,
            mode="lines+markers",
            line=dict(shape="hv", color=CHART_SINR, width=2),
            marker=dict(symbol="square", size=5),
            name="NCI",
            hovertemplate="Time: %{x}<br>NCI: %{y}<extra></extra>",
        ),
        row=2,
        col=1,
    )

# 3. NRARFCN Line
if "nrarfcn" in df.columns:
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["nrarfcn"],
            mode="lines+markers",
            line=dict(color=CHART_CELL_MARKER, width=1.5),
            name="NRARFCN",
            hovertemplate="Time: %{x}<br>NRARFCN: %{y}<extra></extra>",
        ),
        row=3,
        col=1,
    )

layout = get_plotly_layout_defaults()
layout["height"] = 650
fig.update_layout(**layout)
st.plotly_chart(fig, use_container_width=True)
st.caption(
    "Chart Summary: Displays step-wise Physical Cell ID (PCI) handovers, 5G Cell ID "
    "(NCI) transitions, and NRARFCN frequency channel changes over time across "
    "recorded sessions."
)

# Transition Events Table
st.markdown("### Transition Events")
if transitions:
    trans_df = pd.DataFrame(transitions)
    st.dataframe(trans_df, use_container_width=True)
else:
    st.info("No cell identifier or network type transition events recorded in this selection.")

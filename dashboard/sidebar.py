"""Global Sidebar Component for 5G-NADS Dashboard (T6-010).

Provides dataset selection, device/operator/session filters, and replay slider
with state persistence in st.session_state across all pages.
"""

from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st
from dashboard.data_loader import load_scores_data


def render_sidebar() -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Render global sidebar filters and return the filtered dataframe and active filter state.

    Returns:
        Tuple of (filtered_dataframe_or_None, filter_state_dict).
    """
    st.sidebar.title("📡 5G-NADS")
    st.sidebar.caption("5G Network Anomaly Detection System")

    # Load dataset based on user choice
    dataset_choice = st.sidebar.radio(
        "Dataset Source",
        options=["Processed Dataset (data/processed)", "Sample Excerpt (data/sample)"],
        index=0,
        key="dataset_source",
    )

    if dataset_choice.startswith("Processed"):
        df = load_scores_data("data/processed/scores.csv")
    else:
        df = load_scores_data("data/sample/sample_measurements.csv")

    if df is None or df.empty:
        st.sidebar.warning("No data available for selected source.")
        return None, {}

    # Filters
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")

    # Device filter
    devices = sorted(df["device"].dropna().astype(str).unique().tolist())
    all_devices = ["All Devices"] + devices
    selected_device = st.sidebar.selectbox("Device", options=all_devices, index=0, key="sel_device")

    filtered_df = df.copy()
    if selected_device != "All Devices":
        filtered_df = filtered_df[filtered_df["device"].astype(str) == selected_device]

    # Operator filter
    operators = sorted(filtered_df["operator"].dropna().astype(str).unique().tolist())
    all_operators = ["All Operators"] + operators
    selected_operator = st.sidebar.selectbox("Operator", options=all_operators, index=0, key="sel_operator")

    if selected_operator != "All Operators":
        filtered_df = filtered_df[filtered_df["operator"].astype(str) == selected_operator]

    # Session filter
    sessions = sorted(filtered_df["session_id"].dropna().astype(str).unique().tolist()) if "session_id" in filtered_df.columns else []
    all_sessions = ["All Sessions"] + sessions
    selected_session = st.sidebar.selectbox("Session", options=all_sessions, index=0, key="sel_session")

    if selected_session != "All Sessions" and "session_id" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["session_id"].astype(str) == selected_session]

    # Replay Slider
    st.sidebar.markdown("---")
    st.sidebar.subheader("Replay Controls")
    num_samples = len(filtered_df)

    if num_samples > 0:
        current_idx = st.session_state.get("replay_idx", 0)
        valid_idx = current_idx if current_idx < num_samples else 0
        replay_idx = st.sidebar.slider(
            "Replay Position",
            min_value=0,
            max_value=num_samples - 1,
            value=valid_idx,
            key="replay_idx",
            help="Select sample position in time to inspect overview metrics.",
        )
        current_sample = filtered_df.iloc[replay_idx]
    else:
        replay_idx = 0
        current_sample = None

    filter_state = {
        "dataset_choice": dataset_choice,
        "device": selected_device,
        "operator": selected_operator,
        "session": selected_session,
        "replay_idx": replay_idx,
        "current_sample": current_sample,
        "total_samples": num_samples,
    }

    return filtered_df, filter_state

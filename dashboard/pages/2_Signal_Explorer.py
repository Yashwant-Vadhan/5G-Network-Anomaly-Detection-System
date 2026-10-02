"""2. Signal Explorer Page for 5G-NADS Dashboard (T6-001)."""

from __future__ import annotations

import streamlit as st

from dashboard.data_loader import load_scores_data

st.set_page_config(page_title="2. Signal Explorer - 5G-NADS", layout="wide")
st.title("2. Signal Explorer")

df = load_scores_data()

if df is None:
    st.info("No valid samples for the selected device/session.")
else:
    st.write("Signal telemetry visualization placeholder.")

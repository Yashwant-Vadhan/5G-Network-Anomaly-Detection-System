"""3. Cells & Network Page for 5G-NADS Dashboard (T6-001)."""

from __future__ import annotations

import streamlit as st

from dashboard.data_loader import load_scores_data

st.set_page_config(page_title="3. Cells & Network - 5G-NADS", layout="wide")
st.title("3. Cells & Network")

st.info(
    "A cell change is normal network behaviour."
    " It is highlighted here as an *event*, not as an anomaly."
)

df = load_scores_data()
if df is None:
    st.info("No cell or network transitions in this selection.")
else:
    st.write("Cell and network transition timelines placeholder.")

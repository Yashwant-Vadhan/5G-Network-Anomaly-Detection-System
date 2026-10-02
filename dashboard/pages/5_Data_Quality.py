"""5. Data Quality Page for 5G-NADS Dashboard (T6-001)."""

from __future__ import annotations

import streamlit as st

from dashboard.data_loader import load_preprocess_log, load_scores_data

st.set_page_config(page_title="5. Data Quality - 5G-NADS", layout="wide")
st.title("5. Data Quality")

df = load_scores_data()
log = load_preprocess_log()

if df is None:
    st.info("No data quality metrics available for this selection.")
else:
    st.write("Data quality summary placeholder.")

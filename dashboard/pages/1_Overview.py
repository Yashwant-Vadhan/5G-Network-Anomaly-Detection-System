"""1. Overview Page for 5G-NADS Dashboard (T6-001)."""

from __future__ import annotations

import streamlit as st
from dashboard.data_loader import load_events_diagnosed, load_scores_data

st.set_page_config(page_title="1. Overview - 5G-NADS", layout="wide")
st.title("1. Overview")

df = load_scores_data()
events = load_events_diagnosed()

if df is None:
    st.info("No processed data found. Run python -m pipelines.run_pipeline --input data/raw (see README).")
else:
    st.success(f"Dataset loaded successfully ({len(df)} samples).")
    st.dataframe(df.head())

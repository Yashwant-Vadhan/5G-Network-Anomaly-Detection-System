"""4. Events & Diagnosis Page for 5G-NADS Dashboard (T6-001)."""

from __future__ import annotations

import streamlit as st
from dashboard.data_loader import load_events_diagnosed

st.set_page_config(page_title="4. Events & Diagnosis - 5G-NADS", layout="wide")
st.title("4. Events & Diagnosis")

events = load_events_diagnosed()
if events is None:
    st.info("events_diagnosed.json missing — run the pipeline.")
elif len(events) == 0:
    st.info("No events detected for this selection. This does not guarantee the network was healthy.")
else:
    st.write(f"Diagnosed Events Count: {len(events)}")

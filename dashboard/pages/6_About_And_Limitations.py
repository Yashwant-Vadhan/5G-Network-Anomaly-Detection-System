"""6. About & Limitations Page for 5G-NADS Dashboard (T6-001)."""

from __future__ import annotations

import streamlit as st

from dashboard.data_loader import load_model_metadata

st.set_page_config(page_title="6. About & Limitations - 5G-NADS", layout="wide")
st.title("6. About & Limitations")

st.markdown("""
### 5G-NADS (5G Network Anomaly Detection System)

### Explicit Non-Claims
5G-NADS does **not** claim to:
- Provide universal 5G anomaly detection generalizable beyond the collected dataset
- Guarantee identification of root cause for a detected anomaly
- Guarantee correct SA/NSA identification when the device itself reports it as unknown
- Control or modify the operator network in any way
- Treat every cell transition, or every weak-signal reading, as an anomaly on its own
""")

meta = load_model_metadata()
if meta is None:
    st.info("Model metadata unavailable")
else:
    st.json(meta)

"""6. About & Limitations Page for 5G-NADS Dashboard (T6-011).

Provides architecture summary, PRD explicit non-claims, dataset documentation,
model metadata, and links to project documentation.
"""

from __future__ import annotations

import streamlit as st

from dashboard.data_loader import load_model_metadata, load_scores_data

st.set_page_config(page_title="6. About & Limitations - 5G-NADS", layout="wide")

st.title("6. About & Limitations")

st.markdown("""
### About 5G-NADS
**5G-NADS (5G Network Anomaly Detection System)** is a deterministic multi-agent and ML pipeline
designed to analyze 5G cellular signal telemetry collected from standard Android smartphones.
It detects anomalous degradation patterns (such as sudden SINR drops or persistent low quality)
and synthesizes human-readable evidence without relying on LLMs in the critical execution path.

---

### ⚠️ Explicit Non-Claims (PRD & Overview §53)
5G-NADS **does not** claim to:
1. Provide universal 5G anomaly detection generalizable beyond the collected dataset.
2. Guarantee identification of root cause (attributions are correlation-based).
3. Guarantee correct SA/NSA identification when reported as `UNKNOWN`.
4. Control or modify the operator network or device connection state in any way.
5. Treat every cell transition or weak-signal reading as an anomaly on its own.
""")

st.markdown("---")

# Dataset Summary Section
st.markdown("### 📊 Dataset Summary")
df = load_scores_data()

if df is not None and not df.empty:
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    col_d1.metric("Total Samples", f"{len(df):,}")
    col_d2.metric("Devices", len(df["device"].dropna().unique()))
    col_d3.metric("Operators", len(df["operator"].dropna().unique()))

    if "session_id" in df.columns:
        col_d4.metric("Sessions", len(df["session_id"].dropna().unique()))
else:
    st.info("No active dataset loaded for summary.")

st.markdown("---")

# Model Metadata Section
st.markdown("### 🤖 Trained Model Metadata (`models/if_v1.meta.json`)")
meta = load_model_metadata()

if meta is None:
    st.info(
        "Model metadata unavailable — train model via `python -m ml.train` or"
        " `python -m pipelines.run_pipeline`."
    )
else:
    st.json(meta)

st.markdown("---")

# Documentation Links
st.markdown("### 🔗 Project Documentation")
st.markdown("""
- [Repository README](https://github.com/Yashwant-Vadhan/5G-Network-Anomaly-Detection-System)
- [Project Overview & Guardrails](docs/planning/TECH_RULES.md)
- [Multi-Agent Data Contracts](agents/contracts.py)
""")

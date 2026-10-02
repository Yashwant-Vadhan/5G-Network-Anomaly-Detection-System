"""5. Data Quality Page for 5G-NADS Dashboard (T6-008).

Provides missing value tables, CSI availability, deployment mode distribution with
copy rule notes, preprocessing logs, and synthetic data indicators.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.data_loader import load_preprocess_log
from dashboard.sidebar import render_sidebar

st.set_page_config(page_title="5. Data Quality - 5G-NADS", layout="wide")

df, filter_state = render_sidebar()

st.title("5. Data Quality")
st.caption("Inspect missing metrics, device quirks, deployment modes, and preprocessing logs.")

if df is None or df.empty:
    st.info("No data quality metrics available for this selection.")
    st.stop()

# Synthetic Data Banner (DESIGN.md §Screen 5)
if "is_synthetic" in df.columns and df["is_synthetic"].fillna(False).astype(bool).any():
    st.warning(
        "⚠️ **Synthetic Data Banner:** This selection contains synthetic edge-case fixture rows"
        " (`is_synthetic = True`)."
    )

# 1. Missing Value Counts per Column per Device
st.markdown("### Missing-Value Counts per Column & Device")
devices = df["device"].dropna().unique()

missing_records = []
for dev in devices:
    dev_df = df[df["device"] == dev]
    total_rows = len(dev_df)
    row_dict = {"Device": dev, "Total Samples": total_rows}
    target_cols = [
        "ss_rsrp",
        "ss_rsrq",
        "ss_sinr",
        "csi_rsrp",
        "csi_rsrq",
        "csi_sinr",
        "pci",
        "nci",
        "nrarfcn",
    ]
    for col in target_cols:
        if col in dev_df.columns:
            missing_cnt = dev_df[col].isna().sum()
            missing_pct = (missing_cnt / total_rows * 100) if total_rows > 0 else 0
            row_dict[col] = f"{missing_cnt} ({missing_pct:.1f}%)"
        else:
            row_dict[col] = "N/A"
    missing_records.append(row_dict)

missing_df = pd.DataFrame(missing_records)
st.dataframe(missing_df, use_container_width=True)

# 2. CSI Availability per Device
st.markdown("### CSI Signal Availability")
if "csi_available" in df.columns:
    csi_summary = (
        df.groupby("device", observed=True)["csi_available"]
        .value_counts(normalize=True)
        .unstack()
        .fillna(0)
        * 100
    )
    st.dataframe(csi_summary.style.format("{:.1f}%"), use_container_width=True)
else:
    csi_cols = [c for c in ["csi_rsrp", "csi_rsrq", "csi_sinr"] if c in df.columns]
    csi_counts = df[csi_cols].notna().any(axis=1) if csi_cols else pd.Series(False, index=df.index)
    st.write("CSI availability calculated directly from non-null CSI columns:")
    st.dataframe(pd.DataFrame({"CSI Present": csi_counts.value_counts()}))

# 3. Deployment Mode Distribution with Copy Rule Note
st.markdown("### Deployment Mode Distribution")
st.info(
    "💡 **Copy Rule Note:** UNKNOWN means Android did not expose enough information."
    " It does not mean SA."
)

if "deployment_mode" in df.columns:
    dep_dist = df.groupby(["device", "deployment_mode"], observed=True).size().unstack(fill_value=0)
    st.dataframe(dep_dist, use_container_width=True)
else:
    st.write("No `deployment_mode` column present in this dataset.")

# 4. Sample Counts per Device / Operator / Session
st.markdown("### Sample Counts Summary")
group_cols = [c for c in ["device", "operator", "session_id"] if c in df.columns]
if group_cols:
    sample_counts = df.groupby(group_cols, observed=True).size().reset_index(name="Sample Count")
    st.dataframe(sample_counts, use_container_width=True)

# 5. Preprocessing Audit Log
st.markdown("### Preprocessing Log (Rows Removed by Validation)")
prep_log = load_preprocess_log()

if prep_log:
    c1, c2, c3 = st.columns(3)
    c1.metric("Raw Rows Loaded", prep_log.get("raw_rows_loaded", "—"))
    c2.metric("Valid Rows Kept", prep_log.get("valid_rows_kept", "—"))
    c3.metric("Invalid Rows Dropped", prep_log.get("invalid_rows_dropped", "—"))

    reasons = prep_log.get("rejected_reasons", {})
    if reasons:
        st.markdown("**Rejection Reasons:**")
        st.json(reasons)
else:
    st.info("`preprocess_log.json` unavailable.")

"""1. Overview Page for 5G-NADS Dashboard (T6-003).

Provides immediate view of network health, current sample metrics, network state,
anomaly score/flags, agent diagnosis, evidence, and recommendations.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from dashboard.data_loader import load_events_diagnosed
from dashboard.sidebar import render_sidebar
from dashboard.theme import (
    COLOR_ANOMALY,
    COLOR_NORMAL,
    COLOR_WARNING,
)

st.set_page_config(page_title="1. Overview - 5G-NADS", layout="wide")

df, filter_state = render_sidebar()

st.title("1. Overview")
st.caption("5G Network Anomaly Detection System — Real-time & Replay Diagnostic Overview")

if df is None or df.empty:
    st.info(
        "No processed data found."
        " Run `python -m pipelines.run_pipeline --input data/raw` (see README)."
    )
    st.stop()

current_sample = filter_state.get("current_sample")
replay_idx = filter_state.get("replay_idx", 0)

if current_sample is None:
    st.warning("No sample selected at current replay position.")
    st.stop()

# Previous sample for delta calculations
prev_sample = df.iloc[replay_idx - 1] if replay_idx > 0 else None

# Determine status and severity
is_anom = bool(current_sample.get("is_anom", False))
if not is_anom:
    anomaly_type = str(current_sample.get("anomaly_type", "NORMAL"))
    is_anom = anomaly_type not in ("NORMAL", "CELL_TRANSITION", "NETWORK_STATE_TRANSITION")

severity = str(current_sample.get("severity", "LOW")).upper()

# Status Banner (Row 1)
banner_container = st.container()
with banner_container:
    div_style = "color: white; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px;"
    if is_anom:
        sev_color = COLOR_ANOMALY if severity == "HIGH" else COLOR_WARNING
        h3_tag = '<h3 style="margin:0; padding:0; display:inline-block; font-size: 20px;">'
        span_tag = (
            '<span style="background-color: rgba(255,255,255,0.25); padding: 4px 10px;'
            ' border-radius: 12px; margin-left: 15px; font-weight: bold; font-size: 14px;">'
        )
        st.markdown(
            f"""
            <div style="background-color: {sev_color}; {div_style}">
                {h3_tag}⚠️ ANOMALY DETECTED</h3>
                {span_tag}Severity: {severity}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        h3_tag = '<h3 style="margin:0; padding:0; display:inline-block; font-size: 20px;">'
        span_tag = (
            '<span style="background-color: rgba(255,255,255,0.25); padding: 4px 10px;'
            ' border-radius: 12px; margin-left: 15px; font-weight: bold; font-size: 14px;">'
        )
        st.markdown(
            f"""
            <div style="background-color: {COLOR_NORMAL}; {div_style}">
                {h3_tag}✅ NORMAL OPERATING CONDITIONS</h3>
                {span_tag}Status: OK</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def format_val(val: float | int | str | None, unit: str = "", decimals: int = 1) -> str:
    if val is None or str(val) in ("nan", "NA", "None", "<NA>", "2147483647"):
        return "—"
    if isinstance(val, (float, int)):
        return f"{float(val):.{decimals}f} {unit}".strip()
    return f"{val} {unit}".strip()


def calc_delta(curr: Any, prev: Any, decimals: int = 1) -> str | None:
    try:
        if curr is not None and prev is not None:
            c = float(curr)
            p = float(prev)
            if not (c != c or p != p or c == 2147483647 or p == 2147483647):
                diff = c - p
                return f"{diff:+.{decimals}f}"
    except (ValueError, TypeError):
        pass
    return None


# Row 2: Network-State Card (4 col) + Metric Cards (8 col)
c1, c2 = st.columns([4, 8])

with c1:
    with st.container(border=True):
        st.caption("NETWORK & DEVICE STATE")
        dev = str(current_sample.get("device", "Unknown"))
        op = str(current_sample.get("operator", "Unknown"))
        net_type = str(current_sample.get("network_type", "Unknown"))

        dep_mode_raw = str(current_sample.get("deployment_mode", "UNKNOWN"))
        if dep_mode_raw == "UNKNOWN":
            dep_mode_disp = "Unknown (not exposed by this device)"
        else:
            dep_mode_disp = dep_mode_raw

        reg_val = current_sample.get("registered")
        if reg_val is True or reg_val == 1:
            reg_disp = "Yes"
        elif reg_val is False or reg_val == 0:
            reg_disp = "No"
        else:
            reg_disp = "—"

        st.markdown(f"**Device:** {dev}")
        st.markdown(f"**Operator:** {op}")
        st.markdown(f"**Network Type:** `{net_type}`")
        st.markdown(f"**Deployment Mode:** `{dep_mode_disp}`")
        st.markdown(f"**Registered:** {reg_disp}")

with c2:
    with st.container(border=True):
        st.caption("SIGNAL & CELL METRICS (REPLAY SAMPLE)")
        m1, m2, m3 = st.columns(3)
        m4, m5, m6 = st.columns(3)

        rsrp_val = current_sample.get("ss_rsrp")
        prev_rsrp = prev_sample.get("ss_rsrp") if prev_sample is not None else None
        rsrp_delta = calc_delta(rsrp_val, prev_rsrp)
        m1.metric("SS-RSRP", format_val(rsrp_val, "dBm"), delta=rsrp_delta, help="Missing: —")

        rsrq_val = current_sample.get("ss_rsrq")
        prev_rsrq = prev_sample.get("ss_rsrq") if prev_sample is not None else None
        rsrq_delta = calc_delta(rsrq_val, prev_rsrq)
        m2.metric("SS-RSRQ", format_val(rsrq_val, "dB"), delta=rsrq_delta, help="Missing: —")

        sinr_val = current_sample.get("ss_sinr")
        prev_sinr = prev_sample.get("ss_sinr") if prev_sample is not None else None
        sinr_delta = calc_delta(sinr_val, prev_sinr)
        m3.metric("SS-SINR", format_val(sinr_val, "dB"), delta=sinr_delta, help="Missing: —")

        pci_val = current_sample.get("pci")
        m4.metric("PCI (Cell ID)", format_val(pci_val, "", 0))

        nci_val = current_sample.get("nci")
        m5.metric("NCI (5G Cell)", format_val(nci_val, "", 0))

        nrarfcn_val = current_sample.get("nrarfcn")
        m6.metric("NRARFCN (Freq)", format_val(nrarfcn_val, "", 0))

st.markdown("---")

# Row 3: Score Gauge / Detection Breakdown (4 col) + Event & Diagnosis (8 col)
r3_c1, r3_c2 = st.columns([4, 8])

with r3_c1:
    with st.container(border=True):
        st.caption("ANOMALY DETECTION SCORES")
        if_score = current_sample.get("if_score")
        z_max = current_sample.get("baseline_z_max")

        base_flag = bool(current_sample.get("baseline_flag", False))
        if_flag = bool(current_sample.get("if_flag", False))

        if if_score is not None and not pd.isna(if_score):
            st.markdown(f"### IF Anomaly Score: **{float(if_score):.3f}** / 1.000")
        else:
            st.markdown("### IF Anomaly Score: *N/A (Ineligible)*")

        st.markdown(f"**Baseline Max |Z| Score:** `{format_val(z_max, '', 2)}`")
        st.markdown(
            f"**Baseline Flag:** `{'TRUE 🚩' if base_flag else 'False'}` | "
            f"**IF Flag:** `{'TRUE 🚩' if if_flag else 'False'}`"
        )

with r3_c2:
    with st.container(border=True):
        st.caption("DIAGNOSTICS & RECOMMENDATIONS")
        anom_type = str(current_sample.get("anomaly_type", "NORMAL"))
        st.markdown(f"**Detected Event Type:** `{anom_type}`")

        # Load diagnosed events list if available
        events = load_events_diagnosed()
        matching_event = None
        if events and current_sample.get("timestamp") is not None:
            curr_ts = str(current_sample.get("timestamp"))
            for evt in events:
                start_ts = evt.get("start") or evt.get("start_time")
                end_ts = evt.get("end") or evt.get("end_time")
                if start_ts and end_ts and str(start_ts) <= curr_ts <= str(end_ts):
                    matching_event = evt
                    break

        if matching_event and "diagnosis" in matching_event:
            diag = matching_event["diagnosis"]
            recom = matching_event.get("recommendation", {})
            st.markdown(f"**Diagnosis:** {diag.get('summary', 'No summary available.')}")

            evidence_list = diag.get("evidence", [])
            if evidence_list:
                st.markdown("**Evidence:**")
                for ev in evidence_list:
                    st.markdown(f"- {ev}")

            rec_text = recom.get("text", "Continue standard monitoring.")
            rec_kind = recom.get("kind", "MONITORING")
            st.info(f"💡 **Recommendation [{rec_kind}]:** {rec_text}")
        else:
            if anom_type == "NORMAL":
                st.success("Normal network operating conditions. No active anomaly event.")
            else:
                curr_ts = current_sample.get("timestamp")
                st.markdown(f"**Status:** {anom_type} observed at timestamp `{curr_ts}`.")
                st.info("💡 **Recommendation [MONITORING]:** Continue standard metric monitoring.")

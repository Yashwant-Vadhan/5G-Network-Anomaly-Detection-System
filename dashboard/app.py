"""Main Streamlit Entry Point for 5G-NADS Dashboard (T6-001).

Implements multipage navigation, global context sidebar, and app configuration.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="5G-NADS - 5G Network Anomaly Detection System",
    page_icon="📡",
    layout="wide",
)

st.sidebar.title("📡 5G-NADS")
st.sidebar.caption("5G Network Anomaly Detection System")

pages = [
    st.Page("pages/1_Overview.py", title="1. Overview", icon="📊", default=True),
    st.Page("pages/2_Signal_Explorer.py", title="2. Signal Explorer", icon="📈"),
    st.Page("pages/3_Cells_And_Network.py", title="3. Cells & Network", icon="🗼"),
    st.Page("pages/4_Events_And_Diagnosis.py", title="4. Events & Diagnosis", icon="🔍"),
    st.Page("pages/5_Data_Quality.py", title="5. Data Quality", icon="🛡️"),
    st.Page("pages/6_About_And_Limitations.py", title="6. About & Limitations", icon="ℹ️"),
]

pg = st.navigation(pages)
pg.run()

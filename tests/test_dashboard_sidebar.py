"""Unit tests for dashboard sidebar component (T6-010)."""

from __future__ import annotations

import pandas as pd
from unittest.mock import patch
from dashboard.sidebar import render_sidebar


def test_sidebar_rendering_with_data(tmp_path):
    """Verify render_sidebar operates correctly when data exists."""
    df = pd.DataFrame(
        {
            "device": ["Redmi", "Samsung"],
            "operator": ["Airtel", "Airtel"],
            "session_id": ["redmi-1", "samsung-1"],
            "ss_rsrp": [-80.0, -90.0],
            "timestamp": pd.date_range("2026-09-28T10:00:00Z", periods=2, freq="3s"),
        }
    )

    with patch("dashboard.sidebar.load_scores_data", return_value=df):
        with patch("streamlit.sidebar.radio", return_value="Processed Dataset (data/processed)"):
            with patch("streamlit.sidebar.selectbox", side_effect=["All Devices", "All Operators", "All Sessions"]):
                with patch("streamlit.sidebar.slider", return_value=0):
                    filtered_df, state = render_sidebar()
                    assert filtered_df is not None
                    assert len(filtered_df) == 2
                    assert state["total_samples"] == 2
                    assert state["replay_idx"] == 0
                    assert state["current_sample"]["ss_rsrp"] == -80.0

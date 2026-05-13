import streamlit as st

from views.matching_view import render_matching_section
from views.trend_view import render_trend_section
from views.weekly_view import render_weekly_section


st.set_page_config(layout="wide", page_title="CSV Matcher")
st.title("APC Validation")

tab_match, tab_trend, tab_weekly = st.tabs([
    "🛡️ Daily Matching Data",
    "📊 Trend Consolidation",
    "📋 Weekly Report",
])

with tab_match:
    render_matching_section()

with tab_trend:
    trend_data = render_trend_section()

with tab_weekly:
    if trend_data is not None:
        full_df, valid_df = trend_data
        render_weekly_section(full_df, valid_df)
    else:
        st.info("Upload daily reports in the **Trend Consolidation** tab to enable the weekly view.")

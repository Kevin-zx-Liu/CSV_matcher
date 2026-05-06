import streamlit as st

from views.matching_view import render_matching_section
from views.trend_view import render_trend_section
from views.weekly_view import render_weekly_section


st.set_page_config(layout="wide", page_title="CSV Matcher")
st.title("🛡️ APC Validation")

render_matching_section()

trend_data = render_trend_section()
if trend_data is not None:
    full_df, valid_df = trend_data
    render_weekly_section(full_df, valid_df)

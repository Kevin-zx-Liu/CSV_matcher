import pandas as pd
import streamlit as st

from charts import build_current_week_bar, build_weekly_trend_chart


def render_weekly_section(full_df, valid_df):
    st.header("📋 Weekly Report & Trend Analysis")

    wk_col1, wk_col2 = st.columns([1, 3])
    with wk_col1:
        _render_current_week_summary(full_df, valid_df)
    with wk_col2:
        _render_weekly_historical_trend()


def _render_current_week_summary(full_df, valid_df):
    st.subheader("Current Week Summary")
    st.write("Overall summary based on current uploaded daily reports.")

    total_cases = len(full_df)
    status_counts = full_df['Match_Status'].value_counts()

    m_count = status_counts.get('Matching', 0)
    u_count = status_counts.get('Update needed', 0)
    ms_count = status_counts.get('Missing', 0)

    m_rate = (m_count / total_cases * 100) if total_cases > 0 else 0
    u_rate = (u_count / total_cases * 100) if total_cases > 0 else 0
    ms_rate = (ms_count / total_cases * 100) if total_cases > 0 else 0

    try:
        start_label = valid_df['Business_Date'].min().strftime('%m%d')
        end_label = valid_df['Business_Date'].max().strftime('%m%d')
        date_range_label = f"{start_label}-{end_label}"
    except Exception:
        date_range_label = "Overall"

    summary_df = pd.DataFrame({
        'Time': [date_range_label] * 3,
        'Match_Status': ['Matching', 'Update needed', 'Missing'],
        'Percentage': [round(m_rate, 1), round(u_rate, 1), round(ms_rate, 1)],
        'Count': [m_count, u_count, ms_count],
    })

    st.info(f"Period: **{date_range_label}** | Total Cases: **{total_cases}**")

    st.download_button(
        label="📥 Export Weekly Summary (CSV)",
        data=summary_df.to_csv(index=False).encode('utf-8'),
        file_name=f"weekly_summary_{date_range_label}.csv",
        mime="text/csv",
    )

    chart = build_current_week_bar(m_rate)
    st.altair_chart(chart, use_container_width=True)


def _render_weekly_historical_trend():
    st.subheader("Weekly Historical Trend")

    weekly_trend_files = st.file_uploader(
        "Upload Weekly Summaries to get weekly trend",
        accept_multiple_files=True,
        type="csv",
        key="wk_trend_uploader",
    )

    if not weekly_trend_files:
        st.info("👈 Upload previously exported weekly files here.")
        return

    all_wk_data = []
    for f in weekly_trend_files:
        try:
            df_wk = pd.read_csv(f)
            if all(col in df_wk.columns for col in ['Time', 'Match_Status', 'Percentage']):
                all_wk_data.append(df_wk)
        except Exception as e:
            st.error(f"Error loading {f.name}: {e}")

    if not all_wk_data:
        st.info("Upload valid weekly summary CSVs to generate the trend chart.")
        return

    combined_wk_df = pd.concat(all_wk_data, ignore_index=True).sort_values('Time', ascending=True)
    chart = build_weekly_trend_chart(combined_wk_df)
    st.altair_chart(chart, use_container_width=True)

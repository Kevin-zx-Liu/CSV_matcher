import pandas as pd
import streamlit as st

from trends import process_trend_reports, get_trend_suffix, get_apc_performance_data
from charts import build_daily_chart, build_reasons_chart, build_apc_performance_chart


def render_trend_section():
    """Renders the Trend Consolidation block. Returns (full_df, valid_df) when data is available, else None."""
    st.divider()
    st.header("📊 Trend Consolidation")

    trend_files = _render_trend_uploader()
    if not trend_files:
        return None

    all_reports, failed_files = process_trend_reports(trend_files)
    if failed_files:
        st.warning("⚠️ The following files were skipped:")
        st.dataframe(pd.DataFrame(failed_files), hide_index=True)

    if not all_reports:
        return None

    full_df = pd.concat(all_reports, ignore_index=True).drop_duplicates()
    full_df['DT'] = pd.to_datetime(full_df['Time'], format='%Y%m%d %H%M%S', errors='coerce')
    full_df.loc[full_df['DT'].isna(), 'DT'] = pd.to_datetime(
        full_df.loc[full_df['DT'].isna(), 'Time'], errors='coerce'
    )
    valid_df = full_df.dropna(subset=['DT']).copy()

    if valid_df.empty:
        return None

    valid_df['Business_Date'] = (valid_df['DT'] - pd.Timedelta(hours=7)).dt.normalize()
    trend_suffix = get_trend_suffix(valid_df)

    _render_chart_daily(valid_df, trend_suffix)
    _render_chart_reasons(valid_df, trend_suffix)
    _render_chart_performance(valid_df, trend_suffix)
    _render_detail_table(valid_df)

    return full_df, valid_df


def _render_trend_uploader():
    if "uploader_version" not in st.session_state:
        st.session_state.uploader_version = 0

    if st.button("🗑️ Clear All Uploaded Reports"):
        st.session_state.uploader_version += 1
        st.rerun()

    return st.file_uploader(
        "Upload Daily Reports",
        accept_multiple_files=True,
        type="csv",
        key=f"trend_uploader_v{st.session_state.uploader_version}",
    )


def _render_chart_daily(valid_df, trend_suffix):
    st.subheader("1. Daily Matching vs Missing (%)")
    chart = build_daily_chart(valid_df, trend_suffix)
    st.altair_chart(chart, use_container_width=True)


def _render_chart_reasons(valid_df, trend_suffix):
    if 'Reason' not in valid_df.columns:
        return
    st.divider()
    st.subheader("2. Missing Reasons Analysis")
    chart = build_reasons_chart(valid_df, trend_suffix)
    st.altair_chart(chart, use_container_width=True)


def _render_chart_performance(valid_df, trend_suffix):
    if 'Reason' not in valid_df.columns:
        st.warning("⚠️ No 'Reason' column found to analyze APC performance.")
        return

    st.divider()
    st.subheader("3. APC Performance Analysis")
    st.info("Percentage of 'Time is more accurate in APC'")
    perf_data = get_apc_performance_data(valid_df)

    if perf_data.empty:
        st.info("No 'Matching' status records found to calculate performance.")
        return

    chart = build_apc_performance_chart(perf_data, trend_suffix)
    st.altair_chart(chart, use_container_width=True)
    with st.expander("View Performance Details"):
        st.dataframe(
            perf_data[['Business_Date', 'Total_Matching', 'Accurate_Time_Count', 'Performance %']],
            hide_index=True,
        )


def _render_detail_table(valid_df):
    st.divider()
    st.subheader("📋 4. Detailed Records Analysis")

    if valid_df.empty:
        st.info("Upload trend reports above to analyze detailed data.")
        return

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        all_statuses = sorted(valid_df['Match_Status'].unique())
        target_defaults = ['Missing', 'Update needed']
        final_defaults = [status for status in target_defaults if status in all_statuses]
        selected_statuses = st.multiselect(
            "Filter by Status (Leave empty to show all):",
            options=all_statuses,
            default=final_defaults,
        )

    with filter_col2:
        available_charts = sorted(valid_df['CHARTNAME'].fillna("Unknown").str.lower().unique())
        selected_charts = st.multiselect(
            "Filter by Chart Name (Leave empty to show all):",
            options=available_charts,
        )

    filtered_df = valid_df.copy()
    if selected_statuses:
        filtered_df = filtered_df[filtered_df['Match_Status'].isin(selected_statuses)]
    if selected_charts:
        filtered_df = filtered_df[
            filtered_df['CHARTNAME'].fillna("Unknown").str.lower().isin(selected_charts)
        ]

    if filtered_df.empty:
        st.info("No records match the current filter criteria.")
        return

    start_dt = valid_df['Business_Date'].min().strftime('%Y-%m-%d')
    end_dt = valid_df['Business_Date'].max().strftime('%Y-%m-%d')
    export_filename = f"Filtered_Report_{start_dt}_to_{end_dt}.csv"

    st.write(f"Showing {len(filtered_df)} records.")

    export_columns = ['Match_Status', 'Reason', 'Time', 'CHARTNAME', 'ID', 'EQUIP', 'Info']
    available_export_cols = [c for c in export_columns if c in filtered_df.columns]

    st.download_button(
        label=f"📥 Export Current View ({export_filename})",
        data=filtered_df[available_export_cols].to_csv(index=False).encode('utf-8'),
        file_name=export_filename,
        mime="text/csv",
    )

    target_cols = ['Match_Status', 'Reason', 'ID', 'Time', 'CHARTNAME', 'EQUIP', 'Info']
    final_table = filtered_df[[c for c in target_cols if c in filtered_df.columns]]
    st.dataframe(final_table, use_container_width=True, hide_index=True)

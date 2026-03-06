import streamlit as st
import pandas as pd
import altair as alt
from utils import robust_scan
from logic import extract_metadata, apply_matching_logic, get_export_filename, process_trend_reports, get_reason_colors, get_trend_suffix, get_apc_performance_data

st.set_page_config(layout="wide", page_title="CSV Matcher")
st.title("🛡️ APC Validation")
st.markdown("Left File: **Temptation data** | Right Files: **APC data**")

col1, col2 = st.columns(2)
with col1:
    left_file = st.file_uploader("Upload Left CSV (Hold Data)", type="csv")
with col2:
    right_files = st.file_uploader("Upload Right CSV (Process Data)", type="csv", accept_multiple_files=True)

# Define target columns for scanning
left_targets = {'ID': ['LOT_ID', 'LOTID'], 'Time': ['LOT_HOLD_TIME', 'TIME'], 'Info': ['LOT_HOLD_COMMENT']}
right_targets = {
    'ID': ['LOTID', 'LOT_ID', 'BATCHID'], 'Chart': ['CHARTNAME', 'CHART'],
    'Time': ['DATETIME', 'TIME'], 'Equipment': ['EQPNAME', 'EQUIPMENT'], 'Eventlist': ['EVENTLIST', 'EVENT_LIST']
}

# --- 1. Scan Left File ---
if left_file:
    df_left, err_l = robust_scan(left_file, "Left", left_targets)
    
    if df_left is not None:
        df_left = extract_metadata(df_left)
        # Initialize default columns if matching hasn't happened yet
        if 'Found_in_Right' not in df_left.columns:
            df_left['Found_in_Right'] = False
        if 'CHARTNAME' not in df_left.columns:
            df_left['CHARTNAME'] = ""
        if 'EQUIP' not in df_left.columns:
            df_left['EQUIP'] = ""
        # Create a key for the selection logic even if empty
        df_left['__key'] = df_left['ID'].astype(str).str.upper().str.strip()

        # --- 2. Process Right Files (If they exist) ---
        df_right = None
        if right_files:
            all_right_dfs = []
            right_errors = []
            for f in right_files:
                df_r, err_r = robust_scan(f, f.name, right_targets)
                if df_r is not None:
                    all_right_dfs.append(df_r)
                else:
                    right_errors.append(err_r)

            if right_errors:
                for err in right_errors: st.error(f"❌ Right File Error: {err}")
            elif all_right_dfs:
                df_right = pd.concat(all_right_dfs, ignore_index=True).drop_duplicates()
                # Run the actual matching logic once both sides exist
                df_left, df_right = apply_matching_logic(df_left, df_right)
                st.success(f"✅ Loaded: {len(df_left)} rows (Left) vs {len(df_right)} unique rows (Right)")

        # --- 3. Interface Display (Always shows if Left exists) ---
        c1, c2 = st.columns([1, 1])
        with c1:
            st.subheader("1. Temptation Data")
            
            # Show Chart List code block if available
            if 'CHARTNAME' in df_left.columns and not df_left['CHARTNAME'].replace('', pd.NA).dropna().empty:
                unique_charts = sorted(df_left['CHARTNAME'].dropna().unique())
                formatted_list = ", ".join([f'"{chart}"' for chart in unique_charts])
                with st.expander("📋 View Chart Name List (String Format)"):
                    st.code(formatted_list, language="text")

            # Export Button
            df_export = df_left.copy()
            df_export['Match_Status'] = df_export['Found_in_Right'].apply(lambda x: "Matching" if x else "Missing")
            export_filename = get_export_filename(df_export)
            export_cols = [c for c in ['Match_Status', 'ID', 'Time', 'CHARTNAME', 'EQUIP', 'Info'] if c in df_export.columns]
            
            st.download_button(
                label=f"📥 Export Report ({export_filename})", 
                data=df_export[export_cols].to_csv(index=False).encode('utf-8'), 
                file_name=export_filename, 
                mime="text/csv"
            )

            # Dataframe Selection
            display_cols = ['Found_in_Right', 'ID', 'Time', 'CHARTNAME', 'EQUIP']
            selection = st.dataframe(
                df_left[[c for c in display_cols if c in df_left.columns]], 
                on_select="rerun", 
                selection_mode="single-row", 
                width=1000, 
                hide_index=True,
                column_config={
                    "Found_in_Right": st.column_config.CheckboxColumn("MatchFound", disabled=True), 
                    "Time": "Lothold Time"
                }
            )

        with c2:
            st.subheader("2. APC Data (Combined)")
            if df_right is not None and selection.selection["rows"]:
                idx = selection.selection["rows"][0]
                sel_key, sel_display = df_left.iloc[idx]['__key'], df_left.iloc[idx]['ID']
                st.info(f"Searching Combined Process Data for: **{sel_display}**")
                
                # Search logic
                if '.' in sel_display and 'Eventlist' in df_right.columns:
                    match = df_right[df_right['Eventlist'].astype(str).str.contains(sel_display, case=False, regex=False)]
                else:
                    match = df_right[df_right['__key'] == sel_key]
                
                if not match.empty:
                    cols_to_show = ['ID', 'Chart', 'Time', 'Equipment']
                    if 'Eventlist' in match.columns and '.' in sel_display: cols_to_show.append('Eventlist')
                    st.dataframe(match[[c for c in cols_to_show if c in match.columns]], width='stretch', hide_index=True)
                else:
                    st.warning("❌ No record found in any uploaded Right file.")
            elif df_right is None:
                st.info("Upload Right CSV files to see matching records.")
    else:
        st.error(f"❌ Left File Error: {err_l}")

# --- 3. Consolidation & Trending ---
st.divider()
st.header("📊 3. Trend Consolidation")
trend_files = st.file_uploader("Upload Daily Reports", accept_multiple_files=True, type="csv", key="trend_uploader")

if trend_files:
    all_reports, failed_files = process_trend_reports(trend_files)
    if failed_files:
        st.warning("⚠️ The following files were skipped:")
        st.dataframe(pd.DataFrame(failed_files), hide_index=True)
            
    if all_reports:
        full_df = pd.concat(all_reports)
        full_df['DT'] = pd.to_datetime(full_df['Time'], format='%Y%m%d %H%M%S', errors='coerce')
        full_df.loc[full_df['DT'].isna(), 'DT'] = pd.to_datetime(full_df.loc[full_df['DT'].isna(), 'Time'], errors='coerce')
        valid_df = full_df.dropna(subset=['DT']).copy()
        
        if not valid_df.empty:
            valid_df['Business_Date'] = (valid_df['DT'] - pd.Timedelta(hours=7)).dt.normalize()
            trend_suffix = get_trend_suffix(valid_df)
            
            # --- Chart 1: Daily Matching ---
            st.subheader("1. Daily Matching vs Missing (%)")
            daily_counts = valid_df.groupby(['Business_Date', 'Match_Status']).size().unstack(fill_value=0)
            for col in ['Matching', 'Missing', 'Update needed']:
                if col not in daily_counts.columns: daily_counts[col] = 0
            
            total = daily_counts['Matching'] + daily_counts['Missing'] + daily_counts['Update needed']
            chart_data = (daily_counts[['Missing', 'Update needed', 'Matching']].div(total, axis=0) * 100).reset_index()
            chart_data['Date_Label'] = chart_data['Business_Date'].dt.strftime('%b %d')
            chart_data = chart_data.melt(['Business_Date', 'Date_Label'], var_name='Status', value_name='Percentage')
            
            chart1 = alt.Chart(chart_data).mark_bar().encode(
                x=alt.X('Date_Label:O', sort=alt.EncodingSortField(field="Business_Date", op="min"), title='Date', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Percentage:Q', scale=alt.Scale(domain=[0, 100])),
                color=alt.Color('Status', scale=alt.Scale(domain=['Missing', 'Update needed', 'Matching'], range=['#FF7601', '#FCB53B', '#00809D'])),
                tooltip=['Date_Label', 'Status', alt.Tooltip('Percentage', format='.1f')]
            ).properties(height=350)
            chart1["usermeta"] = {"embedOptions": {"downloadFileName": f"Trend_{trend_suffix}"}}
            st.altair_chart(chart1, use_container_width=True)
            
            # --- Chart 2: Reasons Analysis ---
            if 'Reason' in valid_df.columns:
                st.divider()
                st.subheader("2. Missing Reasons Analysis")
                missing_df = valid_df[valid_df['Match_Status'].isin(['Missing', 'Update needed'])].copy()
                # Identify all possible dates across the entire dataset to show empty columns
                all_dates = sorted(valid_df['Business_Date'].unique())
                if not missing_df.empty:
                    # Clean and normalize Reasons
                    missing_df['Reason'] = missing_df['Reason'].fillna("Unknown").astype(str).str.strip().str.capitalize().replace({'Nan': 'Unknown', 'None': 'Unknown', '': 'Unknown'})
                    unique_reasons = sorted(missing_df['Reason'].unique().tolist())
                else:
                    unique_reasons = ["No Missing Items"]

                # Create a complete grid of Date x Reason using MultiIndex
                full_index = pd.MultiIndex.from_product([all_dates, unique_reasons], names=['Business_Date', 'Reason'])
                reason_counts = pd.DataFrame(index=full_index).reset_index()

                # Merge with actual counts if they exist; otherwise initialize 'Count' to 0
                if not missing_df.empty:
                    actual_counts = missing_df.groupby(['Business_Date', 'Reason']).size().reset_index(name='Count')
                    reason_counts = pd.merge(reason_counts, actual_counts, on=['Business_Date', 'Reason'], how='left')
                else:
                    # Fix for KeyError: 'Count' when no data is missing
                    reason_counts['Count'] = 0
                
                # Safely fill missing combinations (or existing 0s)
                reason_counts['Count'] = reason_counts['Count'].fillna(0)
                reason_counts['Date_Label'] = reason_counts['Business_Date'].dt.strftime('%b %d')
                
                # Generate chart with restored red/pink color logic from logic.py
                chart2 = alt.Chart(reason_counts).mark_bar().encode(
                    x=alt.X('Date_Label:O', sort=alt.EncodingSortField(field="Business_Date", op="min"), title='Date', axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('Count:Q'),
                    color=alt.Color('Reason', title='Reason', scale=alt.Scale(domain=unique_reasons, range=get_reason_colors(unique_reasons))), 
                    tooltip=['Date_Label', 'Reason', 'Count']
                ).properties(height=400)
                
                chart2["usermeta"] = {"embedOptions": {"downloadFileName": f"MissingReasons_trend_{trend_suffix}"}}
                st.altair_chart(chart2, use_container_width=True)
            # --- CHART 3: APC PERFORMANCE ---
            if 'Reason' in valid_df.columns:
                st.divider()
                st.subheader("3. APC Performance Analysis")
                st.info("Percentage of 'Time is more accurate in APC'")
                perf_data = get_apc_performance_data(valid_df)
                if not perf_data.empty:
                    chart3 = alt.Chart(perf_data).mark_bar().encode(
                        x=alt.X('Date_Label:O', 
                                sort=alt.EncodingSortField(field="Business_Date", op="min"), 
								title='Date'),
						y=alt.Y('Performance %:Q', 
								scale=alt.Scale(domain=[0, 100]), 
								title='Accurate Time Percentage (%)'),
                            tooltip=['Date_Label', alt.Tooltip('Performance %', format='.1f'), 'Total_Matching']
                        ).properties(height=350)
                    chart3["usermeta"] = {
						"embedOptions": {
							"downloadFileName": f"APC_Performance_{trend_suffix}"
						}
					}
                    st.altair_chart(chart3, use_container_width=True)
                    with st.expander("View Performance Details"):
                        st.dataframe(perf_data[['Business_Date', 'Total_Matching', 'Accurate_Time_Count', 'Performance %']], hide_index=True)
                else:
                    st.info("No 'Matching' status records found to calculate performance.")
            else:
                st.warning("⚠️ No 'Reason' column found to analyze APC performance.")
            
            # --- 4. Weekly Report & Trend Section ---
            st.divider()
            st.header("📋 4. Weekly Report & Trend Analysis")
            
            # Create a 2-column layout for the Weekly section
            wk_col1, wk_col2 = st.columns([1,3])

            with wk_col1:
                st.subheader("Current Week Summary")
                st.write("Overall summary based on current uploaded daily reports.")
                
                # 1. Calculation logic (Same as before)
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
                except:
                    date_range_label = "Overall"

                # 2. Create Summary DataFrame for Export
                summary_df = pd.DataFrame({
                    'Time': [date_range_label, date_range_label, date_range_label],
                    'Match_Status': ['Matching', 'Update needed', 'Missing'],
                    'Percentage': [round(m_rate, 1), round(u_rate, 1), round(ms_rate, 1)],
                    'Count': [m_count, u_count, ms_count]
                })
                
                st.info(f"Period: **{date_range_label}** | Total Cases: **{total_cases}**")
                
                st.download_button(
                    label="📥 Export Weekly Summary (CSV)",
                    data=summary_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"weekly_summary_{date_range_label}.csv",
                    mime="text/csv"
                )
                
                # Single Bar Chart for current week
                chart_data_curr = pd.DataFrame({'Category': ['Current Week'], 'Matching Rate': [m_rate]})
                curr_bar = alt.Chart(chart_data_curr).mark_bar(size=60, color='#00809D').encode(
                    x=alt.X('Category:N', title=None),
                    y=alt.Y('Matching Rate:Q', scale=alt.Scale(domain=[0, 100]), title='Matching %'),
                    tooltip=[alt.Tooltip('Matching Rate', format='.1f')]
                ).properties(height=300)
                
                st.altair_chart(curr_bar + curr_bar.mark_text(dy=-5, fontWeight='bold').encode(text=alt.Text('Matching Rate:Q', format='.1f')), use_container_width=True)

            with wk_col2:
                st.subheader("Weekly Historical Trend")                
                # 3. Reading in exported weekly summary files
                weekly_trend_files = st.file_uploader("Upload Weekly Summaries to get weekly trend", accept_multiple_files=True, type="csv", key="wk_trend_uploader")
                
                if weekly_trend_files:
                    all_wk_data = []
                    for f in weekly_trend_files:
                        try:
                            df_wk = pd.read_csv(f)
                            # Ensure required columns exist
                            if all(col in df_wk.columns for col in ['Time', 'Match_Status', 'Percentage']):
                                all_wk_data.append(df_wk)
                        except Exception as e:
                            st.error(f"Error loading {f.name}: {e}")
                    
                    if all_wk_data:
                        combined_wk_df = pd.concat(all_wk_data, ignore_index=True)
                        combined_wk_df = combined_wk_df.sort_values('Time', ascending=True)
                        # Create the Weekly Trend Chart (Similar to Daily Trend)
                        # We treat 'Time' as an ordinal category since it's a string range (e.g. 0203-0207)
                        wk_trend_chart = alt.Chart(combined_wk_df).mark_bar().encode(
                            x=alt.X('Time:O', title='Week Range', sort=None), 
                            y=alt.Y('Percentage:Q', scale=alt.Scale(domain=[0, 100]), title='Percentage (%)'),
                            color=alt.Color('Match_Status:N', 
                                           scale=alt.Scale(domain=['Missing', 'Update needed', 'Matching'], 
                                                         range=['#FF7601', '#FCB53B', '#00809D']),
                                           title='Status'),
                            tooltip=['Time', 'Match_Status', alt.Tooltip('Percentage', format='.1f'), 'Count']
                        ).properties(height=350)
                        wk_trend_chart["usermeta"] = {"embedOptions": {"downloadFileName": f"Weekly_trend"}}
                        st.altair_chart(wk_trend_chart, use_container_width=True)
                    else:
                        st.info("Upload valid weekly summary CSVs to generate the trend chart.")
                else:
                    st.info("👈 Upload previously exported weekly files here.")
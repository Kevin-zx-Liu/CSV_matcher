import streamlit as st
import pandas as pd
import altair as alt
from utils import robust_scan
from logic import apply_matching_logic, get_export_filename, process_trend_reports, get_reason_colors, get_trend_suffix

st.set_page_config(layout="wide", page_title="CSV Matcher")
st.title("🛡️ APC Validation")
st.markdown("Left File: **Temptation data** | Right File: **APC data**")

col1, col2 = st.columns(2)
with col1:
    left_file = st.file_uploader("Upload Left CSV (Hold Data)", type="csv")
with col2:
    right_file = st.file_uploader("Upload Right CSV (Process Data)", type="csv")

if left_file and right_file:
    left_targets = {'ID': ['LOT_ID', 'LOTID'], 'Time': ['LOT_HOLD_TIME', 'TIME'], 'Info': ['LOT_HOLD_COMMENT']}
    right_targets = {
        'ID': ['LOTID', 'LOT_ID', 'BATCHID'], 'Chart': ['CHARTNAME', 'CHART'],
        'Time': ['DATETIME', 'TIME'], 'Equipment': ['EQPNAME', 'EQUIPMENT'], 'Eventlist': ['EVENTLIST', 'EVENT_LIST']
    }

    df_left, err_l = robust_scan(left_file, "Left", left_targets)
    df_right, err_r = robust_scan(right_file, "Right", right_targets)

    if df_left is None:
        st.error(f"❌ Left File Error: {err_l}")
    elif df_right is None:
        st.error(f"❌ Right File Error: {err_r}")
    else:
        st.success(f"✅ Loaded: {len(df_left)} rows (Left) vs {len(df_right)} rows (Right)")
        df_left, df_right = apply_matching_logic(df_left, df_right)

        c1, c2 = st.columns([1, 1])
        with c1:
            st.subheader("1. Temptation Data")
            df_export = df_left.copy()
            df_export['Match_Status'] = df_export['Found_in_Right'].apply(lambda x: "Matching" if x else "Missing")
            export_filename = get_export_filename(df_export)
            st.download_button(label=f"📥 Export Report ({export_filename})", data=df_export[['Match_Status', 'ID', 'Time', 'Info']].to_csv(index=False).encode('utf-8'), file_name=export_filename, mime="text/csv")
            selection = st.dataframe(df_left[['Found_in_Right','ID','Time', 'Info']], on_select="rerun", selection_mode="single-row", width=1000, hide_index=True,
                column_config={"Found_in_Right": st.column_config.CheckboxColumn("MatchFound", disabled=True), "Time": "Lothold Time"})

        with c2:
            st.subheader("2. APC Data")
            if selection.selection["rows"]:
                idx = selection.selection["rows"][0]
                sel_key, sel_display = df_left.iloc[idx]['__key'], df_left.iloc[idx]['ID']
                st.info(f"Searching Process Data for: **{sel_display}**")
                match = df_right[df_right['Eventlist'].astype(str).str.contains(sel_display, case=False, regex=False)] if '.' in sel_display and 'Eventlist' in df_right.columns else df_right[df_right['__key'] == sel_key]
                if not match.empty:
                    cols_to_show = ['ID', 'Chart', 'Time', 'Equipment']
                    if 'Eventlist' in match.columns and '.' in sel_display: cols_to_show.append('Eventlist')
                    st.dataframe(match[[c for c in cols_to_show if c in match.columns]], width='stretch', hide_index=True)
                else: st.warning("❌ No record found in Right file.")

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
                if not missing_df.empty:
                    missing_df['Reason'] = missing_df['Reason'].fillna("Unknown").astype(str).str.strip().str.capitalize().replace({'Nan': 'Unknown', 'None': 'Unknown', '': 'Unknown'})
                    reason_counts = missing_df.groupby(['Business_Date', 'Reason']).size().reset_index(name='Count')
                    reason_counts['Date_Label'] = reason_counts['Business_Date'].dt.strftime('%b %d')
                    unique_reasons = sorted(reason_counts['Reason'].unique().tolist())
                    
                    chart2 = alt.Chart(reason_counts).mark_bar().encode(
                        x=alt.X('Date_Label:O', sort=alt.EncodingSortField(field="Business_Date", op="min"), title='Date', axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('Count:Q'),
                        color=alt.Color('Reason', title='Reason', scale=alt.Scale(domain=unique_reasons, range=get_reason_colors(unique_reasons))), 
                        tooltip=['Date_Label', 'Reason', 'Count']
                    ).properties(height=400)
                    chart2["usermeta"] = {"embedOptions": {"downloadFileName": f"MissingReasons_trend_{trend_suffix}"}}
                    st.altair_chart(chart2, use_container_width=True)	
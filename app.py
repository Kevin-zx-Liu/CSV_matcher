import streamlit as st
import pandas as pd
import io
import altair as alt

st.set_page_config(layout="wide", page_title="CSV Matcher")
st.title("🛡️ APC Validation")
st.markdown("Left File: **Temptation data** | Right File: **APC data**")

# --- 1. Universal Manual Scanner ---
def robust_scan(file, file_label, target_cols):
    """
    Scans a file line-by-line looking for specific column headers.
    """
    file.seek(0)
    lines = []
    for line in file.readlines():
        if isinstance(line, bytes):
            lines.append(line.decode('latin1', errors='ignore'))
        else:
            lines.append(line)
            
    # A. Detect Header Row & Column Indices
    header_index = -1
    col_indices = {key: -1 for key in target_cols} 
    found_header = False
    
    # Scan first 50 lines to find a header row that contains our main ID
    for i, line in enumerate(lines[:50]):
        parts = [p.strip().upper() for p in line.split(',')]
        
        # Check if this line contains at least the 'ID' column
        has_id = any(term in part for part in parts for term in target_cols['ID'])
        
        if has_id:
            header_index = i
            found_header = True
            
            # Map columns
            for idx, part in enumerate(parts):
                for key, search_terms in target_cols.items():
                    if col_indices[key] == -1:
                        if any(term in part for term in search_terms):
                            col_indices[key] = idx
            break
            
    if not found_header:
        return None, f"Could not find a Header row containing 'LOT' in {file_label} file."

    # B. Extract Data
    data = []
    for line in lines[header_index+1:]:
        parts = line.split(',')
        max_idx = max(col_indices.values())
        
        if len(parts) > max_idx:
            row_data = {}
            for key, idx in col_indices.items():
                if idx != -1:
                    val = parts[idx].strip().replace('"', '').replace("'", "")
                    row_data[key] = val
                else:
                    row_data[key] = "N/A"
            data.append(row_data)

    return pd.DataFrame(data), None

# --- 2. Main Application ---
col1, col2 = st.columns(2)
with col1:
    left_file = st.file_uploader("Upload Left CSV (Hold Data)", type="csv")
with col2:
    right_file = st.file_uploader("Upload Right CSV (Process Data)", type="csv")

if left_file and right_file:
    
    # --- CONFIGURATION ---
    
    # Left File targets: ID, Hold Time, Hold comment
    left_targets = {
        'ID':   ['LOT_ID', 'LOTID'],
        'Time': ['LOT_HOLD_TIME', 'TIME'], 
        'Comment': ['LOT_HOLD_COMMENT']
    }

    # Right File targets: ID, Chart, DateTime, Equipment
    right_targets = {
        'ID':        ['LOTID', 'LOT_ID', 'BATCHID'], 
        'Chart':     ['CHARTNAME', 'CHART'],
        'Time':      ['DATETIME', 'TIME'],
        'Equipment': ['EQPNAME', 'EQP', 'EQUIPMENT']
    }

    # --- EXECUTION ---
    df_left, err_l = robust_scan(left_file, "Left", left_targets)
    df_right, err_r = robust_scan(right_file, "Right", right_targets)

    if df_left is None:
        st.error(f"❌ Left File Error: {err_l}")
    elif df_right is None:
        st.error(f"❌ Right File Error: {err_r}")
    else:
        st.success(f"✅ Loaded: {len(df_left)} rows (Left) vs {len(df_right)} rows (Right)")

        # --- MATCHING LOGIC ---
        
        # Normalize Keys
        df_left['__key'] = df_left['ID'].astype(str).str.upper().str.strip()
        df_right['__key'] = df_right['ID'].astype(str).str.upper().str.strip()
        
        # Check Matches (Does Left exist in Right?)
        df_left['Found_in_Right'] = df_left['__key'].isin(df_right['__key'])

        # --- INTERFACE ---
        c1, c2 = st.columns([1, 1])

        with c1:
            st.subheader("1. Temptation Data")
            
            # --- [NEW] EXPORT LOGIC ---
            # 1. Create a clean copy for export
            df_export = df_left.copy()
            
            # 2. Add the status column based on the boolean match
            df_export['Match_Status'] = df_export['Found_in_Right'].apply(lambda x: "Matching" if x else "Missing")
            
            # 3. Select and Reorder columns (Status first, then data)
            export_cols = ['Match_Status', 'ID', 'Time', 'Comment']
            
            # 4. Convert to CSV
            csv_data = df_export[export_cols].to_csv(index=False).encode('utf-8')
            
            # 5. Display Button
            st.download_button(
                label="📥 Export Report (csv)",
                data=csv_data,
                file_name="matching_report.csv",
                mime="text/csv",
                help="Download left table with 'Matching' or 'Missing' status."
            )
            # --------------------------

            # Display ID, Time, and Comment
            display_cols = ['Found_in_Right','ID','Time', 'Comment']
            
            selection = st.dataframe(
                df_left[display_cols],
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
            st.subheader("2. APC Data")
            
            if selection.selection["rows"]:
                idx = selection.selection["rows"][0]
                
                sel_key = df_left.iloc[idx]['__key']
                sel_display = df_left.iloc[idx]['ID']
                
                st.info(f"Searching Process Data for: **{sel_display}**")
                
                # Find matching row in Right DF
                match = df_right[df_right['__key'] == sel_key]
                
                if not match.empty:
                    st.success("✅ Match Found")
                    # Display Chart, Time, Equipment
                    st.dataframe(
                        match[['ID', 'Chart', 'Time', 'Equipment']], 
                        width='stretch', 
                        hide_index=True,
                        column_config={"Time": "Process Time"}
                    )
                else:
                    st.warning("❌ No record found in Right file.")
            else:
                st.info("👈 Select a Hold Record on the left.")

# --- 3. Consolidation & Trending ---
st.divider()
st.header("📊 3. Trend Consolidation")
st.write("Upload multiple exported 'Matching Report' files to see the daily trend.")

trend_files = st.file_uploader("Upload Daily Reports", accept_multiple_files=True, type="csv", key="trend_uploader")

if trend_files:
    all_reports = []
    
    # 1. Read and combine files
    for file in trend_files:
        try:
            df_temp = pd.read_csv(file)
            all_reports.append(df_temp)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")
            
    if all_reports:
        full_df = pd.concat(all_reports)
        
        # Check required columns
        required_cols = ['Match_Status', 'Time']
        if all(col in full_df.columns for col in required_cols):
            
            # 2. Parse Dates (Handle Parsing Errors)
            full_df['DT'] = pd.to_datetime(
                full_df['Time'], 
                format='%Y%m%d %H%M%S', 
                errors='coerce'
            )
            # Fallback for other formats
            mask_fail = full_df['DT'].isna()
            if mask_fail.any():
                full_df.loc[mask_fail, 'DT'] = pd.to_datetime(full_df.loc[mask_fail, 'Time'], errors='coerce')

            # Filter valid dates
            valid_df = full_df.dropna(subset=['DT']).copy()
            
            if not valid_df.empty:
                # 3. Apply Business Day Logic (7AM to 7AM)
                valid_df['Adjusted_DT'] = valid_df['DT'] - pd.Timedelta(hours=7)
                valid_df['Business_Date'] = valid_df['Adjusted_DT'].dt.normalize()
                
                # 4. Group by Business Date and Status
                daily_counts = valid_df.groupby(['Business_Date', 'Match_Status']).size().unstack(fill_value=0)
                
                # Ensure columns exist
                if 'Matching' not in daily_counts.columns: daily_counts['Matching'] = 0
                if 'Missing' not in daily_counts.columns: daily_counts['Missing'] = 0
                
                # Calculate Totals and Percentages
                daily_counts['Total'] = daily_counts['Matching'] + daily_counts['Missing']
                daily_counts['Matching %'] = (daily_counts['Matching'] / daily_counts['Total']) * 100
                daily_counts['Missing %'] = (daily_counts['Missing'] / daily_counts['Total']) * 100
                
                # 5. Visualization
                st.subheader("Daily Matching vs Missing (%)")
                
                # Prepare data
                chart_data = daily_counts[['Matching %', 'Missing %']].reset_index()
                
                # [NEW] Create a string label for the axis (e.g. "Jan 08")
                # This ensures the chart treats them as text categories, not a timeline
                chart_data['Date_Label'] = chart_data['Business_Date'].dt.strftime('%b %d')
                
                chart_data = chart_data.melt(['Business_Date', 'Date_Label'], var_name='Status', value_name='Percentage')
                
                # Create Stacked Bar Chart
                chart = alt.Chart(chart_data).mark_bar().encode(
                    # Use the String Label as Ordinal (:O)
                    # We sort by 'Business_Date' so Jan 05 comes before Jan 06 correctly
                    x=alt.X('Date_Label:O', 
                            sort=alt.EncodingSortField(field="Business_Date", order="ascending"),
                            title='Date',
                            axis=alt.Axis(labelAngle=0)), 
                    y=alt.Y('Percentage:Q', scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color('Status', scale=alt.Scale(domain=['Missing %', 'Matching %'], range=['#dc3545', '#28a745'])),
                    tooltip=[
                        alt.Tooltip('Date_Label', title='Date'), 
                        'Status', 
                        alt.Tooltip('Percentage', format='.1f')
                    ]
                ).properties(height=400)
                
                st.altair_chart(chart, use_container_width=True)
                
                # Show source data table
                with st.expander("View Data Source"):
                    display_table = daily_counts.copy()
                    display_table.index = display_table.index.strftime('%Y-%m-%d')
                    st.dataframe(display_table.sort_index())
                    
            else:
                st.warning("Could not parse dates. Please ensure the Time format is 'YYYYMMDD HHMMSS'.")
        else:
            st.error(f"Uploaded files are missing required columns: {required_cols}")
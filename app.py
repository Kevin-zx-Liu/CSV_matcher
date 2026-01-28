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
    Auto-detects whether the separator is a comma (,) or semicolon (;).
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
    delimiter = ',' # Default fallback
    
    # Scan first 50 lines to find a header row that contains our main ID
    for i, line in enumerate(lines[:50]):
        clean_line = line.strip()
        if not clean_line: continue
        
        # --- Improved Delimiter Detection ---
        # 1. Split by Comma
        parts_comma = [p.strip().upper() for p in clean_line.split(',')]
        # It is only a valid split if we have more than 1 column
        valid_comma = len(parts_comma) > 1 and any(term in part for part in parts_comma for term in target_cols['ID'])
        
        # 2. Split by Semicolon
        parts_semi = [p.strip().upper() for p in clean_line.split(';')]
        valid_semi = len(parts_semi) > 1 and any(term in part for part in parts_semi for term in target_cols['ID'])
        
        parts = []
        if valid_semi:
            delimiter = ';'
            parts = parts_semi
            found_header = True
        elif valid_comma:
            delimiter = ','
            parts = parts_comma
            found_header = True
            
        if found_header:
            header_index = i
            
            # Map columns using the detected parts
            for idx, part in enumerate(parts):
                for key, search_terms in target_cols.items():
                    if col_indices[key] == -1:
                        if any(term in part for term in search_terms):
                            col_indices[key] = idx
            break
            
    if not found_header:
        return None, f"Could not find a Header row containing 'LOT' (or delimiters were not detected) in {file_label} file."

    # B. Extract Data
    data = []
    for line in lines[header_index+1:]:
        parts = line.split(delimiter)
        if len(parts) < 2: continue

        row_data = {}
        max_needed = max(col_indices.values())
        
        if len(parts) > max_needed:
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
    left_targets = {
        'ID':   ['LOT_ID', 'LOTID'],
        'Time': ['LOT_HOLD_TIME', 'TIME'], 
        'Info': ['LOT_HOLD_COMMENT']
    }

    right_targets = {
        'ID':        ['LOTID', 'LOT_ID', 'BATCHID'], 
        'Chart':     ['CHARTNAME', 'CHART'],
        'Time':      ['DATETIME', 'TIME'],
        'Equipment': ['EQPNAME', 'EQUIPMENT'],
        'Eventlist': ['EVENTLIST', 'EVENT_LIST']
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

        # =========================================================
        # --- GLOBAL MATCHING LOGIC (Applied to whole table) ---
        # =========================================================
        
        # 1. Standard Normalization
        df_left['__key'] = df_left['ID'].astype(str).str.upper().str.strip()
        df_right['__key'] = df_right['ID'].astype(str).str.upper().str.strip()
        
        # 2. Initial Exact Match Check
        df_left['Found_in_Right'] = df_left['__key'].isin(df_right['__key'])

        # 3. --- SPECIAL DOT RULE ---
        # Identify rows that are currently MISSING and have a DOT in the ID
        mask_special = (~df_left['Found_in_Right']) & (df_left['ID'].astype(str).str.contains('.', regex=False))
        
        # Only run this if we have special cases AND the right file has an Eventlist
        if mask_special.any() and 'Eventlist' in df_right.columns:
            st.toast(f"ℹ️ detected {mask_special.sum()} complex IDs with dots. Scanning Eventlists...")
            
            # Prepare right side column for faster searching
            right_eventlist_series = df_right['Eventlist'].astype(str)
            
            # Iterate through the special rows (usually few) to update status
            for idx in df_left[mask_special].index:
                search_val = df_left.at[idx, 'ID']
                
                # Check if search_val exists as a substring in ANY row of Eventlist
                # regex=False treats '.' as a literal dot, case=False ignores case
                is_found = right_eventlist_series.str.contains(search_val, case=False, regex=False).any()
                
                if is_found:
                    df_left.at[idx, 'Found_in_Right'] = True
        # =========================================================

    # --- INTERFACE ---
        c1, c2 = st.columns([1, 1])

        with c1:
            st.subheader("1. Temptation Data")
            
            # --- EXPORT LOGIC ---
            df_export = df_left.copy()
            df_export['Match_Status'] = df_export['Found_in_Right'].apply(lambda x: "Matching" if x else "Missing")
            
            # --- [NEW] DYNAMIC FILENAME GENERATION ---
            # Default filename
            export_filename = "matching_report.csv"
            
            try:
                # 1. Parse dates (Handle formats)
                temp_dates = pd.to_datetime(df_export['Time'], format='%Y%m%d %H%M%S', errors='coerce')
                # Fallback for other formats if mostly NaT
                if temp_dates.isna().sum() > (len(temp_dates) * 0.5): 
                     temp_dates = pd.to_datetime(df_export['Time'], errors='coerce')
                
                # 2. Subtract 7 hours to get "Business Date"
                # (Jan 2 08:00 -> Jan 2 | Jan 3 06:00 -> Jan 2)
                business_dates = temp_dates - pd.Timedelta(hours=7)
                
                # 3. Find the most common date (mode) to name the file
                if not business_dates.dropna().empty:
                    top_date = business_dates.mode()[0]
                    date_suffix = top_date.strftime('%m%d') # Format MMDD (e.g. 0102)
                    export_filename = f"matching_report_{date_suffix}.csv"
            except Exception as e:
                print(f"Date parsing failed for filename generation: {e}")
            # ----------------------------------------
            
            export_cols = ['Match_Status', 'ID', 'Time', 'Info']
            csv_data = df_export[export_cols].to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label=f"📥 Export Report ({export_filename})",
                data=csv_data,
                file_name=export_filename,
                mime="text/csv",
                help="Download left table with 'Matching' or 'Missing' status."
            )
            # --------------------------

            display_cols = ['Found_in_Right','ID','Time', 'Info']
            
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
                
                # --- INTERACTIVE SEARCH DISPLAY ---
                # Determine HOW to find the record to display based on the ID structure
                
                if '.' in sel_display and 'Eventlist' in df_right.columns:
                    # Special Display Logic: Search in Eventlist
                    match = df_right[df_right['Eventlist'].astype(str).str.contains(sel_display, case=False, regex=False)]
                    if not match.empty:
                         st.caption("✅ Matched via Eventlist Search")
                else:
                    # Standard Display Logic: Exact Match
                    match = df_right[df_right['__key'] == sel_key]
                
                if not match.empty:
                    cols_to_show = ['ID', 'Chart', 'Time', 'Equipment']
                    if 'Eventlist' in match.columns and '.' in sel_display:
                        cols_to_show.append('Eventlist')
                        
                    final_cols = [c for c in cols_to_show if c in match.columns]

                    st.dataframe(
                        match[final_cols], 
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
    failed_files = []  # [NEW] Track files that fail to load
    
    # 1. Read and combine files (Robust to Separators)
    for file in trend_files:
        try:
            df_temp = pd.read_csv(file, sep=None, engine='python')

            has_match_col = 'Match_Status' in df_temp.columns
            has_time_col = ('Time' in df_temp.columns) or ('LOT_HOLD_TIME' in df_temp.columns)
            
            if not has_match_col or not has_time_col:
                file.seek(0)
                df_temp = pd.read_csv(file, sep=';')

            # 1. Clean whitespaces in column names
            df_temp.columns = df_temp.columns.str.strip()
            
            # 2. Rename dictionary (Handles variations in headers)
            rename_map = {
                'NEW COMMENT': 'Reason',
                'New_Comments': 'Reason',
                'new comments': 'Reason',
                'New Comments': 'Reason',
                'new comment'   : 'Reason',
                'new_comment'   : 'Reason',
                'new_comments'  : 'Reason',
                'COMMENT'       : 'Match_Status',
                'comment'       : 'Match_Status',
                'Comments': 'Match_Status',
                'LOT_HOLD_TIME': 'Time'
            }
            df_temp.rename(columns=rename_map, inplace=True)
            
            # Check for required columns immediately
            required_check = ['Match_Status','Time']
            missing_cols = [c for c in required_check if c not in df_temp.columns]
            
            if missing_cols:
                failed_files.append({'File': file.name, 'Reason': f"Missing columns: {missing_cols}, get columns: {df_temp.columns.tolist()}"})
                continue  # Skip this file
          
            if 'Match_Status' in df_temp.columns:
                df_temp['Match_Status'] = df_temp['Match_Status'].astype(str).str.title().str.strip()

                # Explicit override just to be 100% sure
                df_temp['Match_Status'] = df_temp['Match_Status'].replace({
                    'Update Needed': 'Update needed',
                    'Matching': 'Matching',
                    'Missing': 'Missing'
                })
            all_reports.append(df_temp)
        except Exception as e:
            # [MODIFIED] Log error to table instead of just printing
            failed_files.append({'File': file.name, 'Reason': str(e)})
            
    # Display the status of skipped files
    if failed_files:
        st.warning("⚠️ The following files were skipped:")
        st.dataframe(pd.DataFrame(failed_files), hide_index=True)
            
    if all_reports:
        full_df = pd.concat(all_reports)
        required_cols = ['Match_Status', 'Time']
        
        if all(col in full_df.columns for col in required_cols):
              
            # --- DATE PARSING ---
            full_df['DT'] = pd.to_datetime(
                full_df['Time'], 
                format='%Y%m%d %H%M%S', 
                errors='coerce'
            )
            mask_fail = full_df['DT'].isna()
            if mask_fail.any():
                full_df.loc[mask_fail, 'DT'] = pd.to_datetime(full_df.loc[mask_fail, 'Time'], errors='coerce')

            valid_df = full_df.dropna(subset=['DT']).copy()
            
            if not valid_df.empty:
                # --- BUSINESS LOGIC ---
                valid_df['Adjusted_DT'] = valid_df['DT'] - pd.Timedelta(hours=7)
                valid_df['Business_Date'] = valid_df['Adjusted_DT'].dt.normalize()
                
                # --- CHART 1: MATCHING VS MISSING ---
                st.subheader("1. Daily Matching vs Missing (%)")
                
                daily_counts = valid_df.groupby(['Business_Date', 'Match_Status']).size().unstack(fill_value=0)
                if 'Matching' not in daily_counts.columns: daily_counts['Matching'] = 0
                if 'Missing' not in daily_counts.columns: daily_counts['Missing'] = 0
                if 'Update needed' not in daily_counts.columns: daily_counts['Update needed'] = 0

                daily_counts['Total'] = daily_counts['Matching'] + daily_counts['Missing'] + daily_counts['Update needed']
                daily_counts['Matching %'] = (daily_counts['Matching'] / daily_counts['Total']) * 100
                daily_counts['Missing %'] = (daily_counts['Missing'] / daily_counts['Total']) * 100
                daily_counts['Update needed %'] = (daily_counts['Update needed'] / daily_counts['Total']) * 100

                chart_data = daily_counts[['Missing %', 'Update needed %', 'Matching %']].reset_index()
                chart_data['Date_Label'] = chart_data['Business_Date'].dt.strftime('%b %d')
                chart_data = chart_data.melt(['Business_Date', 'Date_Label'], var_name='Status', value_name='Percentage')
                
                chart1 = alt.Chart(chart_data).mark_bar().encode(
                    x=alt.X('Date_Label:O', 
                            sort=alt.EncodingSortField(field="Business_Date", op="min", order="ascending"), 
                            title='Date', 
                            axis=alt.Axis(labelAngle=0)), 
                    y=alt.Y('Percentage:Q', scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color('Status', scale=alt.Scale(domain=['Missing %', 'Update needed %','Matching %'], range=['#FF7601', '#FCB53B','#00809D'])),
                    tooltip=[alt.Tooltip('Date_Label', title='Date'), 'Status', alt.Tooltip('Percentage', format='.1f')]
                ).properties(height=350)
                
                st.altair_chart(chart1, use_container_width=True)
                
                export_df1 = daily_counts.copy()
                export_df1.index = export_df1.index.strftime('%Y-%m-%d')
                st.download_button("📥 Export Status Data (CSV)", export_df1.to_csv().encode('utf-8'), "trend_status.csv", "text/csv")
                
                # --- CHART 2: MISSING REASONS TREND ---
                st.divider()
                st.subheader("2. Missing Reasons Analysis")
                
                if 'Reason' in valid_df.columns:
                    missing_df = valid_df[valid_df['Match_Status'].isin(['Missing', 'Update needed'])].copy()
                    if not missing_df.empty:
                        missing_df['Reason'] = missing_df['Reason'].fillna("Unknown")

                        # This converts "limit changed" -> "Limit changed" so duplicates merge
                        missing_df['Reason'] = missing_df['Reason'].astype(str).str.strip().str.capitalize()
                        
                        # Handle case where "Unknown" became "Unknown" correctly, but "nan" strings might need fixing
                        missing_df['Reason'] = missing_df['Reason'].replace({'Nan': 'Unknown', 'None': 'Unknown', '': 'Unknown'})
                        
                        reason_counts = missing_df.groupby(['Business_Date', 'Reason']).size().reset_index(name='Count')
                        reason_counts['Date_Label'] = reason_counts['Business_Date'].dt.strftime('%b %d')

                        unique_reasons = sorted(reason_counts['Reason'].unique().tolist())

                        # Create a color list that matches the order of 'unique_reasons'
                        color_range = []
                        # Palette for non-error items (Blue, Orange, Green, Purple, Brown, Pink, Gray, Yellow, Cyan)
                        safe_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
                        palette_idx = 0
                        
                        for r in unique_reasons:
                            r_lower = r.lower()
                            # 1. Check for explicit "Missing"
                            if r_lower == "missing":
                                color_range.append('#d62728') # Standard Red
                            # 2. Check for "Missing in APC..." (contains logic)
                            elif "missing in apc" in r_lower:
                                color_range.append('#ff9896') # Lighter Red / Pink
                            # 3. All other reasons -> Cycle through safe palette
                            else:
                                color_range.append(safe_palette[palette_idx % len(safe_palette)])
                                palette_idx += 1
                        
                        chart2 = alt.Chart(reason_counts).mark_bar().encode(
                            x=alt.X('Date_Label:O', 
                                    sort=alt.EncodingSortField(field="Business_Date", op="min", order="ascending"), 
                                    title='Date', 
                                    axis=alt.Axis(labelAngle=0)),
                            y=alt.Y('Count:Q', title='Count of Missing Items'),
                            color=alt.Color('Reason', title='Reason', scale=alt.Scale(domain=unique_reasons, range=color_range)),
                            tooltip=[alt.Tooltip('Date_Label', title='Date'), 'Reason', 'Count']
                        ).properties(height=400)
                        
                        st.altair_chart(chart2, use_container_width=True)
                        
                        with st.expander("View Reason Breakdown"):
                            pivot_reason = reason_counts.pivot(index='Business_Date', columns='Reason', values='Count').fillna(0)
                            pivot_reason.index = pivot_reason.index.strftime('%Y-%m-%d')
                            st.dataframe(pivot_reason)
                            
                            st.download_button(
                                "📥 Export Reason Data (CSV)", 
                                pivot_reason.to_csv().encode('utf-8'), 
                                "trend_reasons.csv", 
                                "text/csv"
                            )
                    else:
                        st.info("✅ No missing data found! (Or all missing items have no recorded reason).")
                else:
                    st.warning("⚠️ No 'Reason' (or 'New_Comments') column found in the uploaded files.")
                    
            else:
                st.warning("Could not parse dates. Please ensure the Time format is 'YYYYMMDD HHMMSS'.")
        else:
            st.error(f"Uploaded files are missing required columns: {required_cols}. Please check if the file uses standard headers. Found headers: {full_df.columns.tolist()}")
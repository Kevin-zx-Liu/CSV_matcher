import streamlit as st
import pandas as pd
import io
import altair as alt

st.set_page_config(layout="wide", page_title="CSV Matcher")
st.title("🛡️ APC Validation")
st.markdown("Left File: **Temptation data** | Right File: **APC data**")

# --- 1. Universal Manual Scanner (Fixed Delimiter Detection) ---
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
        # Clean the line
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
                        # Check exact match or substring match depending on your needs
                        # Using substring match as per original logic
                        if any(term in part for term in search_terms):
                            col_indices[key] = idx
            break
            
    if not found_header:
        return None, f"Could not find a Header row containing 'LOT' (or delimiters were not detected) in {file_label} file."

    # B. Extract Data
    data = []
    for line in lines[header_index+1:]:
        # Use the detected delimiter to split data rows
        parts = line.split(delimiter)
        
        # Basic check to ensure row isn't empty
        if len(parts) < 2: continue

        row_data = {}
        # Only extract if we have enough columns for the indices we found
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
    
    # Left File targets: ID, Hold Time, Hold comment
    left_targets = {
        'ID':   ['LOT_ID', 'LOTID'],
        'Time': ['LOT_HOLD_TIME', 'TIME'], 
        'Comment': ['LOT_HOLD_COMMENT']
    }

    # Right File targets: ID, Chart, DateTime, Equipment, [NEW] Eventlist
    right_targets = {
        'ID':        ['LOTID', 'LOT_ID', 'BATCHID'], 
        'Chart':     ['CHARTNAME', 'CHART'],
        'Time':      ['DATETIME', 'TIME'],
        'Equipment': ['EQPNAME', 'EQUIPMENT'],
        'Eventlist': ['EVENTLIST'] # Target column for special search
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
        # Note: This boolean check is purely based on ID match. 
        # If you want the "Special Dot Rule" to also affect the "Missing/Matching" status 
        # for the export, you would need to iterate row by row, which is slow.
        # For now, we keep the quick vector match for the general status, 
        # assuming the 'dot' IDs are rare edge cases or handled manually.
        df_left['Found_in_Right'] = df_left['__key'].isin(df_right['__key'])

        # --- INTERFACE ---
        c1, c2 = st.columns([1, 1])

        with c1:
            st.subheader("1. Temptation Data")
            
            # --- EXPORT LOGIC ---
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
                
                # --- [NEW] SPECIAL SEARCH RULE ---
                # Rule: If ID contains '.', search in 'Eventlist' column instead of 'ID'
                if '.' in sel_display:
                    st.caption("ℹ️ 'Dot' detected in ID. Switching search mode to 'Eventlist' column.")
                    
                    if 'Eventlist' in df_right.columns:
                        # Search for the ID inside the Eventlist string (case insensitive)
                        # We use regex=False to treat it as a literal string match
                        match = df_right[df_right['Eventlist'].astype(str).str.contains(sel_display, case=False, regex=False)]
                    else:
                        st.error("⚠️ 'Eventlist' column not found in Right File. Cannot perform special search.")
                        match = pd.DataFrame() # Empty result
                else:
                    # Standard Search (Exact ID Match)
                    match = df_right[df_right['__key'] == sel_key]
                # ---------------------------------
                
                if not match.empty:
                    st.success("✅ Match Found")
                    
                    # Determine columns to display (include Eventlist if it was a special search)
                    cols_to_show = ['ID', 'Chart', 'Time', 'Equipment']
                    if '.' in sel_display and 'Eventlist' in match.columns:
                        cols_to_show.append('Eventlist')
                        
                    # Filter columns that actually exist in the dataframe
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
    
    # 1. Read and combine files (Robust to Separators)
    for file in trend_files:
        try:
            # Attempt 1: Try reading with Python's 'sniffer'
            df_temp = pd.read_csv(file, sep=None, engine='python')
            
            # Validation: specific check for common issue where sniff fails
            if 'Match_Status' not in df_temp.columns or 'Time' not in df_temp.columns:
                file.seek(0)
                df_temp = pd.read_csv(file, sep=';')
            
            # --- [FIX] Normalize Column Names Immediately ---
            # If a file has "New_Comments", rename it to "Reason" right now.
            # This ensures all files match perfectly when we combine them.
            if 'New_Comments' in df_temp.columns:
                df_temp.rename(columns={'New_Comments': 'Reason'}, inplace=True)
            if 'Comments' in df_temp.columns:
                df_temp.rename(columns={'Comments': 'Match_Status'}, inplace=True)
            # -----------------------------------------------

            all_reports.append(df_temp)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")
            
    if all_reports:
        full_df = pd.concat(all_reports)
        
        # Check required columns
        required_cols = ['Match_Status', 'Time']
        
        if all(col in full_df.columns for col in required_cols):
            
            # --- DATE PARSING ---
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
                # --- BUSINESS LOGIC ---
                # Subtract 7 hours so 07:00 becomes 00:00 of the same day
                valid_df['Adjusted_DT'] = valid_df['DT'] - pd.Timedelta(hours=7)
                valid_df['Business_Date'] = valid_df['Adjusted_DT'].dt.normalize()
                
                # --- CHART 1: MATCHING VS MISSING ---
                st.subheader("1. Daily Matching vs Missing (%)")
                
                daily_counts = valid_df.groupby(['Business_Date', 'Match_Status']).size().unstack(fill_value=0)
                if 'Matching' not in daily_counts.columns: daily_counts['Matching'] = 0
                if 'Missing' not in daily_counts.columns: daily_counts['Missing'] = 0
                
                daily_counts['Total'] = daily_counts['Matching'] + daily_counts['Missing']
                daily_counts['Matching %'] = (daily_counts['Matching'] / daily_counts['Total']) * 100
                daily_counts['Missing %'] = (daily_counts['Missing'] / daily_counts['Total']) * 100
                
                # Prepare data
                chart_data = daily_counts[['Matching %', 'Missing %']].reset_index()
                chart_data['Date_Label'] = chart_data['Business_Date'].dt.strftime('%b %d')
                chart_data = chart_data.melt(['Business_Date', 'Date_Label'], var_name='Status', value_name='Percentage')
                
                chart1 = alt.Chart(chart_data).mark_bar().encode(
                    x=alt.X('Date_Label:O', 
                            sort=alt.EncodingSortField(field="Business_Date", op="min", order="ascending"), 
                            title='Date', 
                            axis=alt.Axis(labelAngle=0)), 
                    y=alt.Y('Percentage:Q', scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color('Status', scale=alt.Scale(domain=['Matching %', 'Missing %'], range=['#28a745', '#dc3545'])),
                    tooltip=[alt.Tooltip('Date_Label', title='Date'), 'Status', alt.Tooltip('Percentage', format='.1f')]
                ).properties(height=350)
                
                st.altair_chart(chart1, use_container_width=True)
                
                # Export Button 1
                export_df1 = daily_counts.copy()
                export_df1.index = export_df1.index.strftime('%Y-%m-%d')
                st.download_button("📥 Export Status Data (CSV)", export_df1.to_csv().encode('utf-8'), "trend_status.csv", "text/csv")
                
                # --- CHART 2: MISSING REASONS TREND ---
                st.divider()
                st.subheader("2. Missing Reasons Analysis")
                
                if 'Reason' in valid_df.columns:
                    # Filter only Missing rows
                    missing_df = valid_df[valid_df['Match_Status'] == 'Missing'].copy()
                    
                    if not missing_df.empty:
                        # Handle NaNs
                        missing_df['Reason'] = missing_df['Reason'].fillna("Unknown")
                        
                        # Group by Date and Reason
                        reason_counts = missing_df.groupby(['Business_Date', 'Reason']).size().reset_index(name='Count')
                        
                        # Add Date Label for sorting
                        reason_counts['Date_Label'] = reason_counts['Business_Date'].dt.strftime('%b %d')

                        # --- [FIX] Calculate Master List of Reasons ---
                        # We get every unique reason from the entire dataset and sort them.
                        # This 'unique_reasons' list is passed to the chart domain.
                        unique_reasons = sorted(reason_counts['Reason'].unique().tolist())
                        # ---------------------------------------------
                        
                        # Create Chart
                        chart2 = alt.Chart(reason_counts).mark_bar().encode(
                            x=alt.X('Date_Label:O', 
                                    sort=alt.EncodingSortField(field="Business_Date", op="min", order="ascending"), 
                                    title='Date', 
                                    axis=alt.Axis(labelAngle=0)),
                            y=alt.Y('Count:Q', title='Count of Missing Items'),
                            color=alt.Color('Reason', title='Reason', scale=alt.Scale(domain=unique_reasons,scheme='tableau10')),
                            tooltip=[alt.Tooltip('Date_Label', title='Date'), 'Reason', 'Count']
                        ).properties(height=400)
                        
                        st.altair_chart(chart2, use_container_width=True)
                        
                        # Data Table & Export
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
            st.error(f"Uploaded files are missing required columns: {required_cols}. Please check if the file uses standard headers.")
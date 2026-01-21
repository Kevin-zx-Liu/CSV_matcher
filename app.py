import streamlit as st
import pandas as pd
import io

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
    
    # --- UPDATED CONFIGURATION (SWAPPED) ---
    
    # Left File targets: ID, Hold Time, Hold Rule
    left_targets = {
        'ID':   ['LOT_ID', 'LOTID'],
        'Time': ['LOT_HOLD_TIME', 'HOLD_TIME', 'TIME'], 
        'Rule': ['LOT_HOLD_RULE', 'HOLD_RULE', 'RULE']
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
            # Display ID, Time, and Rule
            display_cols = ['ID', 'Found_in_Right', 'Time', 'Rule']
            
            selection = st.dataframe(
                df_left[display_cols],
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True,
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
                        use_container_width=True, 
                        hide_index=True,
                        column_config={"Time": "Process Time"}
                    )
                else:
                    st.warning("❌ No record found in Right file.")
            else:
                st.info("👈 Select a Hold Record on the left.")
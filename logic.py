import pandas as pd
import streamlit as st

def apply_matching_logic(df_left, df_right):
    """Performs LotID and Chart Name matching, including special ChildLot rules."""
    df_left['__key'] = df_left['ID'].astype(str).str.upper().str.strip()
    df_right['__key'] = df_right['ID'].astype(str).str.upper().str.strip()
    
    df_left['__chart_extracted'] = df_left['Info'].astype(str).str.extract(r'SMCchart\s+(.+?)\s+-\s+Lot', expand=False)
    df_left['__chart_clean'] = df_left['__chart_extracted'].fillna('').str.strip().str.upper()
    
    if 'Chart' in df_right.columns:
        df_right['__chart_clean'] = df_right['Chart'].astype(str).replace('nan', '').fillna('').str.strip().str.upper()
    else:
        df_right['__chart_clean'] = ""

    df_left['__composite_key'] = df_left['__key'] + "|" + df_left['__chart_clean']
    df_right['__composite_key'] = df_right['__key'] + "|" + df_right['__chart_clean']
    
    df_left['Found_in_Right'] = df_left['__composite_key'].isin(df_right['__composite_key'])

    mask_special = (~df_left['Found_in_Right']) & (df_left['ID'].astype(str).str.contains('.', regex=False))
    
    if mask_special.any() and 'Eventlist' in df_right.columns:
        st.toast(f"ℹ️ detected {mask_special.sum()} complex IDs with dots. Scanning Eventlists...")
        right_eventlist_series = df_right['Eventlist'].astype(str)
        
        for idx in df_left[mask_special].index:
            search_val = df_left.at[idx, 'ID']
            is_found = right_eventlist_series.str.contains(search_val, case=False, regex=False).any()
            if is_found:
                df_left.at[idx, 'Found_in_Right'] = True
                
    return df_left, df_right

def get_export_filename(df_export):
    """Generates a filename based on the business date found in the data."""
    export_filename = "matching_report.csv"
    try:
        temp_dates = pd.to_datetime(df_export['Time'], format='%Y%m%d %H%M%S', errors='coerce')
        if temp_dates.isna().sum() > (len(temp_dates) * 0.5): 
             temp_dates = pd.to_datetime(df_export['Time'], errors='coerce')
        
        business_dates = temp_dates - pd.Timedelta(hours=7) + pd.Timedelta(days=1)
        
        if not business_dates.dropna().empty:
            top_date = business_dates.mode()[0]
            date_suffix = top_date.strftime('%m%d')
            export_filename = f"matching_report_{date_suffix}.csv"
    except Exception as e:
        print(f"Date parsing failed for filename generation: {e}")
    return export_filename

def process_trend_reports(trend_files):
    """Consolidates multiple reports and prepares data for trending."""
    all_reports = []
    failed_files = []
    
    rename_map = {
        'NEW COMMENT': 'Reason', 'New_Comments': 'Reason', 'new comments': 'Reason',
        'New Comments': 'Reason', 'new comment': 'Reason', 'new_comment': 'Reason',
        'new_comments': 'Reason', 'COMMENT': 'Match_Status', 'comment': 'Match_Status',
        'Comments': 'Match_Status', 'LOT_HOLD_TIME': 'Time'
    }

    for file in trend_files:
        try:
            df_temp = pd.read_csv(file, sep=None, engine='python')
            if 'Match_Status' not in df_temp.columns or 'Time' not in df_temp.columns:
                file.seek(0)
                df_temp = pd.read_csv(file, sep=';')

            df_temp.columns = df_temp.columns.str.strip()
            df_temp.rename(columns=rename_map, inplace=True)
            
            required_check = ['Match_Status', 'Time']
            if not all(col in df_temp.columns for col in required_check):
                failed_files.append({'File': file.name, 'Reason': "Missing required columns"})
                continue
          
            df_temp['Match_Status'] = df_temp['Match_Status'].astype(str).str.title().str.strip()
            df_temp['Match_Status'] = df_temp['Match_Status'].replace({
                'Update Needed': 'Update needed', 'Matching': 'Matching', 'Missing': 'Missing'
            })
            all_reports.append(df_temp)
        except Exception as e:
            failed_files.append({'File': file.name, 'Reason': str(e)})
            
    return all_reports, failed_files

def get_trend_suffix(valid_df):
    """Generates the suffix used for trend chart export filenames."""
    try:
        start_date = valid_df['Business_Date'].min().strftime('%m%d')
        end_date = valid_df['Business_Date'].max().strftime('%m%d')
        return f"{start_date}_to_{end_date}"
    except:
        return "history"

def get_reason_colors(unique_reasons):
    """Generates the specific color mapping for missing reasons."""
    color_range = []
    safe_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    palette_idx = 0
    
    for r in unique_reasons:
        r_lower = r.lower()
        if r_lower == "missing":
            color_range.append('#d62728') 
        elif "missing in apc but present in trend" in r_lower:
            color_range.append('#ff9896') 
        else:
            color_range.append(safe_palette[palette_idx % len(safe_palette)])
            palette_idx += 1
    return color_range

def get_apc_performance_data(valid_df):
    # 1. Find all Matching data
    matching_df = valid_df[valid_df['Match_Status'] == 'Matching'].copy()
    
    if matching_df.empty:
        return pd.DataFrame()

    # 2. Find "more accurate in APC" from Reason
    target_reason = "Time is more accurate in APC"
    matching_df['is_accurate_time'] = matching_df['Reason'].astype(str).str.contains(
        "time is more accurate in APC", case=False, na=False
    )

    # 3. group by Business_Date and calculate counts for total Matching and accurate time cases
    perf_stats = matching_df.groupby('Business_Date').agg(
        Total_Matching=('Match_Status', 'count'),
        Accurate_Time_Count=('is_accurate_time', 'sum')
    ).reset_index()

    # 4. calculate performance percentage
    perf_stats['Performance %'] = (perf_stats['Accurate_Time_Count'] / perf_stats['Total_Matching']) * 100
    perf_stats['Date_Label'] = perf_stats['Business_Date'].dt.strftime('%b %d')
    
    return perf_stats
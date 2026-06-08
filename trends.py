import pandas as pd


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


def _describe_missing_columns(missing, rename_map):
    """For each missing required column, lists the header names that would have
    been accepted for it (the canonical name plus its aliases in rename_map)."""
    return [
        {
            'column': col,
            'accepted': [col] + [raw for raw, target in rename_map.items() if target == col],
        }
        for col in missing
    ]


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
            found_headers = list(df_temp.columns)
            df_temp.rename(columns=rename_map, inplace=True)

            required_check = ['Match_Status', 'Time']
            missing = [col for col in required_check if col not in df_temp.columns]
            if missing:
                failed_files.append({
                    'File': file.name,
                    'Reason': f"Missing required column(s): {', '.join(missing)}",
                    'Missing': _describe_missing_columns(missing, rename_map),
                    'Found': found_headers,
                })
                continue

            df_temp['Match_Status'] = df_temp['Match_Status'].astype(str).str.title().str.strip()
            df_temp['Match_Status'] = df_temp['Match_Status'].replace({
                'Update Needed': 'Update needed', 'Matching': 'Matching', 'Missing': 'Missing'
            })
            all_reports.append(df_temp)
        except Exception as e:
            failed_files.append({
                'File': file.name,
                'Reason': f"Could not read the file ({e})",
                'Missing': [],
                'Found': [],
            })

    return all_reports, failed_files


def get_trend_suffix(valid_df):
    """Generates the suffix used for trend chart export filenames."""
    try:
        start_date = valid_df['Business_Date'].min().strftime('%m%d')
        end_date = valid_df['Business_Date'].max().strftime('%m%d')
        return f"{start_date}_to_{end_date}"
    except Exception:
        return "history"


def get_apc_performance_data(valid_df):
    """Aggregates Matching rows per Business_Date and computes accurate-time %."""
    matching_df = valid_df[valid_df['Match_Status'] == 'Matching'].copy()

    if matching_df.empty:
        return pd.DataFrame()

    matching_df['is_accurate_time'] = matching_df['Reason'].astype(str).str.contains(
        "time is more accurate in APC", case=False, na=False
    )

    perf_stats = matching_df.groupby('Business_Date').agg(
        Total_Matching=('Match_Status', 'count'),
        Accurate_Time_Count=('is_accurate_time', 'sum')
    ).reset_index()

    perf_stats['Performance %'] = (perf_stats['Accurate_Time_Count'] / perf_stats['Total_Matching']) * 100
    perf_stats['Date_Label'] = perf_stats['Business_Date'].dt.strftime('%b %d')

    return perf_stats

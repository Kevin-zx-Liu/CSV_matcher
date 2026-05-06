import altair as alt
import pandas as pd

STATUS_DOMAIN = ['Missing', 'Update needed', 'Matching']
STATUS_RANGE = ['#FF7601', '#FCB53B', '#00809D']


def get_reason_colors(unique_reasons):
    """Generates the color mapping for missing reasons, with specific colors for known reasons."""
    color_range = []
    safe_palette = ['#2ca02c', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    palette_idx = 0

    for r in unique_reasons:
        r_lower = r.lower()
        if r_lower == "missing":
            color_range.append('#d62728')
        elif "missing in apc but present in trend" in r_lower:
            color_range.append('#ff9896')
        elif "chart status not correct" in r_lower:
            color_range.append('#1f77b4')
        elif "missing due to a virtual parameter" in r_lower:
            color_range.append('#ff7f0e')
        else:
            color_range.append(safe_palette[palette_idx % len(safe_palette)])
            palette_idx += 1
    return color_range


def build_daily_chart(valid_df, trend_suffix):
    """Stacked bar of Missing / Update needed / Matching percentages per Business_Date."""
    daily_counts = valid_df.groupby(['Business_Date', 'Match_Status']).size().unstack(fill_value=0)
    for col in STATUS_DOMAIN:
        if col not in daily_counts.columns:
            daily_counts[col] = 0

    total = daily_counts['Matching'] + daily_counts['Missing'] + daily_counts['Update needed']
    chart_data = (daily_counts[['Missing', 'Update needed', 'Matching']].div(total, axis=0) * 100).reset_index()
    chart_data['Date_Label'] = chart_data['Business_Date'].dt.strftime('%b %d')
    chart_data = chart_data.melt(['Business_Date', 'Date_Label'], var_name='Status', value_name='Percentage')

    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Date_Label:O', sort=alt.EncodingSortField(field="Business_Date", op="min"),
                title='Date', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Percentage:Q', scale=alt.Scale(domain=[0, 100])),
        color=alt.Color('Status', scale=alt.Scale(domain=STATUS_DOMAIN, range=STATUS_RANGE)),
        tooltip=['Date_Label', 'Status', alt.Tooltip('Percentage', format='.1f')]
    ).properties(height=350)
    chart["usermeta"] = {"embedOptions": {"downloadFileName": f"Trend_{trend_suffix}"}}
    return chart


def build_reasons_chart(valid_df, trend_suffix):
    """Per-day stacked bar of Missing/Update-needed reasons. Shows empty bars for days with no missing data."""
    missing_df = valid_df[valid_df['Match_Status'].isin(['Missing', 'Update needed'])].copy()
    all_dates = sorted(valid_df['Business_Date'].unique())

    if not missing_df.empty:
        missing_df['Reason'] = (
            missing_df['Reason']
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .str.capitalize()
            .replace({'Nan': 'Unknown', 'None': 'Unknown', '': 'Unknown'})
        )
        unique_reasons = sorted(missing_df['Reason'].unique().tolist())
    else:
        unique_reasons = ["No Missing Items"]

    full_index = pd.MultiIndex.from_product([all_dates, unique_reasons], names=['Business_Date', 'Reason'])
    reason_counts = pd.DataFrame(index=full_index).reset_index()

    if not missing_df.empty:
        actual_counts = missing_df.groupby(['Business_Date', 'Reason']).size().reset_index(name='Count')
        reason_counts = pd.merge(reason_counts, actual_counts, on=['Business_Date', 'Reason'], how='left')
    else:
        reason_counts['Count'] = 0

    reason_counts['Count'] = reason_counts['Count'].fillna(0)
    reason_counts['Date_Label'] = reason_counts['Business_Date'].dt.strftime('%b %d')

    chart = alt.Chart(reason_counts).mark_bar().encode(
        x=alt.X('Date_Label:O', sort=alt.EncodingSortField(field="Business_Date", op="min"),
                title='Date', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Count:Q'),
        color=alt.Color('Reason', title='Reason',
                        scale=alt.Scale(domain=unique_reasons, range=get_reason_colors(unique_reasons))),
        tooltip=['Date_Label', 'Reason', 'Count']
    ).properties(height=400)
    chart["usermeta"] = {"embedOptions": {"downloadFileName": f"MissingReasons_trend_{trend_suffix}"}}
    return chart


def build_apc_performance_chart(perf_data, trend_suffix):
    """Bar chart of accurate-time percentage per day, from the prepared perf_data frame."""
    chart = alt.Chart(perf_data).mark_bar().encode(
        x=alt.X('Date_Label:O', sort=alt.EncodingSortField(field="Business_Date", op="min"), title='Date'),
        y=alt.Y('Performance %:Q', scale=alt.Scale(domain=[0, 100]), title='Accurate Time Percentage (%)'),
        tooltip=['Date_Label', alt.Tooltip('Performance %', format='.1f'), 'Total_Matching']
    ).properties(height=350)
    chart["usermeta"] = {"embedOptions": {"downloadFileName": f"APC_Performance_{trend_suffix}"}}
    return chart


def build_current_week_bar(matching_rate):
    """Single-bar chart with text label for the current week's matching rate."""
    chart_data_curr = pd.DataFrame({'Category': ['Current Week'], 'Matching Rate': [matching_rate]})
    bar = alt.Chart(chart_data_curr).mark_bar(size=60, color='#00809D').encode(
        x=alt.X('Category:N', title=None),
        y=alt.Y('Matching Rate:Q', scale=alt.Scale(domain=[0, 100]), title='Matching %'),
        tooltip=[alt.Tooltip('Matching Rate', format='.1f')]
    ).properties(height=300)
    label = bar.mark_text(dy=-5, fontWeight='bold').encode(text=alt.Text('Matching Rate:Q', format='.1f'))
    return bar + label


def build_weekly_trend_chart(combined_wk_df):
    """Stacked weekly trend bar across uploaded weekly summaries."""
    chart = alt.Chart(combined_wk_df).mark_bar().encode(
        x=alt.X('Time:O', title='Week Range', sort=None),
        y=alt.Y('Percentage:Q', scale=alt.Scale(domain=[0, 100]), title='Percentage (%)'),
        color=alt.Color('Match_Status:N',
                        scale=alt.Scale(domain=STATUS_DOMAIN, range=STATUS_RANGE),
                        title='Status'),
        tooltip=['Time', 'Match_Status', alt.Tooltip('Percentage', format='.1f'), 'Count']
    ).properties(height=350)
    chart["usermeta"] = {"embedOptions": {"downloadFileName": "Weekly_trend"}}
    return chart

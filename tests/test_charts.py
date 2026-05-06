import unittest

import pandas as pd

from charts import (
    build_apc_performance_chart,
    build_current_week_bar,
    build_daily_chart,
    build_reasons_chart,
    build_weekly_trend_chart,
    get_reason_colors,
)


class TestGetReasonColors(unittest.TestCase):
    def test_specific_keywords_get_specific_colors(self):
        reasons = [
            'Missing',
            'Missing in APC but present in trend',
            'Chart status not correct',
            'Missing due to a virtual parameter',
        ]
        colors = get_reason_colors(reasons)

        self.assertEqual(colors[0], '#d62728')
        self.assertEqual(colors[1], '#ff9896')
        self.assertEqual(colors[2], '#1f77b4')
        self.assertEqual(colors[3], '#ff7f0e')

    def test_unknown_reasons_fall_back_to_safe_palette(self):
        reasons = ['Other_one', 'Other_two', 'Other_three']
        colors = get_reason_colors(reasons)

        self.assertEqual(len(set(colors)), 3)
        for c in colors:
            self.assertTrue(c.startswith('#'))


class TestChartBuilders(unittest.TestCase):
    """Smoke tests: chart builders should produce a valid Altair spec without raising."""

    def _valid_df(self):
        return pd.DataFrame({
            'Match_Status': ['Matching', 'Missing', 'Update needed', 'Matching'],
            'Reason': ['x', 'Missing', 'Chart status not correct', 'Time is more accurate in APC'],
            'CHARTNAME': ['c1', 'c2', 'c1', 'c1'],
            'Business_Date': pd.to_datetime(['2025-03-01', '2025-03-01', '2025-03-02', '2025-03-02']),
        })

    def test_build_daily_chart_has_correct_download_filename(self):
        chart = build_daily_chart(self._valid_df(), trend_suffix='0301_to_0302')
        spec = chart.to_dict()
        self.assertIn('Trend_0301_to_0302', spec['usermeta']['embedOptions']['downloadFileName'])

    def test_build_reasons_chart_renders_with_no_missing_data(self):
        df = pd.DataFrame({
            'Match_Status': ['Matching', 'Matching'],
            'Reason': ['x', 'y'],
            'Business_Date': pd.to_datetime(['2025-03-01', '2025-03-02']),
        })
        chart = build_reasons_chart(df, trend_suffix='0301_to_0302')
        spec = chart.to_dict()
        self.assertIn('MissingReasons_trend_0301_to_0302', spec['usermeta']['embedOptions']['downloadFileName'])

    def test_build_apc_performance_chart_renders(self):
        perf = pd.DataFrame({
            'Business_Date': pd.to_datetime(['2025-03-01']),
            'Total_Matching': [3],
            'Accurate_Time_Count': [2],
            'Performance %': [66.6],
            'Date_Label': ['Mar 01'],
        })
        chart = build_apc_performance_chart(perf, trend_suffix='0301_to_0301')
        spec = chart.to_dict()
        self.assertIn('APC_Performance_0301_to_0301', spec['usermeta']['embedOptions']['downloadFileName'])

    def test_build_current_week_bar_renders(self):
        # Layered chart: returns a LayerChart, not a single Chart
        chart = build_current_week_bar(75.5)
        spec = chart.to_dict()
        self.assertIn('layer', spec)

    def test_build_weekly_trend_chart_renders(self):
        df = pd.DataFrame({
            'Time': ['0301-0307', '0308-0314'],
            'Match_Status': ['Matching', 'Missing'],
            'Percentage': [80.0, 20.0],
            'Count': [16, 4],
        })
        chart = build_weekly_trend_chart(df)
        spec = chart.to_dict()
        self.assertEqual(spec['usermeta']['embedOptions']['downloadFileName'], 'Weekly_trend')


if __name__ == '__main__':
    unittest.main()

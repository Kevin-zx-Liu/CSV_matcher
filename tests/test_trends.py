import io
import unittest

import pandas as pd

from trends import (
    get_apc_performance_data,
    get_export_filename,
    get_trend_suffix,
    process_trend_reports,
)


def make_named_file(content, name="test.csv", encoding='utf-8'):
    """Returns a BytesIO with a `.name` attribute, matching the streamlit UploadedFile shape."""
    if isinstance(content, str):
        content = content.encode(encoding)
    buf = io.BytesIO(content)
    buf.name = name
    return buf


class TestGetExportFilename(unittest.TestCase):
    def test_uses_business_date_from_yyyymmdd_format(self):
        # 20250101 050000 minus 7h = 2024-12-31 22:00 -> +1 day = 2025-01-01 -> "0101"
        df = pd.DataFrame({'Time': ['20250101 050000', '20250101 050000']})
        self.assertEqual(get_export_filename(df), 'matching_report_0101.csv')

    def test_falls_back_to_default_when_dates_unparseable(self):
        df = pd.DataFrame({'Time': ['not a date', 'still not']})
        self.assertEqual(get_export_filename(df), 'matching_report.csv')

    def test_handles_iso_format_via_fallback_parser(self):
        df = pd.DataFrame({'Time': ['2025-03-15 10:00:00', '2025-03-15 11:00:00']})
        result = get_export_filename(df)
        self.assertTrue(result.startswith('matching_report_'))
        self.assertTrue(result.endswith('.csv'))


class TestProcessTrendReports(unittest.TestCase):
    def test_renames_columns_and_normalizes_status(self):
        csv = (
            "Match_Status,Time,New_Comments\n"
            "matching,20250101 120000,All good\n"
            "update needed,20250101 130000,Time off\n"
            "missing,20250101 140000,Not present\n"
        )
        files = [make_named_file(csv, name="report1.csv")]

        all_reports, failed = process_trend_reports(files)

        self.assertEqual(failed, [])
        self.assertEqual(len(all_reports), 1)
        df = all_reports[0]
        self.assertIn('Reason', df.columns)
        self.assertListEqual(
            df['Match_Status'].tolist(),
            ['Matching', 'Update needed', 'Missing'],
        )

    def test_records_failure_when_required_columns_missing(self):
        csv = "foo,bar\n1,2\n"
        files = [make_named_file(csv, name="bad.csv")]

        all_reports, failed = process_trend_reports(files)

        self.assertEqual(all_reports, [])
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['File'], 'bad.csv')

        reason = failed[0]['Reason']
        # Names both missing canonical columns
        self.assertIn('Match_Status', reason)
        self.assertIn('Time', reason)
        # Lists accepted header aliases so the user knows what to rename to
        self.assertIn('LOT_HOLD_TIME', reason)
        self.assertIn('COMMENT', reason)
        # Echoes what the file actually contained
        self.assertIn('foo', reason)
        self.assertIn('bar', reason)

    def test_failure_reason_omits_present_column(self):
        # Time is present (recognized via the LOT_HOLD_TIME alias); only
        # Match_Status should be reported missing. Semicolon-separated so the
        # comma->semicolon re-read fallback doesn't collapse it into one column.
        csv = "foo;LOT_HOLD_TIME\n1;20250101 120000\n"
        files = [make_named_file(csv, name="partial.csv")]

        all_reports, failed = process_trend_reports(files)

        self.assertEqual(all_reports, [])
        reason = failed[0]['Reason']
        self.assertIn("'Match_Status'", reason)
        self.assertNotIn("'Time'", reason)

    def test_records_failure_for_unreadable_file(self):
        files = [make_named_file(b"\x00\x01\x02\x03", name="binary.csv")]
        all_reports, failed = process_trend_reports(files)

        self.assertEqual(all_reports, [])
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['File'], 'binary.csv')


class TestGetTrendSuffix(unittest.TestCase):
    def test_returns_min_to_max_date_range(self):
        df = pd.DataFrame({
            'Business_Date': pd.to_datetime(['2025-03-01', '2025-03-05', '2025-03-03'])
        })
        self.assertEqual(get_trend_suffix(df), '0301_to_0305')

    def test_falls_back_to_history_on_error(self):
        df = pd.DataFrame({'Business_Date': []})
        self.assertEqual(get_trend_suffix(df), 'history')


class TestGetApcPerformanceData(unittest.TestCase):
    def test_returns_empty_when_no_matching_rows(self):
        df = pd.DataFrame({
            'Match_Status': ['Missing', 'Missing'],
            'Reason': ['x', 'y'],
            'Business_Date': pd.to_datetime(['2025-03-01', '2025-03-02']),
        })
        result = get_apc_performance_data(df)
        self.assertTrue(result.empty)

    def test_calculates_performance_percentage(self):
        df = pd.DataFrame({
            'Match_Status': ['Matching', 'Matching', 'Matching', 'Matching', 'Missing'],
            'Reason': [
                'Time is more accurate in APC',
                'Time is more accurate in APC',
                'Other reason',
                'Time is more accurate in APC',
                'irrelevant',
            ],
            'Business_Date': pd.to_datetime(
                ['2025-03-01', '2025-03-01', '2025-03-01', '2025-03-02', '2025-03-02']
            ),
        })
        result = get_apc_performance_data(df)

        self.assertEqual(len(result), 2)
        day1 = result[result['Business_Date'] == pd.Timestamp('2025-03-01')].iloc[0]
        day2 = result[result['Business_Date'] == pd.Timestamp('2025-03-02')].iloc[0]

        self.assertEqual(day1['Total_Matching'], 3)
        self.assertEqual(day1['Accurate_Time_Count'], 2)
        self.assertAlmostEqual(day1['Performance %'], 2 / 3 * 100, places=4)

        self.assertEqual(day2['Total_Matching'], 1)
        self.assertEqual(day2['Accurate_Time_Count'], 1)
        self.assertAlmostEqual(day2['Performance %'], 100.0)
        self.assertIn('Mar', day1['Date_Label'])

    def test_match_is_case_insensitive(self):
        df = pd.DataFrame({
            'Match_Status': ['Matching', 'Matching'],
            'Reason': ['TIME IS MORE ACCURATE IN APC', 'time is more accurate in apc'],
            'Business_Date': pd.to_datetime(['2025-03-01', '2025-03-01']),
        })
        result = get_apc_performance_data(df)
        self.assertEqual(result.iloc[0]['Accurate_Time_Count'], 2)
        self.assertAlmostEqual(result.iloc[0]['Performance %'], 100.0)


if __name__ == '__main__':
    unittest.main()

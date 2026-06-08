import unittest
from unittest.mock import patch

import pandas as pd

from matching import apply_matching_logic, build_export_report, extract_metadata, EXPORT_COLUMNS


class TestExtractMetadata(unittest.TestCase):
    def test_extracts_chartname_and_equip(self):
        df = pd.DataFrame({
            'ID': ['lot001'],
            'Time': ['20250101 120000'],
            'Info': ['SMCchart MyChart_v1 - Lot held by Equipment EQP01#42 due to ...'],
        })
        out = extract_metadata(df)

        self.assertEqual(out.iloc[0]['CHARTNAME'], 'mychart_v1')
        self.assertEqual(out.iloc[0]['EQUIP'], 'EQP01#42')

    def test_normalizes_key_uppercase_and_strip(self):
        df = pd.DataFrame({
            'ID': ['  lot001  '],
            'Time': ['20250101 120000'],
            'Info': ['no pattern here'],
        })
        out = extract_metadata(df)

        self.assertEqual(out.iloc[0]['__key'], 'LOT001')
        self.assertTrue(pd.isna(out.iloc[0]['CHARTNAME']))
        self.assertEqual(out.iloc[0]['__chart_clean'], '')

    def test_missing_chart_pattern_yields_nan(self):
        df = pd.DataFrame({
            'ID': ['lot001'],
            'Time': ['20250101 120000'],
            'Info': ['some unrelated free text'],
        })
        out = extract_metadata(df)
        self.assertTrue(pd.isna(out.iloc[0]['CHARTNAME']))
        self.assertTrue(pd.isna(out.iloc[0]['EQUIP']))


class TestApplyMatchingLogic(unittest.TestCase):
    def _make_left(self, rows):
        return extract_metadata(pd.DataFrame(rows))

    def test_composite_key_match_succeeds(self):
        df_left = self._make_left([{
            'ID': 'LOT001',
            'Time': '20250101 120000',
            'Info': 'SMCchart Chart_A - Lot held by Equipment EQP01#1',
        }])
        df_right = pd.DataFrame({
            'ID': ['LOT001'],
            'Chart': ['CHART_A'],
            'Time': ['20250101 130000'],
        })

        df_left, df_right = apply_matching_logic(df_left, df_right)
        self.assertTrue(bool(df_left.iloc[0]['Found_in_Right']))

    def test_chart_name_mismatch_does_not_match(self):
        df_left = self._make_left([{
            'ID': 'LOT001',
            'Time': '20250101 120000',
            'Info': 'SMCchart Chart_A - Lot held by Equipment EQP01#1',
        }])
        df_right = pd.DataFrame({
            'ID': ['LOT001'],
            'Chart': ['DIFFERENT_CHART'],
            'Time': ['20250101 130000'],
        })

        df_left, _ = apply_matching_logic(df_left, df_right)
        self.assertFalse(bool(df_left.iloc[0]['Found_in_Right']))

    def test_childlot_id_with_dot_matched_via_eventlist(self):
        df_left = self._make_left([{
            'ID': 'LOT001.5',
            'Time': '20250101 120000',
            'Info': 'SMCchart Chart_A - Lot held by Equipment EQP01#1',
        }])
        df_right = pd.DataFrame({
            'ID': ['OTHER_LOT'],
            'Chart': ['Chart_X'],
            'Time': ['20250101 130000'],
            'Eventlist': ['... contained LOT001.5 in here ...'],
        })

        with patch('matching.st.toast'):
            df_left, _ = apply_matching_logic(df_left, df_right)

        self.assertTrue(bool(df_left.iloc[0]['Found_in_Right']))

    def test_handles_right_without_chart_column(self):
        df_left = self._make_left([{
            'ID': 'LOT001',
            'Time': '20250101 120000',
            'Info': 'no chart info',
        }])
        df_right = pd.DataFrame({
            'ID': ['LOT001'],
            'Time': ['20250101 130000'],
        })

        df_left, df_right = apply_matching_logic(df_left, df_right)
        self.assertTrue(bool(df_left.iloc[0]['Found_in_Right']))
        self.assertIn('__chart_clean', df_right.columns)


class TestBuildExportReport(unittest.TestCase):
    def _make_df(self):
        return pd.DataFrame({
            'Found_in_Right': [True, False],
            'ID': ['LOT001', 'LOT002'],
            'Time': ['20250101 120000', '20250101 130000'],
            'CHARTNAME': ['chart_a', 'chart_b'],
            'EQUIP': ['EQP01#1', 'EQP01#2'],
            'Info': ['info one', 'info two'],
        })

    def test_export_has_exact_columns_in_order(self):
        out = build_export_report(self._make_df())
        self.assertEqual(
            list(out.columns),
            ['Match_Status', 'ID', 'Time', 'CHARTNAME', 'EQUIP', 'Info'],
        )
        self.assertEqual(list(out.columns), EXPORT_COLUMNS)

    def test_found_in_right_becomes_match_status(self):
        out = build_export_report(self._make_df())
        self.assertEqual(out['Match_Status'].tolist(), ['Matching', 'Missing'])
        self.assertNotIn('Found_in_Right', out.columns)

    def test_csv_header_matches_expected_format(self):
        csv_text = build_export_report(self._make_df()).to_csv(index=False)
        header = csv_text.splitlines()[0]
        self.assertEqual(header, 'Match_Status,ID,Time,CHARTNAME,EQUIP,Info')

    def test_missing_optional_columns_are_skipped_without_error(self):
        df = pd.DataFrame({
            'Found_in_Right': [True],
            'ID': ['LOT001'],
            'Time': ['20250101 120000'],
        })
        out = build_export_report(df)
        self.assertEqual(list(out.columns), ['Match_Status', 'ID', 'Time'])

    def test_does_not_mutate_input(self):
        df = self._make_df()
        build_export_report(df)
        self.assertNotIn('Match_Status', df.columns)


if __name__ == '__main__':
    unittest.main()

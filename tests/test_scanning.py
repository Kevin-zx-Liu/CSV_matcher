import io
import unittest

from scanning import robust_scan


LEFT_TARGETS = {
    'ID': ['LOT_ID', 'LOTID'],
    'Time': ['LOT_HOLD_TIME', 'TIME'],
    'Info': ['LOT_HOLD_COMMENT'],
}

RIGHT_TARGETS = {
    'ID': ['LOTID', 'LOT_ID', 'BATCHID'],
    'Chart': ['CHARTNAME', 'CHART'],
    'Time': ['DATETIME', 'TIME'],
    'Equipment': ['EQPNAME', 'EQUIPMENT'],
    'Eventlist': ['EVENTLIST', 'EVENT_LIST'],
}


def make_file(content, encoding='utf-8'):
    """Wrap text content in a BytesIO so robust_scan can decode it."""
    if isinstance(content, str):
        content = content.encode(encoding)
    return io.BytesIO(content)


class TestRobustScanDelimiters(unittest.TestCase):
    def test_detects_comma_delimiter(self):
        csv = (
            "LOT_ID,LOT_HOLD_TIME,LOT_HOLD_COMMENT\n"
            "ABC123,20250101 120000,Some comment\n"
            "DEF456,20250101 130000,Another comment\n"
        )
        df, err = robust_scan(make_file(csv), "Left", LEFT_TARGETS)

        self.assertIsNone(err)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['ID'], 'ABC123')
        self.assertEqual(df.iloc[1]['Time'], '20250101 130000')
        self.assertEqual(df.iloc[0]['Info'], 'Some comment')

    def test_detects_semicolon_delimiter(self):
        csv = (
            "LOTID;CHARTNAME;DATETIME;EQPNAME;EVENTLIST\n"
            "ABC123;chart_a;20250101 120000;EQP01#1;evt_a\n"
            "DEF456;chart_b;20250101 130000;EQP02#2;evt_b\n"
        )
        df, err = robust_scan(make_file(csv), "Right", RIGHT_TARGETS)

        self.assertIsNone(err)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['ID'], 'ABC123')
        self.assertEqual(df.iloc[0]['Chart'], 'chart_a')
        self.assertEqual(df.iloc[1]['Equipment'], 'EQP02#2')
        self.assertEqual(df.iloc[1]['Eventlist'], 'evt_b')


class TestRobustScanHeaderDiscovery(unittest.TestCase):
    def test_skips_preamble_rows_before_header(self):
        csv = (
            "# exported on 2025-01-01\n"
            "\n"
            "Some random preamble line\n"
            "LOT_ID,LOT_HOLD_TIME,LOT_HOLD_COMMENT\n"
            "ABC123,20250101 120000,A comment\n"
        )
        df, err = robust_scan(make_file(csv), "Left", LEFT_TARGETS)

        self.assertIsNone(err)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['ID'], 'ABC123')

    def test_returns_error_when_header_not_found(self):
        csv = "foo,bar,baz\n1,2,3\n"
        df, err = robust_scan(make_file(csv), "Left", LEFT_TARGETS)

        self.assertIsNone(df)
        self.assertIsNotNone(err)
        self.assertIn("Left", err)

    def test_strips_quotes_from_values(self):
        csv = (
            'LOT_ID,LOT_HOLD_TIME,LOT_HOLD_COMMENT\n'
            '"ABC123","20250101 120000","quoted comment"\n'
        )
        df, err = robust_scan(make_file(csv), "Left", LEFT_TARGETS)

        self.assertIsNone(err)
        self.assertEqual(df.iloc[0]['ID'], 'ABC123')
        self.assertEqual(df.iloc[0]['Info'], 'quoted comment')


class TestRobustScanEdgeCases(unittest.TestCase):
    def test_handles_latin1_encoded_bytes(self):
        csv_text = "LOT_ID,LOT_HOLD_TIME,LOT_HOLD_COMMENT\nABC,20250101 120000,café\n"
        df, err = robust_scan(make_file(csv_text, encoding='latin1'), "Left", LEFT_TARGETS)

        self.assertIsNone(err)
        self.assertEqual(df.iloc[0]['Info'], 'café')

    def test_skips_rows_shorter_than_max_index(self):
        csv = (
            "LOT_ID,LOT_HOLD_TIME,LOT_HOLD_COMMENT\n"
            "ABC,20250101 120000,ok\n"
            "shortrow\n"
            "DEF,20250101 130000,also ok\n"
        )
        df, err = robust_scan(make_file(csv), "Left", LEFT_TARGETS)

        self.assertIsNone(err)
        self.assertEqual(len(df), 2)
        self.assertListEqual(df['ID'].tolist(), ['ABC', 'DEF'])

    def test_missing_optional_target_marked_as_NA(self):
        csv = (
            "LOT_ID,LOT_HOLD_TIME,EXTRA\n"
            "ABC,20250101 120000,ignored\n"
        )
        df, err = robust_scan(make_file(csv), "Left", LEFT_TARGETS)

        self.assertIsNone(err)
        self.assertEqual(df.iloc[0]['ID'], 'ABC')
        self.assertEqual(df.iloc[0]['Info'], 'N/A')


if __name__ == '__main__':
    unittest.main()

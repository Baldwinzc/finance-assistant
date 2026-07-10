import unittest

import pandas as pd

from valuation_agent.data import merge_index_valuation_frames, normalize_stock_value_frame


class DataTransformTest(unittest.TestCase):
    def test_normalize_stock_value_frame(self):
        raw = pd.DataFrame(
            {
                "日期": ["2024-01-01", "2024-01-02"],
                "收盘价": [10.0, 10.5],
                "市盈率(TTM)": [12.0, 13.0],
                "市净率": [1.2, 1.3],
            }
        )
        frame = normalize_stock_value_frame(raw)
        self.assertEqual(list(frame.columns), ["date", "close", "pe_ttm", "pb"])
        self.assertEqual(frame["pe_ttm"].iloc[-1], 13.0)

    def test_merge_index_frames(self):
        pe = pd.DataFrame({"日期": ["2024-01-01", "2024-01-02"], "指数": [3000, 3010], "市盈率": [10, 11]})
        pb = pd.DataFrame({"日期": ["2024-01-01", "2024-01-02"], "市净率": [1.1, 1.2]})
        frame = merge_index_valuation_frames(pe, pb)
        self.assertIn("pe", frame.columns)
        self.assertIn("pb", frame.columns)
        self.assertEqual(frame["pb"].iloc[-1], 1.2)


if __name__ == "__main__":
    unittest.main()


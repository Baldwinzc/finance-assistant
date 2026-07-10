import unittest

import pandas as pd

from valuation_agent.charts import build_valuation_chart, summarize_valuation, valuation_zone


class ChartsTest(unittest.TestCase):
    def test_summarize_valuation(self):
        frame = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=10),
                "close": range(10),
                "pe_ttm": range(10, 20),
                "pb": [1 + i / 10 for i in range(10)],
            }
        )
        summary = summarize_valuation(frame)
        labels = {item.label for item in summary}
        self.assertIn("PE(TTM)", labels)
        self.assertIn("PB", labels)
        self.assertGreater(summary[0].percentile, 0.9)

    def test_build_chart(self):
        frame = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=10),
                "close": range(10),
                "pe_ttm": range(10, 20),
                "pb": [1 + i / 10 for i in range(10)],
            }
        )
        figure = build_valuation_chart(frame, "测试")
        self.assertGreaterEqual(len(figure.data), 3)

    def test_zone(self):
        self.assertIn("低估", valuation_zone(0.1))
        self.assertIn("高估", valuation_zone(0.95))


if __name__ == "__main__":
    unittest.main()


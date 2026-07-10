import unittest

from valuation_agent.brain import Brain
from valuation_agent.models import AssetCandidate, AssetType


class BrainTest(unittest.TestCase):
    def setUp(self):
        self.brain = Brain(
            stock_catalog=[
                AssetCandidate(AssetType.A_STOCK, "600519.SH", "贵州茅台", 1.0),
                AssetCandidate(AssetType.A_STOCK, "000001.SZ", "平安银行", 1.0),
            ]
        )

    def test_direct_a_share_code(self):
        result = self.brain.resolve("600519")
        self.assertEqual(result.asset_type, AssetType.A_STOCK)
        self.assertEqual(result.primary.symbol, "600519.SH")

    def test_stock_name_match(self):
        result = self.brain.resolve("贵州茅台")
        self.assertEqual(result.asset_type, AssetType.A_STOCK)
        self.assertEqual(result.primary.name, "贵州茅台")

    def test_index_typo_alias(self):
        result = self.brain.resolve("沪深三百")
        self.assertEqual(result.asset_type, AssetType.INDEX)
        self.assertEqual(result.primary.name, "沪深300")

    def test_industry_query(self):
        result = self.brain.resolve("医疗行业")
        self.assertEqual(result.asset_type, AssetType.INDUSTRY_INDEX)
        self.assertGreaterEqual(len(result.candidates), 2)


if __name__ == "__main__":
    unittest.main()

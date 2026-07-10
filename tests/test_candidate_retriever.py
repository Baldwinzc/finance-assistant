import unittest

from valuation_agent.candidate_retriever import CandidateRetriever, normalize_query
from valuation_agent.models import AssetCandidate, AssetType


class CandidateRetrieverTest(unittest.TestCase):
    def setUp(self):
        self.retriever = CandidateRetriever(
            stock_catalog=[
                AssetCandidate(AssetType.A_STOCK, "600519.SH", "贵州茅台", 1.0),
                AssetCandidate(AssetType.A_STOCK, "000001.SZ", "平安银行", 1.0),
            ]
        )

    def test_collects_direct_a_share_code_candidate(self):
        candidates = self.retriever.collect("600519")
        self.assertEqual(candidates[0].asset_type, AssetType.A_STOCK)
        self.assertEqual(candidates[0].symbol, "600519.SH")
        self.assertEqual(candidates[0].name, "贵州茅台")
        self.assertEqual(len(candidates), 1)

    def test_collects_stock_name_candidate(self):
        candidates = self.retriever.collect("贵州茅台")
        self.assertTrue(any(item.name == "贵州茅台" for item in candidates))

    def test_collects_index_typo_alias_candidate(self):
        candidates = self.retriever.collect("沪深三百")
        self.assertTrue(any(item.asset_type == AssetType.INDEX and item.name == "沪深300" for item in candidates))

    def test_collects_industry_candidates(self):
        candidates = self.retriever.collect("医疗行业")
        industry_candidates = [item for item in candidates if item.asset_type == AssetType.INDUSTRY_INDEX]
        self.assertGreaterEqual(len(industry_candidates), 2)

    def test_normalizes_query_for_prompt_context(self):
        self.assertEqual(normalize_query(" 沪深 三百 "), "沪深三百")


if __name__ == "__main__":
    unittest.main()

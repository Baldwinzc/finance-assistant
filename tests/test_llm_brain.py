import json
import unittest

from valuation_agent.llm_brain import LLMBrain
from valuation_agent.models import AssetCandidate, AssetType


def response_for(candidate, confidence=0.91, needs_clarification=False):
    return json.dumps(
        {
            "intent": "valuation_analysis",
            "asset_type": candidate["asset_type"],
            "normalized_query": candidate["name"],
            "primary_candidate_id": "" if needs_clarification else candidate["candidate_id"],
            "candidates": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "asset_type": candidate["asset_type"],
                    "symbol": candidate["symbol"],
                    "name": candidate["name"],
                    "confidence": confidence,
                    "reason": "从候选上下文匹配到最相关标的",
                }
            ],
            "needs_clarification": needs_clarification,
            "clarification_question": "请确认是否选择该候选。" if needs_clarification else "",
            "explanation": "LLM 已基于候选上下文完成结构化判断。",
        },
        ensure_ascii=False,
    )


class LLMBrainTest(unittest.TestCase):
    def setUp(self):
        self.stock_catalog = [
            AssetCandidate(AssetType.A_STOCK, "600519.SH", "贵州茅台", 1.0),
            AssetCandidate(AssetType.A_STOCK, "000001.SZ", "平安银行", 1.0),
        ]

    def test_resolves_stock_from_llm_candidate(self):
        def provider(messages, schema):
            payload = json.loads(messages[-1]["content"])
            candidate = payload["candidates_context"][0]
            return response_for(candidate)

        brain = LLMBrain(stock_catalog=self.stock_catalog, llm_response_provider=provider)
        result = brain.resolve("茅台")
        self.assertEqual(result.asset_type, AssetType.A_STOCK)
        self.assertEqual(result.primary.symbol, "600519.SH")
        self.assertFalse(result.needs_clarification)

    def test_low_confidence_requires_confirmation(self):
        def provider(messages, schema):
            payload = json.loads(messages[-1]["content"])
            candidate = payload["candidates_context"][0]
            return response_for(candidate, confidence=0.55)

        brain = LLMBrain(stock_catalog=self.stock_catalog, llm_response_provider=provider)
        result = brain.resolve("茅台")
        self.assertIsNone(result.primary)
        self.assertTrue(result.needs_clarification)
        self.assertGreaterEqual(len(result.candidates), 1)

    def test_validation_error_is_sent_back_to_llm_for_retry(self):
        calls = []

        def provider(messages, schema):
            payload = json.loads(messages[-1]["content"])
            calls.append(payload)
            candidate = payload["candidates_context"][0]
            if len(calls) == 1:
                bad = dict(candidate)
                bad["candidate_id"] = "made_up"
                return response_for(bad)
            self.assertIn("previous_errors", payload)
            return response_for(candidate)

        brain = LLMBrain(stock_catalog=self.stock_catalog, llm_response_provider=provider, max_retries=1)
        result = brain.resolve("贵州茅台")
        self.assertEqual(result.primary.symbol, "600519.SH")
        self.assertEqual(result.debug["llm_attempts"], 2)

    def test_missing_primary_requires_retry_when_not_clarifying(self):
        calls = []

        def provider(messages, schema):
            payload = json.loads(messages[-1]["content"])
            calls.append(payload)
            candidate = payload["candidates_context"][0]
            if len(calls) == 1:
                response = json.loads(response_for(candidate))
                response["primary_candidate_id"] = ""
                response["needs_clarification"] = False
                return json.dumps(response, ensure_ascii=False)
            self.assertIn("previous_errors", payload)
            return response_for(candidate)

        brain = LLMBrain(stock_catalog=self.stock_catalog, llm_response_provider=provider, max_retries=1)
        result = brain.resolve("600519")
        self.assertEqual(result.primary.symbol, "600519.SH")
        self.assertEqual(result.debug["llm_attempts"], 2)

    def test_industry_index_not_etf(self):
        def provider(messages, schema):
            payload = json.loads(messages[-1]["content"])
            candidate = payload["candidates_context"][0]
            return response_for(candidate)

        brain = LLMBrain(stock_catalog=self.stock_catalog, llm_response_provider=provider)
        result = brain.resolve("医疗行业")
        self.assertEqual(result.asset_type, AssetType.INDUSTRY_INDEX)
        self.assertEqual(result.primary.name, "中证医疗")


if __name__ == "__main__":
    unittest.main()

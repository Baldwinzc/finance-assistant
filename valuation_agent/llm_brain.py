from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from jsonschema import Draft202012Validator, ValidationError

from valuation_agent.brain import Brain, INDEX_ALIASES, INDUSTRY_HINTS, normalize_query
from valuation_agent.models import AssetCandidate, AssetType, Resolution


LLM_ASSET_TYPES = ("stock", "index", "industry_index", "unknown")
MIN_CONFIDENCE_FOR_AUTO_RUN = 0.72


LLM_RESOLUTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["valuation_analysis", "unsupported"],
            "description": "用户是否在请求估值分析。",
        },
        "asset_type": {
            "type": "string",
            "enum": list(LLM_ASSET_TYPES),
            "description": "仅支持个股、指数、行业指数；ETF 暂不支持。",
        },
        "normalized_query": {"type": "string"},
        "primary_candidate_id": {
            "type": "string",
            "description": "从候选上下文选择的候选 ID；没有明确候选时为空字符串。",
        },
        "candidates": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "candidate_id": {"type": "string"},
                    "asset_type": {"type": "string", "enum": ["stock", "index", "industry_index"]},
                    "symbol": {"type": "string"},
                    "name": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string"},
                },
                "required": ["candidate_id", "asset_type", "symbol", "name", "confidence", "reason"],
            },
        },
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": [
        "intent",
        "asset_type",
        "normalized_query",
        "primary_candidate_id",
        "candidates",
        "needs_clarification",
        "clarification_question",
        "explanation",
    ],
}


SYSTEM_PROMPT = """你是一个中文金融估值助手的“第一步大脑”。

你的任务只有一个：理解用户输入，判断用户想分析的标的是 A 股个股、指数、行业指数，还是暂不支持/不明确。

硬性规则：
1. 只输出符合 JSON Schema 的对象，不要输出 Markdown。
2. 只能从候选上下文 candidates_context 中选择候选，不能自行编造代码、名称或市场。
3. 当前阶段不支持 ETF 估值；用户问 ETF 时，如果上下文没有可替代的指数候选，应返回 unknown 并要求澄清。
4. 如果用户输入有错别字、简称、口语表达，可以根据候选上下文纠错。
5. 如果置信度低、多个候选接近、或没有足够信息，needs_clarification 必须为 true，primary_candidate_id 为空字符串。
6. 如果能明确识别，needs_clarification 为 false，primary_candidate_id 必须是 candidates 中置信度最高的候选。
7. 不要给投资建议，不要判断买卖，只做标的识别。

输出字段要求：
- confidence 表示“这个候选就是用户所问标的”的置信度，不是投资机会置信度。
- explanation 用中文简要解释识别依据。
- clarification_question 用中文给出下一步确认问题；不需要确认时为空字符串。
"""


@dataclass
class CandidateContext:
    candidate_id: str
    candidate: AssetCandidate
    llm_asset_type: str
    aliases: list[str]

    def to_prompt_item(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "asset_type": self.llm_asset_type,
            "symbol": self.candidate.symbol,
            "name": self.candidate.name,
            "aliases": self.aliases,
            "reason": self.candidate.reason,
        }


class LLMResolutionError(RuntimeError):
    pass


class LLMConfigurationError(LLMResolutionError):
    pass


class LLMBrain:
    """LLM-backed resolver with local schema and candidate validation."""

    def __init__(
        self,
        stock_catalog: list[AssetCandidate] | None = None,
        model: str | None = None,
        llm_response_provider: Callable[[list[dict[str, str]], dict[str, Any]], str] | None = None,
        max_retries: int = 2,
        min_confidence: float = MIN_CONFIDENCE_FOR_AUTO_RUN,
    ) -> None:
        self.stock_catalog = stock_catalog or []
        self.rule_brain = Brain(stock_catalog=self.stock_catalog)
        self.model = model or os.getenv("VALUATION_AGENT_LLM_MODEL", "gpt-4o-mini")
        self.llm_response_provider = llm_response_provider
        self.max_retries = max_retries
        self.min_confidence = min_confidence
        self.schema_validator = Draft202012Validator(LLM_RESOLUTION_SCHEMA)

    def resolve(self, query: str) -> Resolution:
        context = self._build_candidate_context(query)
        errors: list[str] = []
        raw_responses: list[str] = []

        for attempt in range(self.max_retries + 1):
            messages = self._build_messages(query=query, context=context, errors=errors)
            try:
                raw = self._call_llm(messages)
                raw_responses.append(raw)
                payload = self._parse_and_schema_validate(raw)
                resolution = self._payload_to_resolution(query, payload, context)
                resolution.debug["llm_attempts"] = attempt + 1
                resolution.debug["llm_raw_responses"] = raw_responses
                resolution.debug["candidate_context"] = [item.to_prompt_item() for item in context]
                return resolution
            except LLMConfigurationError as exc:
                return Resolution(
                    query=query,
                    asset_type=AssetType.UNKNOWN,
                    primary=None,
                    candidates=[],
                    explanation=str(exc),
                    needs_clarification=True,
                    clarification_question="请先配置 OPENAI_API_KEY 后再使用 LLM 大脑，或临时切换为 rules 模式。",
                    debug={"llm_errors": [format_retry_error(exc)]},
                )
            except Exception as exc:
                errors.append(format_retry_error(exc))

        explanation = "LLM 判断失败，已将异常信息回灌重试，但仍无法得到有效结构化结果。"
        return Resolution(
            query=query,
            asset_type=AssetType.UNKNOWN,
            primary=None,
            candidates=[],
            explanation=explanation,
            needs_clarification=True,
            clarification_question="请换一种说法，或直接输入股票代码、股票名称、指数名称。",
            debug={"llm_errors": errors, "llm_raw_responses": raw_responses},
        )

    def _build_candidate_context(self, query: str) -> list[CandidateContext]:
        normalized = normalize_query(query)
        seen: set[tuple[AssetType, str, str]] = set()
        candidates: list[AssetCandidate] = []

        direct = self.rule_brain._resolve_direct_code(normalized)
        if direct and direct.asset_type != AssetType.ETF:
            candidates.append(direct)

        industry = self.rule_brain._resolve_industry(normalized)
        if industry:
            candidates.extend(industry.candidates)

        exact_index = self.rule_brain._resolve_index(normalized, exact=False)
        if exact_index:
            candidates.append(exact_index)

        stock_matches = self.rule_brain._top_from_catalog(normalized, self.stock_catalog, limit=5) if self.stock_catalog else []
        candidates.extend(stock_matches)

        for candidate in self.rule_brain.index_candidates:
            if normalized and (normalized in candidate.name.lower() or normalized in candidate.symbol.lower()):
                candidates.append(candidate)

        context: list[CandidateContext] = []
        for candidate in candidates:
            if candidate.asset_type == AssetType.ETF:
                continue
            key = (candidate.asset_type, candidate.symbol, candidate.name)
            if key in seen:
                continue
            seen.add(key)
            context.append(
                CandidateContext(
                    candidate_id=f"cand_{len(context) + 1}",
                    candidate=candidate,
                    llm_asset_type=to_llm_asset_type(candidate.asset_type),
                    aliases=find_aliases(candidate),
                )
            )
            if len(context) >= 12:
                break
        return context

    def _build_messages(self, query: str, context: list[CandidateContext], errors: list[str]) -> list[dict[str, str]]:
        user_payload: dict[str, Any] = {
            "query": query,
            "supported_scope": ["A股个股", "指数", "行业指数"],
            "unsupported_scope": ["ETF估值暂不实现"],
            "candidates_context": [item.to_prompt_item() for item in context],
        }
        if errors:
            user_payload["previous_errors"] = errors
            user_payload["retry_instruction"] = "请修正上一轮错误，重新输出完全符合 schema 且能通过候选校验的 JSON。"

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ]

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        if self.llm_response_provider:
            return self.llm_response_provider(messages, LLM_RESOLUTION_SCHEMA)

        if not os.getenv("OPENAI_API_KEY"):
            raise LLMConfigurationError("缺少 OPENAI_API_KEY，无法调用真实 LLM。")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMConfigurationError("缺少 openai 依赖，请先运行：python3 -m pip install -r requirements.txt") from exc

        client = OpenAI()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "valuation_asset_resolution",
                    "strict": True,
                    "schema": LLM_RESOLUTION_SCHEMA,
                },
            },
        )
        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise LLMResolutionError(f"模型拒绝输出：{refusal}")
        if not message.content:
            raise LLMResolutionError("模型返回空内容。")
        return message.content

    def _parse_and_schema_validate(self, raw: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMResolutionError(f"JSON 解析失败：{exc}") from exc
        try:
            self.schema_validator.validate(payload)
        except ValidationError as exc:
            path = ".".join(str(part) for part in exc.absolute_path)
            location = path or "<root>"
            raise LLMResolutionError(f"Schema 校验失败：{location}: {exc.message}") from exc
        return payload

    def _payload_to_resolution(self, query: str, payload: dict[str, Any], context: list[CandidateContext]) -> Resolution:
        context_by_id = {item.candidate_id: item for item in context}
        selected: list[AssetCandidate] = []

        for item in payload["candidates"]:
            candidate_id = item["candidate_id"]
            if candidate_id not in context_by_id:
                raise LLMResolutionError(f"候选校验失败：candidate_id {candidate_id} 不在候选上下文中。")
            context_item = context_by_id[candidate_id]
            if item["symbol"] != context_item.candidate.symbol or item["name"] != context_item.candidate.name:
                raise LLMResolutionError(f"候选校验失败：{candidate_id} 的代码或名称与上下文不一致。")
            if item["asset_type"] != context_item.llm_asset_type:
                raise LLMResolutionError(f"候选校验失败：{candidate_id} 的资产类型与上下文不一致。")
            selected.append(
                AssetCandidate(
                    asset_type=context_item.candidate.asset_type,
                    symbol=context_item.candidate.symbol,
                    name=context_item.candidate.name,
                    score=float(item["confidence"]),
                    reason=item["reason"],
                    metadata={**context_item.candidate.metadata, "candidate_id": candidate_id, "llm_validated": True},
                )
            )

        primary_id = payload["primary_candidate_id"]
        primary: AssetCandidate | None = None
        if primary_id:
            if primary_id not in {item.metadata.get("candidate_id") for item in selected}:
                raise LLMResolutionError("候选校验失败：primary_candidate_id 不在输出 candidates 中。")
            primary = next(item for item in selected if item.metadata.get("candidate_id") == primary_id)

        needs_clarification = bool(payload["needs_clarification"])
        if primary and primary.score < self.min_confidence:
            needs_clarification = True
        if needs_clarification:
            primary = None

        asset_type = primary.asset_type if primary else from_llm_asset_type(payload["asset_type"])
        clarification = payload["clarification_question"]
        if needs_clarification and not clarification:
            clarification = "请确认你想分析的是下面哪个候选标的？"

        return Resolution(
            query=query,
            asset_type=asset_type,
            primary=primary,
            candidates=sorted(selected, key=lambda item: item.score, reverse=True),
            explanation=payload["explanation"],
            needs_clarification=needs_clarification,
            clarification_question=clarification,
        )


def to_llm_asset_type(asset_type: AssetType) -> str:
    if asset_type == AssetType.A_STOCK:
        return "stock"
    if asset_type == AssetType.INDUSTRY_INDEX:
        return "industry_index"
    if asset_type in (AssetType.INDEX, AssetType.MARKET):
        return "index"
    return "unknown"


def from_llm_asset_type(asset_type: str) -> AssetType:
    mapping = {
        "stock": AssetType.A_STOCK,
        "index": AssetType.INDEX,
        "industry_index": AssetType.INDUSTRY_INDEX,
        "unknown": AssetType.UNKNOWN,
    }
    return mapping.get(asset_type, AssetType.UNKNOWN)


def find_aliases(candidate: AssetCandidate) -> list[str]:
    aliases = [alias for alias, (symbol, name, _, _) in INDEX_ALIASES.items() if symbol == candidate.symbol or name == candidate.name]
    for keyword, candidates in INDUSTRY_HINTS.items():
        if any(item.symbol == candidate.symbol and item.name == candidate.name for item in candidates):
            aliases.append(keyword)
    return sorted(set(aliases))


def format_retry_error(exc: Exception) -> str:
    message = str(exc)
    if len(message) > 1200:
        message = message[:1200] + "..."
    return f"{exc.__class__.__name__}: {message}"

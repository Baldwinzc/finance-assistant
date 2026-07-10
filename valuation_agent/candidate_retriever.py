from __future__ import annotations

import re
from difflib import SequenceMatcher

from valuation_agent.models import AssetCandidate, AssetType


INDEX_ALIASES: dict[str, tuple[str, str, AssetType, dict[str, str]]] = {
    "沪深300": ("000300.SH", "沪深300", AssetType.INDEX, {"ak_symbol": "沪深300"}),
    "沪深三百": ("000300.SH", "沪深300", AssetType.INDEX, {"ak_symbol": "沪深300"}),
    "hs300": ("000300.SH", "沪深300", AssetType.INDEX, {"ak_symbol": "沪深300"}),
    "中证500": ("000905.SH", "中证500", AssetType.INDEX, {"ak_symbol": "中证500"}),
    "zz500": ("000905.SH", "中证500", AssetType.INDEX, {"ak_symbol": "中证500"}),
    "中证1000": ("000852.SH", "中证1000", AssetType.INDEX, {"ak_symbol": "中证1000"}),
    "上证50": ("000016.SH", "上证50", AssetType.INDEX, {"ak_symbol": "上证50"}),
    "上证五十": ("000016.SH", "上证50", AssetType.INDEX, {"ak_symbol": "上证50"}),
    "创业板50": ("399673.SZ", "创业板50", AssetType.INDEX, {"ak_symbol": "创业板50"}),
    "创业板五十": ("399673.SZ", "创业板50", AssetType.INDEX, {"ak_symbol": "创业板50"}),
    "上证红利": ("000015.SH", "上证红利", AssetType.INDEX, {"ak_symbol": "上证红利"}),
    "深证红利": ("399324.SZ", "深证红利", AssetType.INDEX, {"ak_symbol": "深证红利"}),
    "深证100": ("399330.SZ", "深证100", AssetType.INDEX, {"ak_symbol": "深证100"}),
    "中证800": ("000906.SH", "中证800", AssetType.INDEX, {"ak_symbol": "中证800"}),
    "中证100": ("000903.SH", "中证100", AssetType.INDEX, {"ak_symbol": "中证100"}),
    "上证180": ("000010.SH", "上证180", AssetType.INDEX, {"ak_symbol": "上证180"}),
    "上证380": ("000009.SH", "上证380", AssetType.INDEX, {"ak_symbol": "上证380"}),
    "上证指数": ("000001.SH", "上证指数", AssetType.MARKET, {"market": "上海"}),
    "上证综指": ("000001.SH", "上证指数", AssetType.MARKET, {"market": "上海"}),
    "大盘": ("000001.SH", "上证指数", AssetType.MARKET, {"market": "上海"}),
    "深证成指": ("399001.SZ", "深证成指", AssetType.MARKET, {"market": "深圳"}),
    "创业板指": ("399006.SZ", "创业板指", AssetType.MARKET, {"market": "创业板"}),
    "科创板": ("000688.SH", "科创板", AssetType.MARKET, {"market": "科创板"}),
}


INDUSTRY_HINTS: dict[str, list[AssetCandidate]] = {
    "医疗": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "399989.SZ", "中证医疗", 0.95, "医疗主题行业指数"),
        AssetCandidate(AssetType.INDUSTRY_INDEX, "000991.SH", "全指医药", 0.86, "医药行业指数，医疗方向相关"),
    ],
    "医药": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "000991.SH", "全指医药", 0.95, "医药行业指数"),
        AssetCandidate(AssetType.INDUSTRY_INDEX, "399989.SZ", "中证医疗", 0.78, "医药行业中的医疗细分方向"),
    ],
    "白酒": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "399997.SZ", "中证白酒", 0.95, "白酒主题行业指数"),
    ],
    "半导体": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "990001.CSI", "中证半导体", 0.78, "半导体主题行业指数候选"),
    ],
    "新能源": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "930997.CSI", "中证新能源", 0.86, "新能源主题行业指数候选"),
        AssetCandidate(AssetType.INDUSTRY_INDEX, "931151.CSI", "光伏产业", 0.75, "新能源细分方向行业指数候选"),
    ],
    "证券": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "399975.SZ", "证券公司", 0.9, "证券行业指数候选"),
    ],
    "银行": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "399986.SZ", "中证银行", 0.9, "银行行业指数候选"),
    ],
    "消费": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "000932.SH", "中证消费", 0.86, "主要消费行业指数候选"),
        AssetCandidate(AssetType.INDUSTRY_INDEX, "000931.SH", "中证可选", 0.72, "可选消费行业指数候选"),
    ],
    "军工": [
        AssetCandidate(AssetType.INDUSTRY_INDEX, "399967.SZ", "中证军工", 0.9, "军工主题行业指数候选"),
    ],
}


CODE_PATTERN = re.compile(r"^(?:sh|sz)?(?P<code>\d{6})(?:\.(?:sh|sz))?$", re.IGNORECASE)
ETF_PATTERN = re.compile(r"^(?:sh|sz)?(?P<code>5\d{5}|1\d{5})(?:\.(?:sh|sz))?$", re.IGNORECASE)


class CandidateRetriever:
    """Build verifiable candidate context for the LLM prompt."""

    def __init__(self, stock_catalog: list[AssetCandidate] | None = None) -> None:
        self.stock_catalog = stock_catalog or []
        self.index_candidates = self._build_index_candidates()

    def collect(self, query: str, limit: int = 12) -> list[AssetCandidate]:
        normalized = normalize_query(query)
        if not normalized:
            return []

        candidates: list[AssetCandidate] = []
        direct = self.find_direct_code(normalized)
        if direct and direct.asset_type != AssetType.ETF:
            candidates.append(direct)

        candidates.extend(self.find_industry_candidates(normalized))

        index = self.find_index(normalized, exact=False)
        if index:
            candidates.append(index)

        if self.stock_catalog:
            candidates.extend(self.top_from_catalog(normalized, self.stock_catalog, limit=5))

        for candidate in self.index_candidates:
            if normalized in candidate.name.lower() or normalized in candidate.symbol.lower():
                candidates.append(candidate)

        return dedupe_candidates(candidates, limit=limit)

    def _build_index_candidates(self) -> list[AssetCandidate]:
        seen: set[tuple[str, str]] = set()
        candidates: list[AssetCandidate] = []
        for alias, (symbol, name, asset_type, metadata) in INDEX_ALIASES.items():
            key = (symbol, name)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(AssetCandidate(asset_type, symbol, name, 1.0, f"指数别名：{alias}", metadata))
        return candidates

    def find_direct_code(self, normalized: str) -> AssetCandidate | None:
        match = CODE_PATTERN.match(normalized)
        if not match:
            return None
        code = match.group("code")
        if ETF_PATTERN.match(normalized):
            return AssetCandidate(AssetType.ETF, code, f"ETF {code}", 1.0, "识别为场内 ETF 代码")
        suffix = infer_a_share_suffix(code)
        return AssetCandidate(AssetType.A_STOCK, f"{code}.{suffix}", code, 1.0, "候选来自 A 股代码格式", {"raw_code": code})

    def find_industry_candidates(self, normalized: str) -> list[AssetCandidate]:
        if not any(token in normalized for token in ("行业", "板块", "主题", "赛道")):
            return []
        for keyword, candidates in INDUSTRY_HINTS.items():
            if keyword in normalized:
                return candidates

        keyword_scores = [(keyword, similarity(normalized, keyword)) for keyword in INDUSTRY_HINTS]
        keyword_scores.sort(key=lambda item: item[1], reverse=True)
        if keyword_scores and keyword_scores[0][1] >= 0.35:
            return INDUSTRY_HINTS[keyword_scores[0][0]]
        return []

    def find_index(self, normalized: str, exact: bool = False) -> AssetCandidate | None:
        if normalized in INDEX_ALIASES:
            symbol, name, asset_type, metadata = INDEX_ALIASES[normalized]
            return AssetCandidate(asset_type, symbol, name, 1.0, "命中指数别名", metadata)

        best: AssetCandidate | None = None
        best_score = 0.0
        for candidate in self.index_candidates:
            score = max(similarity(normalized, candidate.name), similarity(normalized, candidate.symbol.lower()))
            if score > best_score:
                best = AssetCandidate(candidate.asset_type, candidate.symbol, candidate.name, score, "指数名称模糊匹配", candidate.metadata)
                best_score = score
        threshold = 0.92 if exact else 0.68
        if best and best_score >= threshold:
            return best
        return None

    def top_from_catalog(self, normalized: str, catalog: list[AssetCandidate], limit: int = 5) -> list[AssetCandidate]:
        scored: list[AssetCandidate] = []
        for candidate in catalog:
            symbol = candidate.symbol.lower()
            score = max(similarity(normalized, candidate.name), similarity(normalized, symbol))
            if normalized in candidate.name.lower() or normalized in symbol:
                score = max(score, 0.95)
            if score >= 0.45:
                scored.append(
                    AssetCandidate(
                        candidate.asset_type,
                        candidate.symbol,
                        candidate.name,
                        score,
                        f"候选召回相似度 {score:.0%}",
                        candidate.metadata,
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]


def dedupe_candidates(candidates: list[AssetCandidate], limit: int) -> list[AssetCandidate]:
    seen: set[tuple[AssetType, str, str]] = set()
    unique: list[AssetCandidate] = []
    for candidate in candidates:
        if candidate.asset_type == AssetType.ETF:
            continue
        key = (candidate.asset_type, candidate.symbol, candidate.name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return unique


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", "", query.strip().lower())


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right.lower()).ratio()


def infer_a_share_suffix(code: str) -> str:
    if code.startswith(("6", "9")):
        return "SH"
    return "SZ"

from __future__ import annotations

import re
from difflib import SequenceMatcher

from valuation_agent.models import AssetCandidate, AssetType, Resolution


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
        AssetCandidate(AssetType.INDUSTRY_QUERY, "399989.SZ", "中证医疗", 0.95, "医疗主题指数，适合先确认是否有可用估值源"),
        AssetCandidate(AssetType.ETF, "512170", "医疗ETF", 0.9, "常见医疗主题 ETF，可用于观察价格和交易载体"),
        AssetCandidate(AssetType.ETF, "512010", "医药ETF", 0.82, "医药主题 ETF，和医疗方向高度相关"),
    ],
    "医药": [
        AssetCandidate(AssetType.INDUSTRY_QUERY, "000991.SH", "全指医药", 0.95, "医药行业指数，适合观察行业整体位置"),
        AssetCandidate(AssetType.ETF, "512010", "医药ETF", 0.9, "常见医药主题 ETF，可用于观察价格和交易载体"),
        AssetCandidate(AssetType.ETF, "159938", "医药卫生ETF", 0.82, "医药卫生主题 ETF 候选"),
    ],
    "白酒": [
        AssetCandidate(AssetType.ETF, "512690", "酒ETF", 0.9, "白酒/酒类主题 ETF，可用于观察交易价格"),
        AssetCandidate(AssetType.INDUSTRY_QUERY, "399997.SZ", "中证白酒", 0.88, "白酒主题指数，适合进一步接入估值数据源"),
    ],
    "半导体": [
        AssetCandidate(AssetType.ETF, "512480", "半导体ETF", 0.9, "半导体主题 ETF，可用于观察价格和成交"),
        AssetCandidate(AssetType.ETF, "159995", "芯片ETF", 0.85, "芯片主题 ETF 候选"),
    ],
    "新能源": [
        AssetCandidate(AssetType.ETF, "516160", "新能源ETF", 0.9, "新能源主题 ETF 候选"),
        AssetCandidate(AssetType.ETF, "515790", "光伏ETF", 0.82, "新能源细分方向 ETF 候选"),
    ],
    "证券": [
        AssetCandidate(AssetType.ETF, "512880", "证券ETF", 0.9, "证券行业 ETF，可用于观察交易价格"),
    ],
    "银行": [
        AssetCandidate(AssetType.ETF, "512800", "银行ETF", 0.9, "银行行业 ETF，可用于观察交易价格"),
    ],
    "消费": [
        AssetCandidate(AssetType.ETF, "159928", "消费ETF", 0.9, "主要消费主题 ETF 候选"),
        AssetCandidate(AssetType.ETF, "515650", "消费50ETF", 0.82, "消费龙头方向 ETF 候选"),
    ],
    "军工": [
        AssetCandidate(AssetType.ETF, "512660", "军工ETF", 0.9, "军工主题 ETF，可用于观察价格"),
    ],
}


CODE_PATTERN = re.compile(r"^(?:sh|sz)?(?P<code>\d{6})(?:\.(?:sh|sz))?$", re.IGNORECASE)
ETF_PATTERN = re.compile(r"^(?:sh|sz)?(?P<code>5\d{5}|1\d{5})(?:\.(?:sh|sz))?$", re.IGNORECASE)


class Brain:
    """Rule and fuzzy based resolver for Chinese investment queries."""

    def __init__(self, stock_catalog: list[AssetCandidate] | None = None) -> None:
        self.stock_catalog = stock_catalog or []
        self.index_candidates = self._build_index_candidates()

    def resolve(self, query: str) -> Resolution:
        normalized = normalize_query(query)
        if not normalized:
            return Resolution(query, AssetType.UNKNOWN, None, [], "请输入股票、指数或行业关键词。")

        direct = self._resolve_direct_code(normalized)
        if direct:
            return Resolution(query, direct.asset_type, direct, [direct], f"识别为{asset_type_label(direct.asset_type)}：{direct.display_name}。")

        industry = self._resolve_industry(normalized)
        if industry:
            return industry

        exact_index = self._resolve_index(normalized, exact=True)
        if exact_index:
            return Resolution(query, exact_index.asset_type, exact_index, [exact_index], f"识别为指数：{exact_index.display_name}。")

        stock = self._resolve_stock_name(normalized)
        if stock:
            return Resolution(query, stock.asset_type, stock, [stock], f"识别为 A 股个股：{stock.display_name}。")

        fuzzy = self._fuzzy_candidates(normalized)
        if fuzzy:
            primary = fuzzy[0]
            explanation = f"没有完全命中，按相似度推测最可能是：{primary.display_name}。"
            return Resolution(query, primary.asset_type, primary, fuzzy[:5], explanation)

        return Resolution(query, AssetType.UNKNOWN, None, [], "暂时无法判断标的，请尝试输入更完整的股票代码、股票名称或指数名称。")

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

    def _resolve_direct_code(self, normalized: str) -> AssetCandidate | None:
        match = CODE_PATTERN.match(normalized)
        if not match:
            return None
        code = match.group("code")
        if ETF_PATTERN.match(normalized):
            return AssetCandidate(AssetType.ETF, code, f"ETF {code}", 1.0, "识别为场内 ETF 代码")
        suffix = infer_a_share_suffix(code)
        return AssetCandidate(AssetType.A_STOCK, f"{code}.{suffix}", code, 1.0, "识别为 A 股代码", {"raw_code": code})

    def _resolve_industry(self, normalized: str) -> Resolution | None:
        if not any(token in normalized for token in ("行业", "板块", "主题", "赛道")):
            return None
        for keyword, candidates in INDUSTRY_HINTS.items():
            if keyword in normalized:
                primary = candidates[0]
                return Resolution(
                    normalized,
                    AssetType.INDUSTRY_QUERY,
                    primary,
                    candidates,
                    f"识别为“{keyword}”相关行业/主题查询，优先给出指数和 ETF 候选。",
                )
        keyword_scores = [(keyword, similarity(normalized, keyword)) for keyword in INDUSTRY_HINTS]
        keyword_scores.sort(key=lambda item: item[1], reverse=True)
        if keyword_scores and keyword_scores[0][1] >= 0.35:
            keyword = keyword_scores[0][0]
            candidates = INDUSTRY_HINTS[keyword]
            return Resolution(
                normalized,
                AssetType.INDUSTRY_QUERY,
                candidates[0],
                candidates,
                f"识别为行业/主题查询，最接近“{keyword}”。",
            )
        return None

    def _resolve_index(self, normalized: str, exact: bool = False) -> AssetCandidate | None:
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

    def _resolve_stock_name(self, normalized: str) -> AssetCandidate | None:
        if not self.stock_catalog:
            return None
        best = self._best_from_catalog(normalized, self.stock_catalog)
        if best and best.score >= 0.82:
            return best
        return None

    def _fuzzy_candidates(self, normalized: str) -> list[AssetCandidate]:
        candidates: list[AssetCandidate] = []
        index = self._resolve_index(normalized, exact=False)
        if index:
            candidates.append(index)
        if self.stock_catalog:
            candidates.extend(self._top_from_catalog(normalized, self.stock_catalog, limit=4))
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates

    def _best_from_catalog(self, normalized: str, catalog: list[AssetCandidate]) -> AssetCandidate | None:
        top = self._top_from_catalog(normalized, catalog, limit=1)
        return top[0] if top else None

    def _top_from_catalog(self, normalized: str, catalog: list[AssetCandidate], limit: int = 5) -> list[AssetCandidate]:
        scored: list[AssetCandidate] = []
        for candidate in catalog:
            score = max(similarity(normalized, candidate.name), similarity(normalized, candidate.symbol.lower()))
            if normalized in candidate.name.lower():
                score = max(score, 0.95)
            if score >= 0.45:
                scored.append(
                    AssetCandidate(
                        candidate.asset_type,
                        candidate.symbol,
                        candidate.name,
                        score,
                        f"相似度 {score:.0%}",
                        candidate.metadata,
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", "", query.strip().lower())


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right.lower()).ratio()


def infer_a_share_suffix(code: str) -> str:
    if code.startswith(("6", "9")):
        return "SH"
    return "SZ"


def asset_type_label(asset_type: AssetType) -> str:
    labels = {
        AssetType.A_STOCK: "A 股个股",
        AssetType.INDEX: "指数",
        AssetType.MARKET: "市场指数",
        AssetType.ETF: "ETF",
        AssetType.INDUSTRY_QUERY: "行业/主题",
        AssetType.UNKNOWN: "未知对象",
    }
    return labels[asset_type]


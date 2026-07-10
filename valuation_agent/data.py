from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import pandas as pd

from valuation_agent.models import AssetCandidate, AssetType


class DataFetchError(RuntimeError):
    pass


@dataclass
class DataSource:
    """Fetch and normalize valuation data from AkShare."""

    akshare_loader: Callable[[], object] | None = None

    def fetch_stock_catalog(self) -> list[AssetCandidate]:
        ak = self._ak()
        try:
            raw = ak.stock_info_a_code_name()
        except Exception as exc:  # pragma: no cover - network/provider protection
            raise DataFetchError(f"获取 A 股股票列表失败：{exc}") from exc

        code_col = pick_column(raw, ["code", "证券代码", "代码"])
        name_col = pick_column(raw, ["name", "证券简称", "名称"])
        if not code_col or not name_col:
            return []

        catalog: list[AssetCandidate] = []
        for _, row in raw.iterrows():
            code = str(row[code_col]).zfill(6)
            name = str(row[name_col])
            suffix = "SH" if code.startswith(("6", "9")) else "SZ"
            catalog.append(AssetCandidate(AssetType.A_STOCK, f"{code}.{suffix}", name, 1.0, "A 股股票列表", {"raw_code": code}))
        return catalog

    def fetch_history(self, candidate: AssetCandidate, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        if candidate.asset_type == AssetType.A_STOCK:
            return self.fetch_a_stock(candidate, start, end)
        if candidate.asset_type == AssetType.INDEX:
            return self.fetch_index(candidate, start, end)
        if candidate.asset_type == AssetType.MARKET:
            return self.fetch_market(candidate, start, end)
        if candidate.asset_type == AssetType.ETF:
            return self.fetch_etf_price(candidate, start, end)
        raise DataFetchError(f"暂不支持直接获取 {candidate.display_name} 的历史估值。")

    def fetch_a_stock(self, candidate: AssetCandidate, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        ak = self._ak()
        raw_code = candidate.metadata.get("raw_code") or candidate.symbol[:6]
        try:
            raw = ak.stock_value_em(symbol=raw_code)
        except Exception as exc:  # pragma: no cover - network/provider protection
            raise DataFetchError(f"获取个股估值失败：{exc}") from exc

        frame = normalize_stock_value_frame(raw)
        frame["symbol"] = candidate.symbol
        frame["name"] = candidate.name
        return apply_date_filter(frame, start, end)

    def fetch_index(self, candidate: AssetCandidate, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        ak = self._ak()
        symbol = candidate.metadata.get("ak_symbol", candidate.name)
        try:
            pe_raw = ak.stock_index_pe_lg(symbol=symbol)
            pb_raw = ak.stock_index_pb_lg(symbol=symbol)
        except Exception as exc:  # pragma: no cover - network/provider protection
            raise DataFetchError(f"获取指数估值失败：{exc}") from exc

        frame = merge_index_valuation_frames(pe_raw, pb_raw)
        frame["symbol"] = candidate.symbol
        frame["name"] = candidate.name
        return apply_date_filter(frame, start, end)

    def fetch_market(self, candidate: AssetCandidate, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        ak = self._ak()
        market = candidate.metadata.get("market", candidate.name)
        try:
            pe_raw = ak.stock_market_pe_lg(symbol=market)
            pb_raw = ak.stock_market_pb_lg(symbol=market)
        except Exception as exc:  # pragma: no cover - network/provider protection
            raise DataFetchError(f"获取市场估值失败：{exc}") from exc

        frame = merge_market_valuation_frames(pe_raw, pb_raw)
        frame["symbol"] = candidate.symbol
        frame["name"] = candidate.name
        return apply_date_filter(frame, start, end)

    def fetch_etf_price(self, candidate: AssetCandidate, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        ak = self._ak()
        start_arg = compact_date(start) if start else "20000101"
        end_arg = compact_date(end) if end else compact_date(date.today().isoformat())
        try:
            raw = ak.fund_etf_hist_em(symbol=candidate.symbol[:6], period="daily", start_date=start_arg, end_date=end_arg, adjust="qfq")
        except Exception as exc:  # pragma: no cover - network/provider protection
            raise DataFetchError(f"获取 ETF 价格失败：{exc}") from exc

        frame = normalize_etf_price_frame(raw)
        frame["symbol"] = candidate.symbol
        frame["name"] = candidate.name
        return apply_date_filter(frame, start, end)

    def _ak(self) -> object:
        if self.akshare_loader is not None:
            return self.akshare_loader()
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment protection
            raise DataFetchError("缺少依赖 akshare，请先运行：pip install -r requirements.txt") from exc
        return ak


def normalize_stock_value_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise DataFetchError("数据源返回空数据。")

    mapping = {
        "date": ["日期", "date", "trade_date"],
        "close": ["收盘价", "close", "最新价"],
        "pe_ttm": ["市盈率(TTM)", "PE(TTM)", "pe_ttm", "市盈率ttm"],
        "pe": ["市盈率(静)", "市盈率", "pe"],
        "pb": ["市净率", "PB", "pb"],
        "ps": ["市销率", "PS", "ps"],
        "total_mv": ["总市值", "total_mv"],
    }
    return standardize_columns(raw, mapping)


def merge_index_valuation_frames(pe_raw: pd.DataFrame, pb_raw: pd.DataFrame) -> pd.DataFrame:
    pe = standardize_columns(
        pe_raw,
        {
            "date": ["日期", "date", "trade_date"],
            "close": ["指数", "指数点位", "收盘", "close"],
            "pe": ["静态市盈率", "市盈率", "pe"],
            "pe_ttm": ["滚动市盈率", "市盈率TTM", "pe_ttm", "等权滚动市盈率"],
        },
    )
    pb = standardize_columns(
        pb_raw,
        {
            "date": ["日期", "date", "trade_date"],
            "pb": ["市净率", "pb", "等权市净率"],
            "close": ["指数", "指数点位", "收盘", "close"],
        },
    )
    merged = pd.merge(pe, pb[["date", "pb"]], on="date", how="outer")
    if "close" not in merged.columns and "close_x" in merged.columns:
        merged["close"] = merged["close_x"]
    return finalize_frame(merged)


def merge_market_valuation_frames(pe_raw: pd.DataFrame, pb_raw: pd.DataFrame) -> pd.DataFrame:
    pe = standardize_columns(
        pe_raw,
        {
            "date": ["日期", "date"],
            "pe": ["平均市盈率", "市盈率", "pe"],
            "close": ["指数", "收盘", "close"],
        },
    )
    pb = standardize_columns(
        pb_raw,
        {
            "date": ["日期", "date"],
            "pb": ["平均市净率", "市净率", "pb"],
            "close": ["指数", "收盘", "close"],
        },
    )
    merged = pd.merge(pe, pb[["date", "pb"]], on="date", how="outer")
    return finalize_frame(merged)


def normalize_etf_price_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = standardize_columns(
        raw,
        {
            "date": ["日期", "date"],
            "close": ["收盘", "收盘价", "close"],
            "volume": ["成交量", "volume"],
            "amount": ["成交额", "amount"],
        },
    )
    return finalize_frame(frame)


def standardize_columns(raw: pd.DataFrame, mapping: dict[str, list[str]]) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise DataFetchError("数据源返回空数据。")

    frame = raw.copy()
    rename: dict[str, str] = {}
    used_sources: set[str] = set()
    for target, candidates in mapping.items():
        source = pick_column(frame, candidates, used_sources)
        if source:
            rename[source] = target
            used_sources.add(source)
    frame = frame.rename(columns=rename)

    if "date" not in frame.columns:
        raise DataFetchError(f"无法识别日期字段，可用字段：{list(raw.columns)}")

    keep = [column for column in ["date", "close", "pe_ttm", "pe", "pb", "ps", "total_mv", "volume", "amount"] if column in frame.columns]
    return finalize_frame(frame[keep])


def finalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result = result.dropna(subset=["date"]).sort_values("date")

    for column in result.columns:
        if column != "date":
            converted = pd.to_numeric(result[column], errors="coerce")
            if converted.notna().sum() > 0:
                result[column] = converted

    result = result.drop_duplicates(subset=["date"], keep="last")
    result = result.reset_index(drop=True)
    if result.empty:
        raise DataFetchError("清洗后没有可用历史数据。")
    return result


def apply_date_filter(frame: pd.DataFrame, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    result = frame.copy()
    if start:
        result = result[result["date"] >= pd.to_datetime(start)]
    if end:
        result = result[result["date"] <= pd.to_datetime(end)]
    result = result.reset_index(drop=True)
    if result.empty:
        raise DataFetchError("指定日期范围内没有可用数据。")
    return result


def pick_column(frame: pd.DataFrame, candidates: list[str], used_sources: set[str] | None = None) -> str | None:
    used_sources = used_sources or set()
    available_columns = [column for column in frame.columns if column not in used_sources]
    normalized = {normalize_col(column): column for column in available_columns}
    for candidate in candidates:
        hit = normalized.get(normalize_col(candidate))
        if hit:
            return hit
    for column in available_columns:
        text = normalize_col(column)
        if any(normalize_col(candidate) in text for candidate in candidates):
            return column
    return None


def normalize_col(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "")


def compact_date(value: str) -> str:
    return value.replace("-", "")

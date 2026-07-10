from __future__ import annotations

from datetime import date

from valuation_agent.brain import Brain
from valuation_agent.charts import build_valuation_chart, summarize_valuation
from valuation_agent.data import DataFetchError, DataSource
from valuation_agent.models import AnalysisResult, AssetType


class ValuationAgent:
    def __init__(self, data_source: DataSource | None = None, load_live_catalog: bool = True) -> None:
        self.data_source = data_source or DataSource()
        stock_catalog = []
        if load_live_catalog:
            try:
                stock_catalog = self.data_source.fetch_stock_catalog()
            except DataFetchError:
                stock_catalog = []
        self.brain = Brain(stock_catalog=stock_catalog)

    def analyze(self, query: str, start: str | None = None, end: str | None = None) -> AnalysisResult:
        resolution = self.brain.resolve(query)
        result = AnalysisResult(resolution=resolution)

        if not resolution.primary:
            result.warnings.append("没有识别出明确标的，暂不获取数据。")
            return result

        if resolution.asset_type == AssetType.INDUSTRY_QUERY:
            result.warnings.append("行业主题查询已给出候选。若候选没有公开 PE/PB 历史源，建议选择对应指数或 ETF 进一步分析。")

        try:
            frame = self.data_source.fetch_history(resolution.primary, start=start, end=end or date.today().isoformat())
        except DataFetchError as exc:
            result.warnings.append(str(exc))
            return result

        result.data = frame
        result.summary = summarize_valuation(frame)
        title = f"{resolution.primary.display_name} 历史估值与价格"
        result.figure = build_valuation_chart(frame, title=title)

        if not result.summary:
            result.warnings.append("已获取价格数据，但没有可用的 PE/PB 历史字段。")
        return result


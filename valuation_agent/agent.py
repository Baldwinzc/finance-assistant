from __future__ import annotations

from datetime import date

from valuation_agent.charts import build_valuation_chart, summarize_valuation
from valuation_agent.data import DataFetchError, DataSource
from valuation_agent.llm_brain import LLMBrain
from valuation_agent.models import AnalysisResult, AssetType


class ValuationAgent:
    def __init__(
        self,
        data_source: DataSource | None = None,
        load_live_catalog: bool = True,
    ) -> None:
        self.data_source = data_source or DataSource()
        stock_catalog = []
        if load_live_catalog:
            try:
                stock_catalog = self.data_source.fetch_stock_catalog()
            except DataFetchError:
                stock_catalog = []
        self.brain = LLMBrain(stock_catalog=stock_catalog)

    def resolve(self, query: str, history: list[dict[str, str]] | None = None):
        return self.brain.resolve(query, conversation_history=history)

    def analyze(self, query: str, start: str | None = None, end: str | None = None) -> AnalysisResult:
        resolution = self.resolve(query)
        result = AnalysisResult(resolution=resolution)

        if not resolution.primary:
            if resolution.needs_clarification:
                result.warnings.append("需要先确认标的，暂不获取数据和绘图。")
            else:
                result.warnings.append("没有识别出明确标的，暂不获取数据。")
            return result

        if resolution.asset_type == AssetType.INDUSTRY_INDEX:
            result.warnings.append("已识别为行业指数；行业指数估值数据源将在下一步接入，本轮先完成 LLM 判断。")
            return result

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

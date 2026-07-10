from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssetType(str, Enum):
    A_STOCK = "a_stock"
    INDEX = "index"
    INDUSTRY_INDEX = "industry_index"
    MARKET = "market"
    ETF = "etf"
    INDUSTRY_QUERY = "industry_query"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AssetCandidate:
    asset_type: AssetType
    symbol: str
    name: str
    score: float = 1.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.symbol and self.symbol != self.name:
            return f"{self.name}（{self.symbol}）"
        return self.name


@dataclass
class Resolution:
    query: str
    asset_type: AssetType
    primary: AssetCandidate | None
    candidates: list[AssetCandidate]
    explanation: str
    needs_clarification: bool = False
    clarification_question: str = ""
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValuationSummary:
    metric: str
    label: str
    latest: float
    percentile: float
    latest_text: str
    percentile_text: str
    zone: str


@dataclass
class AnalysisResult:
    resolution: Resolution
    data: Any | None = None
    figure: Any | None = None
    summary: list[ValuationSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

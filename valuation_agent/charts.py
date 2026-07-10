from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from valuation_agent.models import ValuationSummary


VALUATION_COLUMNS = [
    ("pe_ttm", "PE(TTM)"),
    ("pe", "PE"),
    ("pb", "PB"),
]


def build_valuation_chart(frame: pd.DataFrame, title: str) -> go.Figure:
    metrics = available_metrics(frame)
    rows = 1 + len(metrics)
    figure = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.42] + [0.58 / max(len(metrics), 1)] * len(metrics),
        subplot_titles=["价格"] + [label for _, label in metrics],
    )

    if "close" in frame.columns:
        figure.add_trace(go.Scatter(x=frame["date"], y=frame["close"], name="价格", line=dict(color="#2563eb", width=1.8)), row=1, col=1)

    for index, (column, label) in enumerate(metrics, start=2):
        series = clean_metric(frame[column])
        figure.add_trace(go.Scatter(x=frame["date"], y=series, name=label, line=dict(width=1.6)), row=index, col=1)
        for percentile, color, dash in [(0.1, "#16a34a", "dot"), (0.5, "#64748b", "dash"), (0.9, "#dc2626", "dot")]:
            value = series.quantile(percentile)
            if pd.notna(value):
                figure.add_hline(y=float(value), line_color=color, line_dash=dash, line_width=1, row=index, col=1)

    figure.update_layout(
        title=title,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=48, r=24, t=72, b=40),
        template="plotly_white",
        height=360 + 180 * len(metrics),
    )
    figure.update_xaxes(showgrid=True, gridcolor="#e5e7eb")
    figure.update_yaxes(showgrid=True, gridcolor="#e5e7eb")
    return figure


def summarize_valuation(frame: pd.DataFrame) -> list[ValuationSummary]:
    summaries: list[ValuationSummary] = []
    for column, label in available_metrics(frame):
        series = clean_metric(frame[column])
        if series.empty:
            continue
        latest = float(series.iloc[-1])
        percentile = percentile_rank(series, latest)
        summaries.append(
            ValuationSummary(
                metric=column,
                label=label,
                latest=latest,
                percentile=percentile,
                latest_text=format_number(latest),
                percentile_text=f"历史分位 {percentile:.1%}",
                zone=valuation_zone(percentile),
            )
        )
    return summaries


def available_metrics(frame: pd.DataFrame) -> list[tuple[str, str]]:
    metrics: list[tuple[str, str]] = []
    for column, label in VALUATION_COLUMNS:
        if column in frame.columns and clean_metric(frame[column]).shape[0] >= 5:
            metrics.append((column, label))
    return metrics


def percentile_rank(series: pd.Series, value: float) -> float:
    clean = clean_metric(series)
    if clean.empty or math.isnan(value):
        return float("nan")
    return float((clean <= value).sum() / len(clean))


def valuation_zone(percentile: float) -> str:
    if math.isnan(percentile):
        return "估值分位不足"
    if percentile <= 0.2:
        return "低估区：适合重点研究基本面和风险"
    if percentile <= 0.4:
        return "偏低区：可关注左侧布局机会"
    if percentile <= 0.7:
        return "合理区：需要结合增长质量判断"
    if percentile <= 0.9:
        return "偏高区：注意安全边际"
    return "高估区：谨慎追高，关注回撤风险"


def clean_metric(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce")
    clean = clean.replace([float("inf"), float("-inf")], pd.NA).dropna()
    clean = clean[clean > 0]
    return clean


def format_number(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.2f}"


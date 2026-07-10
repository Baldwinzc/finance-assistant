from __future__ import annotations

import argparse
import json
from pathlib import Path

from valuation_agent.agent import ValuationAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="中文估值分析 Agent")
    parser.add_argument("query", help="股票代码、股票名称、指数名称或行业关键词")
    parser.add_argument("--start", default=None, help="开始日期，例如 2010-01-01")
    parser.add_argument("--end", default=None, help="结束日期，例如 2026-07-10")
    parser.add_argument("--output-dir", default="reports", help="输出目录")
    parser.add_argument("--brain", choices=["auto", "llm", "rules"], default="auto", help="判断大脑：auto/llm/rules")
    parser.add_argument("--resolve-only", action="store_true", help="只运行第一步标的判断，不获取数据、不绘图")
    args = parser.parse_args()

    agent = ValuationAgent(brain_mode=args.brain)
    if args.resolve_only:
        resolution = agent.resolve(args.query)
        print_resolution(resolution)
        return

    result = agent.analyze(args.query, start=args.start, end=args.end)

    print_resolution(result.resolution)

    if result.summary:
        print("\n历史估值位置：")
        for item in result.summary:
            print(f"- {item.label}: {item.latest_text}, {item.percentile_text}, {item.zone}")

    if result.warnings:
        print("\n提示：")
        for warning in result.warnings:
            print(f"- {warning}")

    if result.data is None or result.data.empty:
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_filename(result.resolution.primary.display_name if result.resolution.primary else args.query)
    csv_path = output_dir / f"{safe_name}.csv"
    json_path = output_dir / f"{safe_name}.json"
    html_path = output_dir / f"{safe_name}.html"

    result.data.to_csv(csv_path, index=False)
    if result.figure is not None:
        result.figure.write_html(html_path)

    json_path.write_text(
        json.dumps(
            {
                "query": result.resolution.query,
                "explanation": result.resolution.explanation,
                "summary": [item.__dict__ for item in result.summary],
                "warnings": result.warnings,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n已输出：\n- {csv_path}\n- {html_path}\n- {json_path}")


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)


def print_resolution(resolution) -> None:
    print(resolution.explanation)
    if resolution.needs_clarification:
        print(f"需要确认：{resolution.clarification_question}")
    for candidate in resolution.candidates:
        print(f"候选：{candidate.display_name} - 置信度 {candidate.score:.0%} - {candidate.reason}")


if __name__ == "__main__":
    main()

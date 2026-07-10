from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from valuation_agent.agent import ValuationAgent


st.set_page_config(page_title="中文估值分析 Agent", page_icon="📈", layout="wide")

st.title("中文估值分析 Agent")
st.caption("输入股票、指数或行业关键词，查看历史 PE/PB、价格曲线和估值分位。")

query = st.text_input("你想分析什么？", value="沪深300", placeholder="例如：贵州茅台、600519、沪深三百、医疗行业")
resolve_only = st.toggle("只运行第一步判断", value=True)

col_start, col_end = st.columns(2)
with col_start:
    start = st.text_input("开始日期", value="2010-01-01")
with col_end:
    end = st.text_input("结束日期", value="")

run = st.button("开始分析", type="primary")

if run and query.strip():
    agent = ValuationAgent()
    with st.spinner("正在判断问题..." if resolve_only else "正在判断问题、获取数据并绘制估值曲线..."):
        if resolve_only:
            resolution = agent.resolve(query=query)
            result = None
        else:
            result = agent.analyze(query=query, start=start or None, end=end or None)
            resolution = result.resolution

    st.subheader("判断结果")
    st.write(resolution.explanation)
    if resolution.needs_clarification:
        st.info(resolution.clarification_question)

    if resolution.candidates:
        st.markdown("**候选对象**")
        for item in resolution.candidates:
            st.write(f"- {item.display_name}：置信度 {item.score:.0%}，{item.reason}")

    if resolve_only:
        st.stop()

    if result.summary:
        st.subheader("历史估值位置")
        metric_cols = st.columns(len(result.summary))
        for metric_col, summary in zip(metric_cols, result.summary):
            with metric_col:
                st.metric(summary.label, summary.latest_text, summary.percentile_text)
                st.caption(summary.zone)

    if result.figure is not None:
        st.subheader("历史估值曲线")
        st.plotly_chart(result.figure, use_container_width=True)

    if result.data is not None and not result.data.empty:
        st.subheader("数据预览")
        st.dataframe(result.data.tail(20), use_container_width=True)

        tmp_dir = Path(tempfile.gettempdir())
        csv_path = tmp_dir / "valuation_agent_result.csv"
        result.data.to_csv(csv_path, index=False)
        st.download_button("下载 CSV", csv_path.read_bytes(), file_name="valuation_agent_result.csv")

    if result.warnings:
        st.warning("\n".join(result.warnings))

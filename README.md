# 中文估值分析 Agent

面向价值投资和左侧交易的本地估值分析工具。你可以输入股票代码、股票名称、指数名称，或者像“医疗行业”这样的模糊行业问题，Agent 会先判断你问的是什么，再尝试获取历史股价、市盈率、市净率数据，并绘制估值曲线和历史分位。

## 能力边界

- A 股个股：默认使用 AkShare 东方财富估值接口，输出股价、PE(TTM)、PB、历史分位。
- 主流宽基/市场指数：默认使用 AkShare 乐咕乐股接口，输出指数价格、PE、PB、历史分位。
- 行业模糊查询：先给出相关行业指数、ETF 或主题候选；能拿到估值的对象会直接画图，不能拿到 PE/PB 的会说明数据限制。
- 中文交互：命令行和 Streamlit 页面均以中文为主。

> 投资判断请结合财报质量、商业模式、现金流、行业周期和风险承受能力；本项目只提供数据整理和估值位置辅助，不构成投资建议。

## 安装

建议使用 Python 3.9+。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 命令行使用

```bash
python -m valuation_agent.cli "贵州茅台" --start 2015-01-01
python -m valuation_agent.cli "沪深300" --start 2010-01-01
python -m valuation_agent.cli "医疗行业"
```

默认会在 `reports/` 下生成：

- `*.html`：交互式估值曲线
- `*.csv`：原始历史数据
- `*.json`：本次判断和历史分位摘要

## 中文网页界面

```bash
streamlit run app.py
```

打开页面后输入“600519”“贵州茅台”“沪深三百”“医疗行业”等关键词即可。

## 三步流程与检验

1. 大脑判断
   - 文件：`valuation_agent/brain.py`
   - 检验：`python -m unittest tests/test_brain.py`
   - 覆盖：代码识别、名称模糊匹配、错别字、行业模糊查询。

2. 获取信息
   - 文件：`valuation_agent/data.py`
   - 检验：`python -m unittest tests/test_data_transform.py`
   - 覆盖：AkShare 返回字段标准化、日期/估值字段统一、空数据保护。

3. 绘制估值曲线
   - 文件：`valuation_agent/charts.py`
   - 检验：`python -m unittest tests/test_charts.py`
   - 覆盖：历史分位计算、低估/合理/高估区间标签、图表生成。

完整本地测试：

```bash
python -m unittest discover -s tests
```

## 数据源说明

历史估值口径会影响结论。本项目默认：

- 个股 PE 使用 `PE(TTM)`，PB 使用市净率。
- 指数 PE/PB 使用乐咕乐股公开接口。
- 行业主题优先推荐可交易 ETF 和常见指数；若公开接口没有稳定 PE/PB 历史，Agent 会给出候选并提示数据缺口。

后续可扩展 Tushare：在 `.env` 或环境变量中设置 `TUSHARE_TOKEN` 后，可增加更完整的 A 股和指数估值覆盖。

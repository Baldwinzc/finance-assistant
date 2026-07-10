# 中文估值分析 Agent

面向价值投资和左侧交易的本地估值分析工具。你可以输入股票代码、股票名称、指数名称，或者像“医疗行业”这样的模糊行业问题，Agent 会先判断你问的是什么，再尝试获取历史股价、市盈率、市净率数据，并绘制估值曲线和历史分位。

## 能力边界

- A 股个股：默认使用 AkShare 东方财富估值接口，输出股价、PE(TTM)、PB、历史分位。
- 主流宽基/市场指数：默认使用 AkShare 乐咕乐股接口，输出指数价格、PE、PB、历史分位。
- 行业模糊查询：当前阶段优先识别行业指数；ETF 估值后续实现。
- 中文交互：命令行、Streamlit 页面和 React 聊天框。

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

只运行第一步“标的判断”，不获取数据、不画图：

```bash
python3 -m valuation_agent.cli "贵州茅台" --resolve-only
python3 -m valuation_agent.cli "医疗行业" --resolve-only
```

第一步判断统一使用 LLM 大脑，需要先在本机配置 API Key：

```bash
export OPENAI_API_KEY="你的 OpenAI API Key"
python3 -m valuation_agent.cli "沪深三百" --resolve-only
```

如果使用 OpenAI 兼容网关，可在本地私有环境中额外设置 `OPENAI_BASE_URL`。默认模型是 `gpt-4o-mini`。
也可以复制 `.env.example` 为 `.env` 或 `.env.local` 后填入私有配置；这些文件不会提交。

LLM 大脑会先让模型输出结构化 JSON，然后做本地 schema 校验和候选校验。若模型输出不是合法 JSON、schema 不匹配、候选代码不在上下文中，系统会把异常信息放回上下文中要求模型重试。置信度低于阈值时不会继续获取数据或绘图，而是要求用户确认候选。

默认会在 `reports/` 下生成：

- `*.html`：交互式估值曲线
- `*.csv`：原始历史数据
- `*.json`：本次判断和历史分位摘要

## Streamlit 界面

```bash
streamlit run app.py
```

打开页面后输入“600519”“贵州茅台”“沪深三百”“医疗行业”等关键词即可。

## React 聊天框

后端 API：

```bash
python3 -m uvicorn valuation_agent.api:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd frontend
pnpm install
pnpm dev --host 127.0.0.1 --port 5173
```

打开 `http://127.0.0.1:5173/`。当前前端只调用第一步标的判断接口 `/api/resolve`，不会获取估值数据或绘图。

## 三步流程与检验

1. 大脑判断
   - 候选召回：`valuation_agent/candidate_retriever.py`
   - LLM 结构化大脑：`valuation_agent/llm_brain.py`
   - 检验：`python3 -m unittest tests/test_candidate_retriever.py tests/test_llm_brain.py`
   - 覆盖：候选召回、代码识别、名称模糊匹配、错别字、行业指数模糊查询、JSON Schema 校验、候选校验、异常回灌重试、低置信度确认。

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

## 前端说明

React 前端位于 `frontend/`，使用 TypeScript、Tailwind CSS 和 shadcn 风格组件结构。聊天输入组件在 `frontend/src/components/ui/chat-input.tsx`，依赖 `button`、`textarea`、`use-textarea-resize`、`lucide-react`、`@radix-ui/react-slot` 和 `class-variance-authority`。

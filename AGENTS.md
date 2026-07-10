# Agent API 调用指南

这份文档给后续编写 Agent 时使用。它是仓库安全版：可以提交到远程仓库，但不能包含真实公司内部地址、控制台地址、图片链接、API Key、Bearer Token 或个人账号信息。

## 核心原则

- 真实密钥只通过环境变量、`.env`、系统 Keychain、1Password、云端 Secret Manager 等私有渠道提供。
- 真实 API Base URL 属于内部地址时，也只放在私有环境变量里，不写入代码、README、测试快照或提交记录。
- 本仓库文档和代码只使用占位符，例如 `<AI_GATEWAY_BASE_URL>`、`<YOUR_API_KEY>`、`<MODEL_NAME>`。
- 提交前运行敏感信息扫描，确认没有把内部域名、控制台地址、图片下载地址或密钥提交出去。

## 后续 Agent 使用规则

- Agent 应优先读取环境变量，不要向用户索取已经存在于环境变量里的信息。
- 缺少 `OPENAI_API_KEY` 时，只向用户索取 API Key，并提醒用户用环境变量或私有 `.env` 注入。
- 如果必须走公司内部代理但缺少 `OPENAI_BASE_URL`，Agent 只能提示用户在本地私有环境中配置，不能猜测、生成或写入真实内部地址。
- Agent 不得把用户粘贴的 Key、内部 URL、控制台链接写入 Markdown、日志、测试、提交信息或 PR 描述。
- 临时调试可以使用 shell 环境变量；需要持久化时使用 `.env` 或 `.env.local`，它们必须保持未提交状态。

## 推荐环境变量

在本地 `.env` 或 shell 中配置，`.env` 不应提交：

```bash
export OPENAI_API_KEY="<YOUR_API_KEY>"
# 可选：仅在使用兼容网关或指定模型时设置
export OPENAI_BASE_URL="<AI_GATEWAY_BASE_URL>/v1"
export VALUATION_AGENT_LLM_MODEL="<MODEL_NAME>"
```

说明：

- `OPENAI_API_KEY`：用户提供的 API Key。
- `OPENAI_BASE_URL`：可选。OpenAI 协议兼容入口，必须来自私有配置，不得写真实内部地址。
- `VALUATION_AGENT_LLM_MODEL`：可选。本项目 LLM 大脑使用的模型名，建议来自私有配置或运行时参数。

如果只使用官方 OpenAI 入口，可以不设置 `OPENAI_BASE_URL`。

## Python 调用模板

适用于 OpenAI SDK 和 OpenAI 协议兼容网关。

```python
import os
from openai import OpenAI


def build_client() -> OpenAI:
    api_key = os.environ["OPENAI_API_KEY"]
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


client = build_client()
model_name = os.getenv("VALUATION_AGENT_LLM_MODEL", "gpt-4o-mini")

response = client.responses.create(
    model=model_name,
    input=[
        {
            "role": "user",
            "content": "请用一句话说明今天要分析的标的。",
        }
    ],
)

print(response.output_text)
```

## Chat Completions 兼容模板

本项目当前的 `valuation_agent.llm_brain.LLMBrain` 使用 Chat Completions，并要求模型输出严格 JSON。

```python
import os
from openai import OpenAI


client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.getenv("OPENAI_BASE_URL"),
)
model_name = os.getenv("VALUATION_AGENT_LLM_MODEL", "gpt-4o-mini")

response = client.chat.completions.create(
    model=model_name,
    messages=[
        {"role": "system", "content": "只输出合法 JSON，不要输出 Markdown。"},
        {"role": "user", "content": "{\"query\": \"贵州茅台\"}"},
    ],
    temperature=0,
    response_format={"type": "json_object"},
)

content = response.choices[0].message.content
```

## cURL 调用模板

不要把真实地址和真实 Key 写进命令历史、脚本或文档。临时调试时优先使用环境变量。

```bash
curl "$OPENAI_BASE_URL/responses" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "'"$VALUATION_AGENT_LLM_MODEL"'",
    "input": [
      {
        "role": "user",
        "content": "用一句话解释 PE 分位数。"
      }
    ]
  }'
```

## 本项目接入方式

当前仓库的 LLM 入口在 `valuation_agent/llm_brain.py`：

- 缺少 `OPENAI_API_KEY` 时，LLM 模式会返回配置错误并要求切回 rules 模式。
- `VALUATION_AGENT_LLM_MODEL` 未设置时，会使用代码内默认模型。
- 如果使用公司或其他 OpenAI 兼容代理，在本地设置 `OPENAI_BASE_URL`，不要改代码硬编码地址。

本地运行示例：

```bash
export OPENAI_API_KEY="<YOUR_API_KEY>"
# 可选：仅在使用兼容网关或指定模型时设置
export OPENAI_BASE_URL="<AI_GATEWAY_BASE_URL>/v1"
export VALUATION_AGENT_LLM_MODEL="<MODEL_NAME>"

python3 -m valuation_agent.cli "沪深三百" --resolve-only --brain llm
```

## 多能力接口约定

当网关兼容 OpenAI 风格时，优先使用这些路径。真实 Base URL 仍然只能来自环境变量。

| 能力 | 路径占位符 | 典型用途 |
| --- | --- | --- |
| 文本/推理 | `$OPENAI_BASE_URL/responses` | Agent 对话、结构化输出、工具调用 |
| 聊天兼容 | `$OPENAI_BASE_URL/chat/completions` | 旧版 Chat Completions 代码 |
| 向量 | `$OPENAI_BASE_URL/embeddings` | 文档检索、RAG、相似度搜索 |
| 图片生成 | `$OPENAI_BASE_URL/images/generations` | 生成图片素材 |
| 语音转文字 | `$OPENAI_BASE_URL/audio/transcriptions` | 音频识别 |
| 文字转语音 | `$OPENAI_BASE_URL/audio/speech` | 语音播报 |

如果网关还支持 Anthropic Messages 协议，应另行用私有环境变量配置，示例只保留占位符：

```bash
export ANTHROPIC_BASE_URL="<AI_GATEWAY_BASE_URL>"
export ANTHROPIC_AUTH_TOKEN="<YOUR_API_KEY>"
export ANTHROPIC_MODEL="<MODEL_NAME>"
```

## 提交前安全检查

提交或推送前执行：

```bash
git diff --cached
rg -n "(sk-|api[_-]?key|authorization: bearer|bearer [a-z0-9._-]+|token|secret|password)" .
rg -n "(internal|intranet|console|corp|company-domain|<COMPANY_INTERNAL_DOMAIN_KEYWORD>)" .
```

检查结果里如果出现真实内部地址、真实域名、图片鉴权链接、API Key、Token 或账号信息，必须先移除或替换为占位符再提交。

真实公司域名、网关域名、内部文档域名等关键词只在本地临时替换 `<COMPANY_INTERNAL_DOMAIN_KEYWORD>` 使用，不要把这些关键词提交到仓库。

## 禁止提交的内容

- 真实 API Key、Token、Cookie、Session、Authorization Header。
- 真实公司内部控制台地址、内部代理地址、内部文档地址、内部图片下载地址。
- 包含真实密钥或内部地址的 `.env`、`.env.local`、私有 Markdown、截图、日志。
- 任何可以让外部人员推断内部网关位置、鉴权方式、账号体系的细节。

# LLM 开发实战项目集

十三个独立 demo，按学习顺序编号。每个 demo 用一个 Python（部分附 Go/Rust）实现，配合本地 MLX 模型或任意 OpenAI 兼容 API。

## 环境配置

每个 demo 目录需要一个 `.env` 文件。`.env` 已在 `.gitignore` 里，自己建：

```bash
API_BASE_URL=http://localhost:8000/v1
API_KEY=your_api_key_here
MODEL_ID=Qwen3.5-27B-Claude-4.6-Opus-Distilled-MLX-4bit
```

少数 demo 需要额外变量：

| demo | 额外变量 |
|------|---------|
| `08-evaluation-demo` | `JUDGE_MODEL_ID` |
| `11-fine-tuning-demo` | `BASE_MODEL`、`ADAPTER_PATH` |

切云端 API（OpenAI/Anthropic）改 `API_BASE_URL` 和 `API_KEY` 即可。

## 推荐学习顺序

| # | demo | 价值 | 说明 |
|---|------|------|------|
| 01 | [llm-function-call-demo](01-llm-function-call-demo) | ⭐⭐⭐⭐⭐ | Function Call，Agent 的基础 |
| 02 | [streaming-demo](02-streaming-demo) | ⭐⭐⭐⭐⭐ | 流式输出，生产环境必备 |
| 03 | [structured-output-demo](03-structured-output-demo) | ⭐⭐⭐⭐⭐ | JSON Schema 强制约束 |
| 04 | [mcp-demo](04-mcp-demo) | ⭐⭐⭐⭐⭐ | Function Call 的标准化演进 |
| 05 | [memory-management-demo](05-memory-management-demo) | ⭐⭐⭐⭐⭐ | 对话历史 + Token 控制 |
| 06 | [error-handling-demo](06-error-handling-demo) | ⭐⭐⭐⭐⭐ | 重试 / 断路器 / 降级 |
| 07 | [caching-demo](07-caching-demo) | ⭐⭐⭐⭐⭐ | 精确 / 语义 / 前缀缓存 |
| 08 | [evaluation-demo](08-evaluation-demo) | ⭐⭐⭐⭐⭐ | 改完之后怎么验证没退化 |
| 09 | [simple-agent-demo](09-simple-agent-demo) | ⭐⭐⭐⭐⭐ | AI 自主决策、多步执行 |
| 10 | [multi-agent-demo](10-multi-agent-demo) | ⭐⭐⭐⭐⭐ | 多 Agent 协作 |
| 11 | [fine-tuning-demo](11-fine-tuning-demo) | ⭐⭐⭐ | LoRA 微调（场景受限） |
| 12 | [hybrid-search-demo](12-hybrid-search-demo) | ⭐⭐⭐ | GREP + 向量检索（小项目不用） |
| 13 | [prompt-engineering-demo](13-prompt-engineering-demo) | ⭐⭐ | Prompt 工程（价值在下降） |

01-08 是核心，建议按顺序过一遍。09-10 看 Agent 兴趣。11-13 按需。

## 快速开始

```bash
cd 01-llm-function-call-demo
pip install -r python/requirements.txt
python python/demo.py
```

每个 demo 都有自己的 README，跑法各异，看子目录文档。

## 技术取舍

价值持续的：Function Call、MCP、Streaming、结构化输出、Agent、记忆管理、错误处理、缓存、评测。

价值下降的：Prompt Engineering（模型越来越强）、复杂 RAG（长上下文越来越长）、通用微调（被换更强基模型 + RAG 替代）。

设计原则：
- 简单方案优先（GREP 能解决就别上向量检索）
- 长期价值优先（别投入会被淘汰的技术）
- 用真实数据验证（凭直觉迭代 = 自欺欺人，所以有 evaluation-demo）

## 技术栈

- 语言：Python（全部）、Go / Rust（部分 demo 有对应实现）
- 模型：本地 MLX、或任意 OpenAI 兼容 API
- 仅需 `requests` / `python-dotenv` / `colorama` 之类轻量依赖

## License

MIT — 详见 [LICENSE](LICENSE)。

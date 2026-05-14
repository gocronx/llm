# LLM 开发实战项目集

二十个独立 demo，按学习顺序编号。每个用 Python（部分附 Go / Rust）实现，配合本地 MLX 模型或任意 OpenAI 兼容 API。

## 环境配置

每个 demo 目录都自带一个 `.env.example` 模板。`.env` 进了 `.gitignore`，所以**复制**模板而不是直接修改：

```bash
cd 01-llm-function-call-demo
cp .env.example .env
# 编辑 .env，把 API_KEY=REPLACE_WITH_YOUR_KEY 改成你自己的
```

标准变量是 `API_BASE_URL` / `API_KEY` / `MODEL_ID`。少数 demo 需要额外变量：

| demo | 额外变量 |
|------|---------|
| `08-evaluation-demo` | `JUDGE_MODEL_ID` |
| `11-fine-tuning-demo` | `BASE_MODEL`、`ADAPTER_PATH`（无 MODEL_ID）|
| `15-a2a-protocol-demo` | `AGENT_TOKEN`（agent 间 bearer 认证）+ 3 个端口 |
| `16-model-router-demo` | `MODEL_CHEAP` / `MODEL_MID` / `MODEL_PREMIUM`（三档模型 ID）|
| `17-cron-agent-demo` | 无额外变量，但需要 `apscheduler` 依赖 |

切云端 API（OpenAI / Anthropic）改 `API_BASE_URL` 和 `API_KEY` 即可。

## 推荐学习顺序

### 核心 LLM 工程（01-08，建议按序过一遍）

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

### Agent（09-10）

| # | demo | 价值 | 说明 |
|---|------|------|------|
| 09 | [simple-agent-demo](09-simple-agent-demo) | ⭐⭐⭐⭐⭐ | AI 自主决策、多步执行 |
| 10 | [multi-agent-demo](10-multi-agent-demo) | ⭐⭐⭐⭐⭐ | 多 Agent 协作 |

### 价值评估两极的话题（11-13）

| # | demo | 价值 | 说明 |
|---|------|------|------|
| 11 | [fine-tuning-demo](11-fine-tuning-demo) | ⭐⭐⭐ | LoRA 微调（场景受限） |
| 12 | [hybrid-search-demo](12-hybrid-search-demo) | ⭐⭐⭐ | GREP + 向量检索（小项目不用） |
| 13 | [prompt-engineering-demo](13-prompt-engineering-demo) | ⭐⭐ | Prompt 工程（价值在下降） |

### 高级架构 / 工程化（14-20）

| # | demo | 价值 | 说明 |
|---|------|------|------|
| 14 | [skill-loader-demo](14-skill-loader-demo) | ⭐⭐⭐⭐ | Skill 概念实现（按请求动态加载指令） |
| 15 | [a2a-protocol-demo](15-a2a-protocol-demo) | ⭐⭐⭐⭐ | Agent-to-Agent 协议（多进程 agent 互通）|
| 16 | [model-router-demo](16-model-router-demo) | ⭐⭐⭐⭐⭐ | 按请求难度路由到不同模型 + failover |
| 17 | [cron-agent-demo](17-cron-agent-demo) | ⭐⭐⭐⭐ | 定时触发的 Agent（监控 / 汇报 / 巡检）|
| 18 | [tool-guardrails-demo](18-tool-guardrails-demo) | ⭐⭐⭐⭐⭐ | 工具调用的 4 层安全围栏（路径/参数/速率/确认）|
| 19 | [batch-runner-demo](19-batch-runner-demo) | ⭐⭐⭐⭐ | 并发 + 重试 + 断点续跑的批量推理 |
| 20 | [context-refs-demo](20-context-refs-demo) | ⭐⭐⭐⭐ | `@file.py` 引用语法（Cursor / Claude Code 风格）|

### 怎么选

- **新手入门**：按 01 → 08 顺序过，每个看 README + 跑一遍就行
- **做 Agent 产品**：09 → 10 → 14 → 15，最后 **18 必看**（工具安全是上线门槛）
- **想降本**：07（缓存）+ 16（模型路由），两层正交叠加
- **跑评测 / 数据生成**：08 + 19，配合用
- **写 IDE / 编辑器集成**：20（@-ref）+ 14（skill）+ 04（MCP）

## 快速开始

```bash
cd 01-llm-function-call-demo
cp .env.example .env
pip install -r python/requirements.txt
python python/demo.py
```

每个 demo 都有自己的 README + 实测数据，跑法各异，看子目录。

## 技术取舍

**价值持续的**：Function Call、MCP、Streaming、结构化输出、Agent、记忆管理、错误处理、缓存、评测、模型路由、工具围栏。

**价值下降的**：Prompt Engineering（模型越来越强）、复杂 RAG（长上下文越来越长）、通用微调（被换更强基模型 + RAG 替代）。

**设计原则**：
- 简单方案优先（GREP 能解决就别上向量检索）
- 长期价值优先（别投入会被淘汰的技术）
- 用真实数据验证（凭直觉迭代 = 自欺欺人，所以有 evaluation-demo）
- 安全围栏从第一行代码就加（生产 Agent 上线前必过 18-tool-guardrails-demo）

## 技术栈

- **语言**：Python（全部）、Go / Rust（01-05、10 等部分 demo 有对应实现）
- **模型**：本地 MLX、或任意 OpenAI 兼容 API
- **核心依赖**：`requests` / `python-dotenv` / `colorama` —— 80% 的 demo 只要这三个
- **进阶依赖**（按需）：
  - 11 微调：`mlx-lm`、`mlx`
  - 14 skill：`PyYAML`
  - 15 A2A：`fastapi`、`uvicorn`、`pydantic`
  - 17 cron：`apscheduler`
  - 19 batch：`tenacity`

## 测试

部分 demo 自带单测：

```bash
# 16-model-router-demo：失败切层覆盖
cd 16-model-router-demo/python && python -m unittest test_failover.py -v
```

凡是覆盖了 mock-based 单测的都不依赖真实 LLM，秒级返回。

## License

MIT — 详见 [LICENSE](LICENSE)。

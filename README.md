# LLM 开发实战项目集

24 个独立 demo，按"目的"分到 4 个父级目录，每个分类下从 01 开始编号。每个用 Python（部分附 Go / Rust）实现，配合本地 MLX 模型或任意 OpenAI 兼容 API。

## 目录结构

```
llm/
├── core/         # 核心 LLM 工程能力 (8 个)
├── agent/        # Agent 范式 + 长跑治理 (6 个)
├── production/   # 生产工程化 (7 个)
└── niche/        # 价值评估两极的话题 (3 个)
```

## 环境配置

每个 demo 目录都自带一个 `.env.example` 模板。`.env` 进了 `.gitignore`，所以**复制**模板而不是直接修改：

```bash
cd core/01-function-call
cp .env.example .env
# 编辑 .env，把 API_KEY=REPLACE_WITH_YOUR_KEY 改成你自己的
```

标准变量是 `API_BASE_URL` / `API_KEY` / `MODEL_ID`。少数 demo 需要额外变量：

| demo | 额外变量 |
|------|---------|
| `core/08-evaluation` | `JUDGE_MODEL_ID` |
| `niche/01-fine-tuning` | `BASE_MODEL`、`ADAPTER_PATH`（无 MODEL_ID）|
| `production/02-a2a-protocol` | `AGENT_TOKEN`（agent 间 bearer 认证）+ 3 个端口 |
| `production/03-model-router` | `MODEL_CHEAP` / `MODEL_MID` / `MODEL_PREMIUM`（三档模型 ID）|
| `production/04-cron-agent` | 无额外变量，但需要 `apscheduler` 依赖 |

切云端 API（OpenAI / Anthropic）改 `API_BASE_URL` 和 `API_KEY` 即可。

## 推荐学习顺序

### core · 核心 LLM 工程（建议按序过一遍）

| # | demo | 价值 | 说明 |
|---|------|------|------|
| 01 | [function-call](core/01-function-call) | ⭐⭐⭐⭐⭐ | Function Call，Agent 的基础 |
| 02 | [streaming](core/02-streaming) | ⭐⭐⭐⭐⭐ | 流式输出，生产环境必备 |
| 03 | [structured-output](core/03-structured-output) | ⭐⭐⭐⭐⭐ | JSON Schema 强制约束 |
| 04 | [mcp](core/04-mcp) | ⭐⭐⭐⭐⭐ | Function Call 的标准化演进 |
| 05 | [memory](core/05-memory) | ⭐⭐⭐⭐⭐ | 对话历史 + Token 控制 |
| 06 | [error-handling](core/06-error-handling) | ⭐⭐⭐⭐⭐ | 重试 / 断路器 / 降级 |
| 07 | [caching](core/07-caching) | ⭐⭐⭐⭐⭐ | 精确 / 语义 / 前缀缓存 |
| 08 | [evaluation](core/08-evaluation) | ⭐⭐⭐⭐⭐ | 改完之后怎么验证没退化 |

### agent · Agent 范式 + 长跑治理

跑 5 轮的 ReAct 跟跑 50 轮的 Agent 是两回事。01-02 是基础范式，03-06 是真生产中长跑治理（源自 nanobot / hermes-agent / PraisonAI）。

| # | demo | 价值 | 说明 |
|---|------|------|------|
| 01 | [simple](agent/01-simple) | ⭐⭐⭐⭐⭐ | 最小 ReAct loop（含「什么是 ReAct」） |
| 02 | [multi-agent](agent/02-multi-agent) | ⭐⭐⭐⭐⭐ | 多 Agent 协作 |
| 03 | [context-governance](agent/03-context-governance) | ⭐⭐⭐⭐⭐ | 5 步组合拳：orphan tool 清理 + backfill + microcompact + budget + snip history（nanobot） |
| 04 | [summary-compression](agent/04-summary-compression) | ⭐⭐⭐⭐ | LLM 把老 history 总结成结构化 markdown（类 Claude Code `/compact`） |
| 05 | [subagent-orchestration](agent/05-subagent-orchestration) | ⭐⭐⭐⭐ | 主 agent 并行 fan-out subagent + isolated context + 真 LLM 实测 |
| 06 | [tool-call-recovery](agent/06-tool-call-recovery) | ⭐⭐⭐⭐ | 4 类死循环检测 + 错误喂回 LLM 自修；真 DuckDuckGo 联网 |

### production · 生产工程化

| # | demo | 价值 | 说明 |
|---|------|------|------|
| 01 | [skill-loader](production/01-skill-loader) | ⭐⭐⭐⭐ | Skill 概念实现（按请求动态加载指令） |
| 02 | [a2a-protocol](production/02-a2a-protocol) | ⭐⭐⭐⭐ | Agent-to-Agent 协议（多进程 agent 互通）|
| 03 | [model-router](production/03-model-router) | ⭐⭐⭐⭐⭐ | 按请求难度路由到不同模型 + failover |
| 04 | [cron-agent](production/04-cron-agent) | ⭐⭐⭐⭐ | 定时触发的 Agent（监控 / 汇报 / 巡检）|
| 05 | [tool-guardrails](production/05-tool-guardrails) | ⭐⭐⭐⭐⭐ | 工具调用的 4 层安全围栏（路径/参数/速率/确认）|
| 06 | [batch-runner](production/06-batch-runner) | ⭐⭐⭐⭐ | 并发 + 重试 + 断点续跑的批量推理 |
| 07 | [context-refs](production/07-context-refs) | ⭐⭐⭐⭐ | `@file.py` 引用语法（Cursor / Claude Code 风格）|

### niche · 价值评估两极的话题

| # | demo | 价值 | 说明 |
|---|------|------|------|
| 01 | [fine-tuning](niche/01-fine-tuning) | ⭐⭐⭐ | LoRA 微调（场景受限） |
| 02 | [hybrid-search](niche/02-hybrid-search) | ⭐⭐⭐ | GREP + 向量检索（小项目不用） |
| 03 | [prompt-engineering](niche/03-prompt-engineering) | ⭐⭐ | Prompt 工程（价值在下降） |

### 怎么选

- **新手入门**：按 `core/01 → 08` 顺序过，每个看 README + 跑一遍就行
- **做 Agent 产品**：`agent/01 → 02` → `production/01-skill-loader → 02-a2a-protocol`，最后 **`production/05-tool-guardrails` 必看**（工具安全是上线门槛）
- **想降本**：`core/07-caching` + `production/03-model-router`，两层正交叠加
- **跑评测 / 数据生成**：`core/08-evaluation` + `production/06-batch-runner`，配合用
- **写 IDE / 编辑器集成**：`production/07-context-refs` + `production/01-skill-loader` + `core/04-mcp`
- **Agent 跑长了崩了**：`agent/03-context-governance`（5 步治理）→ `04-summary-compression`（LLM 总结）→ `06-tool-call-recovery`（错误恢复）；多 agent 并行上 `05-subagent-orchestration`
- **想懂 LLM 内部**：去 [`../llm-internals/`](../llm-internals/) 看采样 / RoPE / 量化 / 投机解码

## 快速开始

```bash
cd core/01-function-call
cp .env.example .env
pip install -r python/requirements.txt
python python/demo.py
```

每个 demo 都有自己的 README + 实测数据，跑法各异，看子目录。

## 技术取舍

**价值持续的**：Function Call、MCP、Streaming、结构化输出、Agent、记忆管理、错误处理、缓存、评测、模型路由、工具围栏、长跑治理（context governance、subagent 编排）。

**价值下降的**：Prompt Engineering（模型越来越强）、复杂 RAG（长上下文越来越长）、通用微调（被换更强基模型 + RAG 替代）。

**设计原则**：
- 简单方案优先（GREP 能解决就别上向量检索）
- 长期价值优先（别投入会被淘汰的技术）
- 用真实数据验证（凭直觉迭代 = 自欺欺人，所以有 `core/08-evaluation`）
- 安全围栏从第一行代码就加（生产 Agent 上线前必过 `production/05-tool-guardrails`）

## 技术栈

- **语言**：Python（全部）、Go / Rust（部分 demo 有对应实现）
- **模型**：本地 MLX、或任意 OpenAI 兼容 API
- **核心依赖**：`openai` / `httpx` / `python-dotenv` —— 80% 的 demo 只要这三个
- **进阶依赖**（按需）：
  - `niche/01-fine-tuning`：`mlx-lm`、`mlx`
  - `production/01-skill-loader`：`PyYAML`
  - `production/02-a2a-protocol`：`fastapi`、`uvicorn`、`pydantic`
  - `production/04-cron-agent`：`apscheduler`
  - `production/06-batch-runner`：`tenacity`
  - `agent/06-tool-call-recovery`：`ddgs`（真联网搜索）

## 测试

部分 demo 自带单测：

```bash
# production/03-model-router：失败切层覆盖
cd production/03-model-router/python && python -m unittest test_failover.py -v

# agent 长跑治理 4 个 demo 都有完整 test.py
cd agent/03-context-governance/python && python test.py    # 7/7
cd agent/06-tool-call-recovery/python && python test.py    # 11/11
```

凡是覆盖了 mock-based 单测的都不依赖真实 LLM，秒级返回。

## License

MIT — 详见 [LICENSE](LICENSE)。

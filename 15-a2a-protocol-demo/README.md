# 15-a2a-protocol-demo

Agent-to-Agent (A2A) 协议的最小工作演示。多个独立 agent 进程通过 HTTP + JSON 互相调用，由 coordinator 把用户请求拆解、分派到专长 agent 并行执行，再汇总结果。

## 一句话理解 A2A 和 MCP

**A2A 和 MCP 是两种互补的协议**：

- **A2A（Agent-to-Agent）** 解决的是不同 AI 智能体之间的**通信和任务协作**——比如让两个智能体商量怎么分工。
- **MCP（Model Context Protocol）** 让 AI 智能体连接**外部工具和数据源**——比如查数据库、调 API。

两者结合，智能体既"聪明"（MCP 接到外部能力）又能"组队干活"（A2A 跟同伴协作）。

## 和 MCP 的层次差别

| 协议 | 谁连谁 | 例子 |
|------|-------|------|
| Function Call | LLM ↔ 本地函数 | LLM 决定调 `get_weather()` |
| MCP | LLM 应用 ↔ 工具服务器 | Claude Code 调 filesystem MCP server |
| **A2A** | **Agent ↔ Agent** | Coordinator agent 把 review 任务交给 reviewer agent |

A2A 是**水平的**——agents 之间相互独立、各自专长，可以是不同团队/不同进程/不同机器。MCP / Function Call 是**垂直的**——LLM 站在上面，工具被动等调用。

## 为什么不直接用 FastAPI + Prompt？

> 那 A2A 协议做了什么，和自己起一个 FastAPI 再加个 prompt 有啥区别？

**核心答案：A2A 的价值在"标准化"**——它定义了一套智能体之间通用的通信规则（怎么发现对方、怎么协商任务、怎么处理错误）。自建 FastAPI + Prompt 当然也能做出类似的东西，但相当于从头造轮子，而且**很难和别人的智能体无缝协作**。A2A 更像一套大家都遵守的"智能体社交礼仪"。

往深里拆，A2A 协议解决的事情可以分三层：

| 层次 | A2A 做了什么 | 自建 FastAPI + Prompt 的代价 |
|------|-------------|-----------------------------|
| **通信层** | 统一的 API 格式（任务请求、状态回调、错误结构） | 接口得自己设计，容易变成"方言"，别人对不上 |
| **协作层** | 内置任务分解、冲突解决、能力发现 (`AgentCard`) 等机制 | 路由、握手、能力声明的逻辑全得自己写 |
| **生态层** | 能直接接入现有 agent 网络，跨团队/跨公司组队 | 只能"单机玩"——别家的 agent 不认识你的协议 |

> 类比：HTTP 之前每个网络程序都有自己的协议；HTTP 出现之后，浏览器可以访问任何遵守 HTTP 的服务器。A2A 想成为"智能体之间的 HTTP"。

本 demo 的 `protocol.py` 就是这套标准的最小骨架（`AgentCard` / `TaskRequest` / `TaskResponse`），下文展开。

## 架构

```mermaid
sequenceDiagram
    participant U as 用户
    participant C as Coordinator
    participant Reg as Discovery<br/>(/.well-known/agent.json)
    participant T as Translator<br/>:8101
    participant R as Reviewer<br/>:8102
    participant S as Summarizer<br/>:8103

    Note over C,Reg: 1. 启动时发现
    C->>T: GET /.well-known/agent.json
    T-->>C: AgentCard
    C->>R: GET /.well-known/agent.json
    R-->>C: AgentCard
    C->>S: GET /.well-known/agent.json
    S-->>C: AgentCard

    Note over U,C: 2. 用户请求
    U->>C: "翻译 X 并审查代码 Y"

    Note over C: 3. LLM 路由<br/>决定派给哪些 agent
    C->>C: decompose() → 2 个 task

    Note over C,R: 4. 并发分派
    par
        C->>T: POST /tasks (translate, "X")
        T-->>C: TaskResponse(completed, ...)
    and
        C->>R: POST /tasks (review-code, "Y")
        R-->>C: TaskResponse(completed, findings=[...])
    end

    C-->>U: 汇总结果
```

## 协议定义

`protocol.py` 三个 Pydantic 模型：

```python
class AgentCard(BaseModel):
    name: str
    description: str
    capabilities: list[str]   # 能处理哪些 task_type
    endpoint: str
    version: str = "1.0"

class TaskRequest(BaseModel):
    task_id: str
    task_type: str            # 必须在目标 agent 的 capabilities 里
    input: dict               # 任务特定 payload
    requester: str            # 调用方名字，方便 trace

class TaskResponse(BaseModel):
    task_id: str
    state: Literal["completed", "failed"]
    output: dict | None
    error: str | None
```

每个 agent 暴露两个端点：

| 端点 | 用途 |
|------|------|
| `GET /.well-known/agent.json` | 返回 AgentCard，用于发现 |
| `POST /tasks` | 接收 TaskRequest，返回 TaskResponse |
| `GET /health` | 健康检查（launcher 等待启动用） |

## 文件结构

```
python/
├── protocol.py        # AgentCard / TaskRequest / TaskResponse
├── agents/
│   ├── _base.py       # FastAPI app factory + LLM 调用
│   ├── translator.py  # 中英翻译，capability=["translate"]
│   ├── reviewer.py    # 代码安全审查，capability=["review-code"]
│   └── summarizer.py  # 文本摘要，capability=["summarize"]
├── coordinator.py     # 发现 + LLM 路由 + 并发分派
└── launcher.py        # 启动所有 agent + 跑 demo + 清理
```

## 运行

```bash
pip install -r requirements.txt
python launcher.py
```

launcher 会：
1. 启动 3 个 agent 在 8101 / 8102 / 8103 端口
2. 拉取它们的 agent card
3. 跑 4 个 demo query（翻译、审查、混合任务、摘要）
4. 退出时清理子进程

也可以手动启动：

```bash
# 终端 1
python -m agents.translator

# 终端 2
python -m agents.reviewer

# 终端 3
python -m agents.summarizer

# 终端 4 —— 单独发请求
python coordinator.py "翻译成英文：你好世界"
```

## Coordinator 的 LLM 路由

`coordinator.decompose()` 用主 LLM 决定要派哪些 task：

```
You are a task router. Given a user request and a list of available agents,
output ONLY a JSON array of tasks:
[{"agent": "<name>", "task_type": "<capability>", "input": {...}}, ...]
```

返回后用 `ThreadPoolExecutor` 并发派给对应 agent。

## 加新 agent

1. 在 `agents/` 新建 `<name>.py`
2. 定义 `AgentCard` + 处理函数
3. 调 `make_app(card, handlers={...})`
4. 在 `.env` 加端口号
5. 在 `launcher.py` 和 `coordinator.SPECIALIST_ENDPOINTS` 注册

不用改 `protocol.py`、`_base.py`、coordinator 的路由逻辑——LLM 看 agent card 自己学新 capability。

## 几个值得说的设计细节

1. **Discovery 简化为硬编码端点列表** —— 真实 A2A 有 registry service 或 DNS 发现。本 demo 用环境变量配置端口、coordinator 启动时拉 card
2. **同步调用** —— `POST /tasks` 阻塞返回结果。真实 A2A 一般异步（POST 拿 task_id，后续轮询状态）
3. **没有流式输出** —— 真实场景应支持 SSE 流回部分结果
4. **路由用 LLM 而不是规则** —— 适合 agent 数少（< 10），多了应该先 embedding 召回再让 LLM 挑

## 认证（Bearer Token）

每个 agent 的 `POST /tasks` 都要求 `Authorization: Bearer <token>`。Token 在 `.env` 里：

```bash
AGENT_TOKEN=demo-secret-token-change-me
```

`/.well-known/agent.json` 和 `/health` 仍开放（A2A 惯例：发现端点公开，业务端点鉴权）。

AgentCard 里声明了 auth 要求，调用方按需带 token：

```json
{
  "name": "translator",
  "capabilities": ["translate"],
  "endpoint": "http://localhost:8101",
  "auth": {"scheme": "bearer"}
}
```

如果想关掉 auth（裸跑），把 `.env` 里 `AGENT_TOKEN` 注释掉即可——`_base.py` 检测到没设就放行所有请求。

### 验证 auth 真在工作

```bash
# 不带 token → 401
curl -X POST http://127.0.0.1:8101/tasks -H "Content-Type: application/json" \
     -d '{"task_id":"x","task_type":"translate","input":{"text":"hi","target":"zh"},"requester":"me"}'
# {"detail":"missing bearer token"}

# 带错误 token → 403
curl -X POST http://127.0.0.1:8101/tasks -H "Authorization: Bearer wrong" ...
# {"detail":"invalid token"}

# 带对的 token → 200
curl -X POST http://127.0.0.1:8101/tasks -H "Authorization: Bearer demo-secret-token-change-me" ...
# {"task_id":"x","state":"completed","output":{...}}
```

### 生产升级路径

Bearer 共享密钥只够 demo 用。生产里逐级加强：

| 升级到 | 何时需要 | 改动量 |
|--------|---------|--------|
| 每 agent 独立 token | 防止一个 agent 被入侵后能调所有其他 agent | 小 |
| 短期 JWT（带 scope）| 多 tenant、需要细粒度权限 | 中 |
| mTLS（双向证书）| Zero-trust、服务网格 | 大（需 PKI） |

## 局限

- 没有重试 / 断路器（参考 `06-error-handling-demo`）
- 没有分布式 trace（每个 task 应该带 trace_id 跨 agent 传递）
- 没有 cost / quota 管理
- token 是固定共享密钥，生产应该轮换 + 细分权限

## 相关 demo

- `04-mcp-demo` —— 工具协议（垂直）；A2A 是 agent 协议（水平），两者互补
- `10-multi-agent-demo` —— 在同一个进程内多 Agent 协作；本 demo 是真正跨进程
- `14-skill-loader-demo` —— Skill 是 prompt 的复用；A2A 是 agent 能力的复用

## 行业参考

- **Google A2A**（2024-2025）—— 本 demo 协议模型借鉴的主要来源
- **Anthropic Multi-Agent Patterns** —— Claude 团队在博客系列里讨论过类似设计
- **Hermes Agent (`acp_adapter` / `acp_registry`)** —— 工业级实现参考

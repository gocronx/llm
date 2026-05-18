# 15 · A2A Protocol — agent ↔ agent 跨进程协作

**A2A（Agent-to-Agent）是 Google 主推的 agent 互操作协议：每个 agent 暴露 HTTP
端点 + 一份 well-known 卡片（capabilities），coordinator 自发现 + 拆任务 + 派发。
比 MCP 更上层 —— MCP 是 tool/resource 共享，A2A 是 agent 互调。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `protocol.py` | 🟢 套出去用 | pydantic：AgentCard / TaskRequest / TaskResponse |
| `agents/_base.py` | 🟢 套出去用 | FastAPI app factory + Bearer auth + 共用 LLM client |
| `agents/translator.py` 等 | 🟢 套出去用（自己改） | 一个 specialist agent = card + handler |
| `coordinator.py` | 🟢 套出去用 | discover → decompose → 并发 dispatch |
| `util.py` | 🟢 共享小工具 | `extract_json_array`（LLM 输出容错抽取） |
| `main.py` | demo only | 拉子进程跑 4 个 demo query |
| `test.py` | demo only | pydantic + util 纯逻辑测试 |

## 三个 endpoint

每个 specialist agent 暴露三个固定端点：

| Path | 用途 | Auth |
|---|---|---|
| `GET /.well-known/agent.json` | 自我介绍（卡片） | 永远公开 |
| `POST /tasks` | 执行一个任务 | 可选 Bearer |
| `GET /health` | 探活 | 公开 |

## 工作流

```
main.py 拉 3 个子进程 (translator / reviewer / summarizer)
    ↓
coordinator.discover_agents()  GET /.well-known/agent.json × 3
    ↓
coordinator.decompose("translate this + check for security")
    LLM 看 user request + agents catalog → 输出
      [{"agent":"translator","task_type":"translate","input":{...}},
       {"agent":"reviewer",  "task_type":"review-code","input":{...}}]
    ↓
coordinator.dispatch 并行
    POST /tasks → translator
    POST /tasks → reviewer
    ↓
聚合结果
```

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py    # 7/7 passed, 不需要 LLM
python main.py    # 拉 3 个子进程跑 4 个 demo query
```

带 Bearer auth：

```bash
export AGENT_TOKEN=$(openssl rand -hex 32)
python main.py
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `well-known/agent.json` 是公开 endpoint | A2A 约定，发现期不能要 auth（鸡生蛋问题） |
| `/tasks` 走 Bearer auth | 不能让随便谁都能调 specialist；不设 token 等于公开 |
| coordinator 用 LLM 拆任务而不是规则 | 用户请求"翻译+审查"这种组合，LLM 自动拆出两个任务比写规则灵活 |
| `extract_json_array` 容错抽 | LLM 经常给一堆解释 + 数组，强抽最后一个合法数组最稳 |
| 并发 dispatch | specialist 之间不互相依赖时并行最快 |

## 常见坑

- ❌ **agent 卡片放在 `/agent.json` 而不是 `/.well-known/agent.json`** —— 标准位置，便于 crawl
- ❌ **不带 max_iters 兜底** —— 错误响应会一直被 dispatch，多花钱
- ❌ **dispatch 串行** —— 多个独立任务串行跑等于浪费时间
- ❌ **`/tasks` 不要 auth** —— 任何人能调你的 agent 等于裸奔
- ⚠️ **本地小模型 decompose 可能答错任务类型** —— `extract_json_array` 兜底，但 input 字段乱填还是会失败

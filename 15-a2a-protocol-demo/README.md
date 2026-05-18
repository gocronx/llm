# 15 · A2A Protocol Demo

Google A2A 风格的 agent ↔ agent 跨进程协作。每个 agent 是独立 HTTP 服务，coordinator 自发现 + LLM 拆任务 + 并行 dispatch。

## A2A vs MCP

| 协议 | 解决什么 |
|---|---|
| **MCP**（见 04） | LLM ↔ tool/resource：让模型用外部工具 |
| **A2A**（本 demo） | agent ↔ agent：让多个独立 agent 互调 |

两者互补：MCP 给 agent 加能力，A2A 让 agent 之间分工。

## 三个固定 endpoint

| Path | 用途 | Auth |
|---|---|---|
| `GET /.well-known/agent.json` | 自我介绍（卡片） | 公开 |
| `POST /tasks` | 执行任务 | 可选 Bearer |
| `GET /health` | 探活 | 公开 |

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py   # 7/7 passed
python main.py   # 拉 3 个 specialist 跑 4 个 demo query
```

带 Bearer auth：

```bash
export AGENT_TOKEN=$(openssl rand -hex 32)
python main.py
```

## 共通的坑

- ❌ agent 卡片路径不在 `/.well-known/`
- ❌ `/tasks` 不要 auth → 裸奔
- ❌ dispatch 串行 → 浪费时间
- ⚠️ 本地小模型 decompose 可能填错 input 字段

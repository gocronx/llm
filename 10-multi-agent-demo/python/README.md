# 10 · Multi-Agent — 顺序 + 并行 + 依赖编排

**Multi-Agent 不是把单 agent 拼起来这么简单 —— 关键是 orchestrator 怎么把上游产物传给下游。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `agent.py` | 🟢 套出去用 | `Agent(name, role, client, model).execute(task, context)` |
| `orchestrator.py` | 🟢 套出去用 | `Step` + `run_sequential` + `run_parallel` |
| `main.py` | demo only | writer → reviewer → editor 顺序；3 写手并行 |
| `test.py` | demo only | mock agent 测依赖传递、并行、context 截断 |

## 工作流模式

```
顺序（带依赖）         并行（彼此独立）
  writer                writer  writer  writer
    ↓ draft               ↓       ↓       ↓
  reviewer               (并发)
    ↓ review
  editor (看到 draft + review)
```

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py     # 3/3 passed
python main.py     # 看 writer/reviewer/editor 协作输出
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `Agent` 不带 function call | 多 agent 协作复杂度在 orchestration，单 agent 保持纯文本 |
| `_context()` 拼依赖 step 的 id+内容 | 下游 LLM 看到 `[draft] ...\n[review] ...` 而不是一坨拼字符串 |
| context 单条 max_chars=400 截断 | 多 step 累加很快爆 context；截断让流程能跑完 |
| `run_parallel` 不解 DAG | 调用方保证 steps 独立；解 DAG 是 100 行额外代码，不在 demo 范围 |
| `Step` 用 dataclass + `id` | 上游产物用 id 索引，比 "agent 名字" 更可控 |

## 常见坑

- ❌ **直接把所有 messages 拼起来传** —— 多 agent 的上下文会爆掉，按 step.id 选所需依赖即可
- ❌ **不截断上游产物** —— 5 个 step 累加成几千 token，最后一个 step 直接爆 context
- ❌ **顺序工作流里 step 失败不中止** —— 后续 step 拿到空 context 会乱跑
- ⚠️ **并行 step 之间不能有依赖** —— `run_parallel` 不解 DAG，传错了就拿不到上游产物

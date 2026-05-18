# 09 · Simple Agent — Function Call 包成多轮循环

**Agent 不是新东西。把 01 的一次 function-call 往返放进 while 循环，加上"达到最大轮数就退"的兜底，就是一个 ReAct 风格的小 agent。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `agent.py` | 🟢 套出去用 | `Agent(client, model)` + `.run(task)` |
| `tools.py` | 🟢 套出去用 | 同 01 的工具注册表 |
| `main.py` | demo only | 4 个多步任务（单步、计算+搜索、对比、聚合） |
| `test.py` | demo only | 用 mock 测 ReAct 循环逻辑，不调外网 |

## ReAct 循环

```
while iter < max:
    LLM 决策（消息 + tools）
    如果给了 content 没 tool_calls → 任务完成，返回
    如果给了 tool_calls → 执行每个工具，结果回灌 messages
    继续下一轮
到达 max 还没完 → 返回最后一次 content（不抛异常）
```

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py    # 3/3 passed
python main.py    # 看 agent 怎么规划工具序列
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `max_iterations` 是硬上限 | LLM 可能死循环调同一个工具，必须有兜底 |
| `on_step` 回调暴露每次工具调用 | 业务方想做 UI / 日志 / 限流自己挂回调 |
| 终止条件：`not msg.tool_calls` | 简单可靠；不靠"finish_reason"判断（不同模型行为不一致） |
| `Step` 不是 message —— 是 audit log | 把"agent 做了什么"和"LLM 看到什么"分开 |
| `temperature=0.3` 而不是 0 | 0 会让 agent 在某些 corner case 死循环；0.3 引入一点随机性容错 |

## 常见坑

- ❌ **没 `max_iterations` 兜底** —— LLM 可能调同一个工具循环上百次，烧钱
- ❌ **`tool_call_id` 漏回灌** —— 第二轮 LLM 看不到自己刚才的决策，会重复决策
- ❌ **只取 `tool_calls[0]`** —— LLM 可能一次返回多个并行 tool_calls，全跑完再继续
- ❌ **工具异常直接 raise** —— LLM 看不到错误，没法自我修正；统一返回 `{"error":...}` JSON
- ⚠️ **`max_iterations` 太小** —— 复杂任务（多次搜索 + 计算 + 总结）可能需要 6-10 轮

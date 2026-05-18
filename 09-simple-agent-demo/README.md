# 09 · Simple Agent Demo

把 01 的一次 function-call 往返包成多轮 while 循环 = ReAct 风格的最小 agent。

## ReAct 循环

```
while iter < max_iterations:
  LLM 决策 → 若给 content 且无 tool_calls：返回（任务完成）
            → 若给 tool_calls：执行，把结果回灌 messages，继续
到达 max 仍未给答案：返回最后一次 content
```

## 目录

```
.
├── python/
│   ├── agent.py    # 🟢 Agent + Step
│   ├── tools.py    # 🟢 工具注册表（同 01）
│   ├── main.py / test.py
│   └── requirements.txt
└── README.md
```

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py    # 3/3 passed，用 mock 测循环逻辑
python main.py    # 4 个多步任务
```

## 常见坑

- ❌ 没 `max_iterations` 兜底 → LLM 死循环
- ❌ 只看 `tool_calls[0]` → 漏调用
- ❌ 工具异常直接 raise → LLM 看不到错误，没法自我修正
- ⚠️ `max_iterations` 太小 → 复杂任务跑不完

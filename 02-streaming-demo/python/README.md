# 02 · Streaming — `openai` SDK 流式输出

**流式输出的关键不是 HTTP 协议（OpenAI SDK 已经帮你处理了 SSE 分帧/`[DONE]`），而是 function call 场景下怎么把分块到达的 `tool_calls` 拼成完整决策。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `client.py` | 🟢 套出去用 | `stream_text()` 纯文本流；`stream_with_tools()` 流式+工具 |
| `tools.py` | 🟢 套出去用（自己改） | 同 01 的注册表写法 |
| `main.py` | demo only | 两个场景的入口 |
| `test.py` | demo only | 冒烟检查 |

## 两个场景

### 纯文本流式

```python
for delta in stream_text(client, model, "你的问题"):
    print(delta, end="", flush=True)
```

OpenAI SDK 的 `stream=True` 会把响应包成一个 iterator，每个 chunk 拿 `chunk.choices[0].delta.content`。手撸 `requests + iter_lines` 解析 `data: ...\n\n` 是上一个时代的活，SDK 拿不到一行好处。

### 流式 + Function Call

挑战在第一轮：`tool_calls[i].function.name` 和 `arguments` 都是分多个 chunk 下发，`arguments` 还永远是 JSON 字符串。要按 `tc.index` 分槽位累积：

```python
acc[tc.index]["name"]  = (前面的) + tc.function.name      # name 通常只来一次
acc[tc.index]["args"] += tc.function.arguments           # arguments 字符串拼接
```

**陷阱**：不能用 dict.update 拼 arguments —— 半截 `{"city": "北` 不是合法 JSON。必须等流读完再 `json.loads`。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python main.py
python test.py
```

期待 `main.py` 输出形如：

```
>>> 纯文本流式：写一段 50 字内的 AI 简介
人工智能是模拟人类智能的...
[首字 0.42s / 总 2.85s / 23 chunks]

>>> 流式 + function call：北京天气
[tool] get_weather({'city': '北京'}) -> {"city":"北京","temperature":15,"condition":"晴"}
北京今天 15°C，天气晴朗。
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| 用 OpenAI SDK 的 stream iterator | 不再手撸 `data: ` 前缀 / `[DONE]` 哨兵 / `iter_lines` |
| `tool_calls` 按 `tc.index` 分槽位 | LLM 一次可能并行调多个工具，每个工具的 chunks 按 index 区分 |
| `arguments` 用字符串拼接，最后才 `json.loads` | 半截 JSON 不是合法字典，不能边收边解析 |
| `yield` 事件字典而不是直接 print | 调用方可能要在 Web UI 里渲染，不能把 UI 决策埋进 client |

## 常见坑

- ❌ **手撸 SSE 解析** —— OpenAI SDK 已经处理 `data: ...`/`[DONE]`/keep-alive 注释，自己写多半漏 case
- ❌ **`arguments` 边收边 `json.loads`** —— 永远会报 JSONDecodeError，必须等流读完
- ❌ **只看 `tool_calls[0]`** —— 同 01，模型可能并行调多个工具，按 index 全收
- ❌ **流式 chunk 里 `delta.content` 可能是 `None`** —— 要 `if delta.content:` 不要直接拼接
- ⚠️ **首字时间 vs 总时间** —— 流式不会让总耗时变短，只是把感知延迟从"等总时间"降到"等首字"

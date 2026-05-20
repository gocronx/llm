# 05 · Memory Management (Python) — 四种对话记忆策略

**LLM 没状态。多轮对话靠应用把历史塞进 messages 数组送回去。问题：历史会越来越长、最终爆 context / 烧钱。四种策略各有取舍。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `memory.py` | 🟢 套出去用 | `Full / Window / Tokens / Summary` 四个策略，同接口 |
| `chat.py` | 🟢 套出去用 | `Chat` 把 memory 和 LLM 客户端粘起来；`make_summarizer` 工厂 |
| `main.py` | demo only | 同一组对话喂四种 memory，对比哪种还记得早期事实 |
| `test.py` | demo only | 纯逻辑测试，不调 LLM |

## 四种策略

| 策略 | 何时丢历史 | 优 | 缺 | 适用 |
|---|---|---|---|---|
| `Full` | 不丢 | 上下文完整 | 长了爆 context、烧钱 | 短对话（<10 轮） |
| `Window(k)` | 超过 k 条丢最旧 | 简单、便宜 | 忘早期事实 | 一般对话（10-50 轮） |
| `Tokens(N)` | 估算 token 超 N 时丢 | 精确控制成本 | 突然"失忆" | 严格成本控制 |
| `Summary(k)` | 攒 k 条调 LLM 压成事实 | 保关键信息 | 多一次 LLM 调用，可能丢细节 | 长对话（>50 轮） |

`Summary` 用累积摘要 —— 旧摘要保留，新一段叠加，否则第二轮 summary 会把第一轮的关键事实丢掉。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py     # 纯逻辑，不需要 LLM
python main.py     # 对比四种策略对早期事实的记忆
```

`main.py` 期待输出：用户先说"我叫张三/25 岁/喜欢编程"，然后问"我叫什么/多大/有什么爱好"。`Window(k=4)` 大概率忘记姓名；`Summary` 应该全记得。

## 关键设计点

| 决策 | 原因 |
|---|---|
| 四种策略同接口 `append/messages` | `Chat` 这层完全不关心用的是哪种 |
| `Summary` 的 `summarize_fn` 注入 | memory 这层不该依赖 OpenAI；测试也可以用 fake 函数 |
| Summary 累积叠加，不覆盖 | 第 N 段摘要可能没提到第 1 段的事实，覆盖就丢了 |
| `Tokens.trim` 至少留 1 条 | 全清空了模型连"用户刚说啥"都不知道 |
| token 估算用规则法（中文 1.5 / 其它 4） | 不引 tiktoken 依赖；生产里换真 tokenizer |

## 常见坑

- ❌ **`Summary` 直接覆盖旧摘要** —— 第二段摘要没提到的旧事实就丢了，要累积
- ❌ **`Tokens` 趋势清光所有 msg** —— 至少留最后一条 user，否则模型完全失忆
- ❌ **system prompt 算进 Window 长度** —— Window 只该裁对话，system 永远固定
- ❌ **Summary 触发时还没把当前 user 算进去** —— append 一条就 _trim，这样新 user 不会被立刻总结掉
- ⚠️ **token 估算是糙的** —— 中文 1.5 字符/t 是经验值，真实下也就 ±20%；生产换 tiktoken

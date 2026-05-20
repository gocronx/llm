# 05 · Memory Management Demo

LLM 没状态。多轮对话靠应用把历史塞进 `messages` 数组送回去 —— 历史越长，越烧钱也越容易爆 context。四种策略各有取舍。

## 四种策略

| 策略 | 何时丢历史 | 优 | 缺 | 适用 |
|---|---|---|---|---|
| `Full` | 不丢 | 上下文完整 | 长了爆 context、烧钱 | 短对话（<10 轮） |
| `Window(k)` | 超过 k 条丢最旧 | 简单、便宜 | 忘早期事实 | 一般对话（10-50 轮） |
| `Tokens(N)` | 估算 token 超 N 时丢 | 精确控制成本 | 突然"失忆" | 严格成本控制 |
| `Summary(k)` | 攒 k 条调 LLM 压成事实 | 保关键信息 | 多一次 LLM 调用，可能丢细节 | 长对话（>50 轮） |

`Summary` 必须**累积叠加**，新摘要拼在旧摘要后面 —— 不能覆盖，否则第二段摘要没提到的旧事实就丢了。

## 目录

```
.
├── .env
├── python/   # Memory ABC + 4 个子类 + Chat
├── go/       # Memory interface + 4 个 struct + Chat
└── rust/     # Memory trait + 4 个 impl + ask()
```

## 跑起来

```bash
cd python && pip install -r requirements.txt && python test.py && python main.py
cd go && go mod tidy && go run .
cd rust && cargo run
```

## 共通的坑

- ❌ **Summary 直接覆盖旧摘要** —— 旧事实会丢，必须累积
- ❌ **Tokens 清空所有 msg** —— 至少留最后一条 user
- ❌ **system prompt 算进 Window 长度** —— Window 只裁对话
- ⚠️ **token 估算糙** —— 中文 1.5 字/t 是经验，生产换 tiktoken

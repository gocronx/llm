# Demo —— Event Callback 最小复刻

约 500 行 Python 复刻 OpenHands 的 event_callback 子系统：**ABC 处理器 + 注册表 + 后台 asyncio 派发 + 双维度过滤 + 失败隔离 + 自禁用 + audit log**，**外加 OpenHands 自己漏掉的 per-callback timeout**。

## 跑法

```bash
cp ../.env.example .env  # 在 case 根目录, 填 API_KEY
pip install -r requirements.txt
python main.py            # 跑全部 6 个场景
python main.py --scenario 5   # 只跑某一个 (5 调真 LLM, 其它不用)
python main.py --cleanup  # 清理 .events/ .titles/ .webhook-sink/ audit.jsonl
```

## 6 个场景

| # | 演示 | 模式 (来自 PATTERNS.md) |
|---|------|------------------------|
| 1 | fan-out: 一事件 → 多 callback 并发 | C (混合并发) |
| 2 | per-conversation 过滤 | B (双维度过滤) |
| 3 | per-event-kind 过滤 | B (双维度过滤) |
| 4 | 失败隔离: 一个 raise 不影响其他 | D (fire-and-forget + log) |
| 5 | TitleSetter 调 LLM + 自禁用 | A (Plugin Processor) |
| 6 | timeout per callback (生产升级 #2) | OpenHands 漏的, demo 补上 |

只有场景 5 需要 LLM (TitleSetterProcessor 真调用)。其他场景不依赖 LLM, 跑得很快。

## 文件分工

| 文件 | 对应 OpenHands 哪段 |
|------|--------------------|
| [events.py](events.py) | `openhands/app_server/event/event_service.py` 的 FilesystemEventService (简化版) |
| [callbacks.py](callbacks.py) | `event_callback_models.py:40-48` (ABC) + `set_title_callback_processor.py` (TitleSetter) + `event_callback_models.py:51` (Logging) |
| [dispatcher.py](dispatcher.py) | `sql_event_callback_service.py:200-252` (注册 + 派发 + 容错) + `webhook_router.py:491-503` (顺序-并发混合) |
| [main.py](main.py) | 6 个端到端场景 |

砍掉的部分:
- 不接 FastAPI: 单 CLI 进程合并演示 (升级 #1)
- 不接 SQL: 注册表在内存, audit log 是 JSONL 文件 (升级 #4)
- 不做真 webhook: WebhookProcessor 写 JSON 到本地文件 (升级 #6)
- 不做幂等性: callback 重复触发会重复执行 (升级 #5)
- 不做 DLQ: 失败的 callback 仅写 audit, 不重试 (升级 #3)

## 比 OpenHands 做对的一处

**per-callback timeout**（`dispatcher.py:_execute_one` 里的 `asyncio.wait_for`）。OpenHands 没设, 一个 hang 的 callback 会拖死整个 `asyncio.gather`. 我们 demo 默认 10s timeout, 场景 6 专门演示这个差异。

## 观察题目

1. 改 `dispatcher.py` 把同事件 callbacks 也改成串行（去掉 `gather`），跑场景 1，时间有差吗？写一个 sleep 1 秒的 LoggingProcessor 试试，3 个并行 vs 串行差几秒？
2. TitleSetterProcessor 在场景 5 跑完就 disabled 了。如果你想让它**每 10 条消息**重新生成一次 title（保持名字与对话漂移），要改哪里？
3. 场景 4 里 FailingProcessor 抛异常时，BEFORE-FAIL 和 AFTER-FAIL 还能跑 —— 但日志里看不到 "before/after" 的顺序。为什么？（提示: gather）
4. 把 audit_log 的格式从 JSONL 改成 SQLite（用 sqlite3 标准库），需要改哪几个方法？
5. 如果场景 5 的 LLM 调用其实是阻塞的 `requests.post`，会发生什么？为什么 demo 用了 `asyncio.to_thread` 包一层？

## 升级路径

详见 [`../BENCHMARK.md`](../BENCHMARK.md)。优先：timeout（已做）→ 幂等性 → 真 webhook → DLQ。

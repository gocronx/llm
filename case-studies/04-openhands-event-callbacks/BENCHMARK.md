# 原版 vs 复刻 Demo —— 差距与升级清单

Demo 复刻了 OpenHands event_callback 的核心机制（ABC + 注册表 + 双维度过滤 + fire-and-forget + 失败隔离 + self-disable + 持久化），用纯 Python（无 FastAPI，无 SQLAlchemy）讲清楚原理。下面列差距 + 怎么升到生产级。

## 功能差距矩阵

| 维度 | OpenHands 原版 | 本 demo |
|------|--------------|---------|
| **进程架构** | App Server FastAPI 收 webhook + 派发 | 单 CLI 进程合并演示 |
| **抽象基类** | `EventCallbackProcessor` (Pydantic discriminated) | 同, 但用普通 dataclass |
| **派发并发模型** | asyncio (事件串行, callback gather) | 同 (asyncio.gather 并发) |
| **存储** | SQLAlchemy + Postgres/SQLite | JSON file (跨进程持久化, 演示足够) |
| **过滤维度** | conv_id + event_kind 双 None 通配 | 同 |
| **结果持久化** | `event_callback_result` 表 | JSON file 追加 |
| **Self-DISABLE** | 改 status 字段 | 同 |
| **Webhook 推送** | httpx.post 真发 | 写 JSON 文件 ("假 webhook") |
| **HTTP 接收 webhook** | FastAPI router | 进程内直接调度 |
| **Timeout per callback** | ❌ 没设 (已知坑) | ✅ 有 (asyncio.wait_for, 演示升级) |
| **重试 / DLQ** | ❌ 没有 | ❌ 没有 (同原版坑) |
| **幂等性保证** | ❌ 没有 | ❌ 没有 (同原版坑) |
| **跨进程恢复** | DB 重启复活 | ✅ JSON 持久化 + reload |
| **企业版处理器** | GitHub / Slack / Jira / GitLab / Bitbucket | 跳过 (模式同 SlackProcessor) |

## 复现一次的最小投入

| 顺序 | 任务 | 投入 | 价值 | 状态 |
|------|------|------|------|------|
| 1 | 用 FastAPI 包成真 webhook 接收器 | 1 小时 | 高（体感双进程通信）| 未做 |
| 2 | 加 timeout per callback (`asyncio.wait_for`) | 10 分钟 | **高（生产必修，OpenHands 自己漏了）** | ✅ 已做 |
| 3 | 加 dead-letter queue (失败的 callback 进队列重试) | 半天 | 中（看产品 SLA） | 未做 |
| 4 | 把 JSON 文件存储换 SQLite + SQLAlchemy | 半天 | 中（多 worker 时必要） | 未做 |
| 5 | 加幂等性键（callback 内查"event_id 是否处理过"） | 1 小时 | 高（涉外部副作用必修）| 未做 |
| 6 | 真 webhook callback（httpx.post 到本地 listener） | 1 小时 | 中（看清完整链路）| 未做 |

推荐顺序：先做 2 + 5（生产可用下限），再做 1 + 6（双进程完整链路），最后 3 + 4（多 worker / 高 SLA）。

## 容易踩的坑

1. **`asyncio.create_task()` 不存引用，任务会被 GC 掉**。Python 3.11 起官方明确："Save a reference to the result of this function, to avoid a task disappearing mid-execution." OpenHands 把任务 `await` 在 `_run_callbacks_in_bg_and_close` 里间接持有，所以没被 GC。Demo 也这么做。
2. **single processor instance 跨 callback 共享 state 会串台**。同一个 SlackProcessor 实例处理 conv_A 和 conv_B 时，如果有 `self._last_message` 字段会污染。最好让 processor **无状态**，状态走 event_store 或 DB。
3. **同步代码进 async callback 会卡 event loop**。如果 processor 里 `requests.post(...)` 而不是 `httpx.AsyncClient.post(...)`，整个派发器卡住等阻塞 IO。
4. **callback 自禁用要先写盘再返回 SUCCESS**。如果先返回再写盘，进程恰好在中间崩了，下次启动 callback 仍是 ACTIVE，会重试已经成功的副作用。Demo 用 atomic write 缓解。
5. **None 返回值的语义要文档化清楚**。`Result | None` 三档（SUCCESS / ERROR / "未做下次再来"）必须在 ABC docstring 写清，否则后人会用错（比如忘 return 默认 None，被误判为"等下次"）。

## 想往生产推到底要什么

按依赖顺序：

1. **真 HTTP 层**：FastAPI 接 webhook + 同样的 FastAPI 发 webhook。让两端可以跑在不同机器。
2. **DB 持久化**：JSON 文件单机够，多 worker 必须 SQLite WAL 模式或 Postgres。WAL 帮你解决"两个 worker 同时改 callback 状态"的竞态。
3. **Timeout 全覆盖**：所有 `await processor(...)` 都包 `wait_for`。已知 hang 会拖死整个 gather，必修。
4. **Dead-letter queue**：失败超过 N 次的 callback 进 DLQ，**不再自动重试**，等运维介入。否则一个坏 callback 会被永远重试浪费资源。
5. **幂等性约定**：要求所有 processor 实现 `def idempotency_key(event) -> str`，框架记录已成功的 key，重复触发跳过。生产平台 Stripe / Slack / GitHub 都用这一招。
6. **观测**：每次 callback 执行打 trace + metrics（耗时、成功率、错误分类）。生产没这层会盲飞。
7. **背压**：事件涌来时 gather 太多 callback 内存爆。加 semaphore 限制并发度。

## 一句话总结

Demo 把"事件 + 副作用解耦"这个核心论点跑通了，**包括 OpenHands 自己漏的 timeout**。剩下的工程化全是让这个论点在高并发 + 多 worker + 跨服务场景下能撑住。

把 demo 当骨架，按上面清单逐条加血肉，就能往生产推。

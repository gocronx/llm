# 原版 vs 复刻 Demo —— 差距和往生产推的清单

OpenHands 是平台级项目（351MB），demo 只可能复刻其中**一条机制**（事件溯源）。下面列差距 + 工程化升级清单。

## 功能差距矩阵

| 维度 | OpenHands 原版 | 本 demo |
|------|--------------|---------|
| **进程架构** | App Server + Agent Server + Sandbox 三层 | 单 CLI 进程合并 |
| **存储后端** | Filesystem / AWS / GoogleCloud 三选 | 只 Filesystem |
| **事件粒度** | user / assistant / tool_call / tool_result / system / observation 多类 | 只 user_message / assistant_message |
| **工具调用** | sandbox 里跑任意 shell + 浏览器 + 编辑器 | 完全没有 |
| **传输** | WebSocket + SSE 流式 | CLI stdout |
| **多用户** | 内建 user/secrets/auth | 单 demo 无 |
| **LLM provider 抽象** | LiteLLM 抽几十个 provider | 直调 openai SDK |
| **MCP** | 双向（消费 + 提供） | 无 |
| **subagent / planning agent** | 注册式 + 强制规划模式 | 无 |
| **事件钩子** | event_callback (自动起标题等) | 无 |
| **Snapshot 加速 replay** | 大对话会做 snapshot | 每次全 replay |
| **并发写入保护** | 事件 id 全局唯一 + 文件原子写 | uuid 防撞但无锁 |

## 复现一次的最小投入

| 顺序 | 任务 | 投入 | 价值 |
|------|------|------|------|
| 1 | 把 `send_message` 包成 FastAPI POST 接口 | 1 小时 | 高（让你真的看到 client/server 分离） |
| 2 | 加 `tool_call` / `tool_result` 事件类型 + 一个 toy 工具 | 半天 | 高（让 demo 能展示 ReAct，不只是聊天）|
| 3 | 加一个 event_callback：每次 assistant_message 后自动写 conversation 标题 | 2 小时 | 中（看 event sourcing 的"事件驱动副作用"威力）|
| 4 | 加 snapshot：每 50 条事件做一份快照，replay 从最近 snapshot 开始 | 半天 | 中（演示大对话怎么不爆）|
| 5 | 把工具调用挪进 `tempfile.TemporaryDirectory` 做"假 sandbox" | 半天 | 中（演示 sandbox 隔离的最小版） |
| 6 | 引入 LiteLLM 替换直调 openai | 1 小时 | 低（只是 import 改一下，但接 Anthropic / Bedrock 立刻就能切了） |

推荐优先级：1 + 2 + 3。三个加完，demo 就有 OpenHands "server + event sourcing + callback" 三件套的最小可跑版。

## 容易踩的坑（设计时就要想好）

1. **事件 id 用时间戳做唯一性 → 必撞**。Demo 用 UUID4 是对的。生产可考虑 ULID（同样唯一但带时间序）。
2. **append 不是原子的** → 半截写入就崩 = 文件损坏 = 整个对话不能读。生产要 `write -> fsync -> rename` 三步。Demo 没做。
3. **event_callback 没做幂等**：如果一个事件触发的 callback 失败，重试时不能重复执行有副作用的动作（发邮件、扣费）。OpenHands 怎么处理的需要看具体 callback 实现，是个值得专门拆的 case。
4. **replay 性能** → 5000 条以上的对话每次全 replay 会卡。snapshot 是必修课。
5. **事件 schema 演化** —— 半年后你想给 user_message 加个字段（比如 client_request_id），老事件没这字段，新代码不能崩。需要在 replay 阶段做"老事件兼容层"，或者强制只追加不修改字段。

## 想往生产推到底要什么

复刻 demo 离生产差一道大墙。生产化拆开是这些模块（按依赖顺序）：

1. **存储层抽象**：把 `events.append` / `load_all` 抽成接口，至少能切到 SQLite（单机生产）和 S3（多机生产）。OpenHands 的 `EventService` 抽象就是干这个。
2. **传输层**：WebSocket / SSE 推流。HTTP request-response 模型扛不住 LLM 这种几分钟一个请求的负载。
3. **认证 / 多租户**：每个 conversation 绑 user_id，replay 时按 user_id 隔离。OpenHands 的 `UserContext` 干这个。
4. **Sandbox**：从 `ProcessSandboxService`（fork 子进程 + chdir tempdir）开始，进阶到 Docker。等生产真正跑起来再上 K8s。
5. **观测**：每条事件打 trace_id，对接 OpenTelemetry。这一步做好之后调试 / 复现问题成本骤降。
6. **删除 / GDPR**：用户要求删数据，事件溯源是**追加日志**，怎么删？OpenHands 是写一个 `event_redacted` 事件遮盖原事件——查询时跳过被遮盖的。

每一层都是独立可做的 demo —— 也就是说本目录可以衍生出 `03-openhands-sandbox-isolation`、`04-openhands-event-callbacks`、`05-openhands-litellm-routing`…… 等。

## 一句话总结

Demo 抓到了 OpenHands "状态在磁盘不在进程" 这条核心论点。**剩下的工程化全是为了让这条论点在多用户 / 高并发 / 工具执行场景下能撑住**。

如果你的项目暂时只服务自己一个人，这套 demo 的最小骨架已经够；如果要服务团队 / 用户，按上面的清单依次补。

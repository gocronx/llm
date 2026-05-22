# 抽出来的设计模式

OpenHands 跟 hermes 不是 "更好版本" 的关系，是 **形态不同**。能搬过来的不是单一机制，是**几个独立的工程化模式**，各自适合不同场景。

## 三个核心模式

### 模式 A · Event Sourcing 对话状态

```
事件流是真相
内存状态是缓存
重建状态 = replay 事件
```

**核心做法**：
- 每条 user/assistant/tool_call/tool_result 都写一条 append-only 事件到磁盘
- 进程任何时候都可以重启，从事件流 replay 出当前 messages
- 想给会话挂钩子（自动起标题、自动总结、自动统计 token）就在事件流上挂 callback

**适用**：任何**对话 / 工作流 / 长跑任务**类系统。

**不适用**：one-shot 调用、纯流式不留痕的场景。

### 模式 B · Sandbox-per-Task 执行隔离

```
LLM 不直接碰宿主机
所有工具调用都进 sandbox 容器
sandbox 是长寿的（不是 ephemeral）
sandbox 可暂停可恢复
```

**核心做法**：
- 每个任务（对话 / job / 用户）一个独立 sandbox
- sandbox 内有自己的文件系统 / Python 环境 / shell
- Agent 通过 HTTP 跟 sandbox 通信（不是直接 fork 子进程）
- 状态用 docker pause/unpause 冻结

**适用**：
- ✅ **多租户**（每用户隔离）
- ✅ **任意代码执行**（LLM 写的代码不可信）
- ✅ **跨多轮保留 workspace**（连续编辑同一份代码）

**不适用**：
- ❌ 单用户工具（开销不值）
- ❌ 纯文本对话（用不上 sandbox 能力）

### 模式 C · 双层进程：Orchestrator + Worker

```
App Server (薄):  鉴权 / 路由 / 持久化 / 状态机
Agent Server (厚): LLM 调用 / 工具执行 / ReAct
HTTP 在两层之间
```

**核心做法**：
- App Server 是 stateless 的，负责拿请求 → 找到 worker → 转发
- Agent Server 跑慢的 LLM 工作，可能耗几分钟一个请求
- 两者解耦后：App 可以横向扩，Agent 可以按负载弹

**适用**：高并发 / 多租户 / 弹性扩容场景。

**不适用**：本地工具 / 个人脚本（多一层 HTTP 没必要）。

## 何时选 OpenHands 模式 vs hermes 模式

| 问题 | 选 hermes 风格 | 选 OpenHands 风格 |
|------|--------------|----------------|
| 谁用？ | 自己 / 团队几个人 | 几十到几千用户 |
| 在哪跑？ | 我的笔记本 / 我的服务器 | 多租户 SaaS / 团队平台 |
| LLM 调用频率？ | 个人级（每天几十次） | 团队 / 平台级（每秒几次起步）|
| 工具会做什么？ | 改我的本地代码 | 改用户提交的代码 / 跑陌生代码 |
| 容忍宕机？ | 我重启一下就行 | 不可，要恢复对话 |
| 部署成本要低？ | 是，pip install 就跑 | 不是，可以接受 Docker / K8s |

**判断口诀**：超过 1 个用户 + LLM 要跑 shell + 不能丢对话 = OpenHands 模式。三条占两条以上就该选这套。

## 实践要点

### Event Sourcing 怎么入门

最常见的踩坑：

- **事件粒度选错**。太粗（一条事件包整轮对话）→ 没办法挂部分 callback；太细（一个 token 一条事件）→ 文件爆炸。OpenHands 的粒度是 **`user_message` / `assistant_message` / `tool_call` / `tool_result` / `system_event`**——业务有意义的离散动作，每条一个事件。
- **事件不要带 tombstone**。"删除"不是写个 `delete_event` 事件，而是写个 `event_redacted` 事件，原事件保留。审计要求。
- **event id 要全局唯一**。OpenHands 用 UUID；时间戳做不到，并发会撞。
- **replay 要快**。如果一个对话有 5000 条事件，全 replay 要几秒。考虑 snapshot：每 100 条事件做一份快照，replay 只从最近 snapshot 开始。

### Sandbox 怎么入门

最低成本的"假 sandbox"是 **Process Sandbox**：fork 子进程，进程 `chdir` 到 tempdir，限制权限。这是 OpenHands 的 `ProcessSandboxService` 实现，开发期足够。

往生产推时升到 Docker，再往上 K8s。**接口设计上把 sandbox 抽象成 `start / pause / resume / delete / exec_shell` 5 个动词**就行，后端可以慢慢换。

### 双层进程怎么入门

如果你不需要扩到多机，**不要做这层抽象**。一个 FastAPI 应用里跑所有东西更简单。等真到瓶颈了再拆——拆的成本比想象的低，因为业务逻辑已经按动词分清楚了（rest endpoint vs agent loop）。

OpenHands 拆的本质原因不是性能，是**让 sandbox 进程可以被独立部署在不同机器上**。如果你的 sandbox 跑在跟 App Server 同台机器上，那双层进程基本无价值。

### LiteLLM 该不该用

如果你的产品 **只支持 1-2 个 provider**：不该用，多余的抽象。
如果你的产品 **允许用户自带 API key 选任意 provider**：必须用，自己实现这层抽象很容易翻车（每个 provider 的 streaming / function calling / 错误码全不一样）。

OpenHands 选 LiteLLM 是因为它是平台产品，必须支持任意 provider。

## 反例：哪些不要抄

- ❌ **把所有事件都同步 flush 到云存储**。本地磁盘已经足够耐用，云存储延迟太高会卡主线程。OpenHands 在 `FilesystemEventService` 之外才有 AWS/GCS 实现，前者是默认。
- ❌ **Sandbox per request**（不是 per conversation）。每条消息起一个容器，启动开销吃掉所有响应时间。
- ❌ **App Server 自己也调一点 LLM**（"快速翻译用户输入"什么的）。一旦这么干两层架构就模糊了，App Server 变重，没法 stateless。OpenHands 严格守住 App Server 不调 LLM 的边界。
- ❌ **同步等 Agent Server 响应**。Agent Server 可能跑几分钟，App Server HTTP 不能就这么挂着。OpenHands 用 WebSocket 推增量，App Server 立刻返回。

## 跟我这个项目里其它 demo 的关系

- [`agent/05-subagent-orchestration`](../../agent/05-subagent-orchestration)：主 agent 临时 spawn subagent。OpenHands 的 subagent 是注册式，更接近"框架化的多 agent"。
- [`production/02-a2a-protocol`](../../production/02-a2a-protocol)：多 agent 通过 HTTP 互通。这就是 OpenHands 双层进程模式的最小版。
- [`production/04-cron-agent`](../../production/04-cron-agent)：定时触发 agent。可以叠加 event sourcing 让 cron 跑的 agent 也可重启可恢复。
- [`production/05-tool-guardrails`](../../production/05-tool-guardrails)：工具围栏。OpenHands 的 sandbox 就是终极版的"围栏"——直接换个执行环境。

把 event sourcing + sandbox + 双层进程拼起来 ≈ OpenHands 完整骨架的最小版。

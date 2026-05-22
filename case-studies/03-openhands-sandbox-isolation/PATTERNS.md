# 抽出来的设计模式

OpenHands 的 sandbox 子系统藏着 3 个不同层次的模式，每个都可以独立搬。

## 模式 A · 多后端抽象（Pluggable Backend Pattern）

```
abstract class Foo:
    start / stop / status / ...

impl ProcessFoo:      # dev / 单机
impl DockerFoo:       # 标准生产
impl RemoteFoo:       # 弹性 / 异构
```

**核心做法**：
- 定义一个**契约**抽象类（这里是 `SandboxService`）
- 所有调用方只跟抽象类打交道
- 三个实现互相不知道彼此存在
- 启动时按 config 选实现（依赖注入）

**好处**：dev 不用 Docker（用 Process backend），CI 不用 Docker（用 mock），生产用 Docker，弹性场景上 K8s——全是配置切换，业务代码零改动。

**适用**：任何**重资源 / 多环境 / 需要弹性**的子系统。LLM 调用层（LiteLLM 是同样的模式）、存储层（Filesystem/S3/GCS）、消息队列（内存/Redis/Kafka），都是这个模式的实例。

**不适用**：单环境固定方案。三个后端都是包袱时不要先做抽象。

### 怎么抄

最小契约（参考 `sandbox_service.py:29-233`）：
1. 抽象基类只暴露**业务动作**（start/pause/resume），不暴露**实现细节**（docker_client/subprocess）
2. 数据模型（SandboxInfo / SandboxStatus）由抽象层定义，所有后端用同一份
3. 工具方法（如 `wait_for_sandbox_running`）放抽象层，所有后端复用
4. **每个后端是一个类，不是一组函数**——状态有地方挂

## 模式 B · 状态机 + 健康检查异步化

```
start() → 立即返回 STARTING
              ↓
         后台轮询 /alive
              ↓
       通过? → RUNNING
       超时? → ERROR
```

**核心做法**：
- 创建动作 (start) 立即返回，不等真正 ready
- ready 状态由健康检查异步推进
- 状态机所有迁移由后台 task 触发，不由调用方主动 poll

**好处**：
- 调用方拿到 `SandboxInfo` 就能继续别的事，不阻塞
- 失败有清晰路径（健康检查 timeout → ERROR）
- 状态变迁集中在一处，好审计

**坑**：
- 调用方需要等 `RUNNING` 才能用 sandbox。OpenHands 提供 `wait_for_sandbox_running` 工具方法兜底（`sandbox_service.py:78-125`）
- 健康检查的 timeout 要调好（OpenHands 默认 15s，太短失败率高，太长用户感知慢）

**适用**：任何**资源创建慢但有明确就绪标志**的场景。容器、虚拟机、远程服务、长跑 job。

### 怎么抄

1. 定义清楚有限状态：STARTING / RUNNING / PAUSED / ERROR / MISSING
2. 每个迁移有触发条件 + 副作用
3. **异步轮询用一个独立 task / coroutine**，不要塞到 start() 里
4. 失败状态要有 cleanup（ERROR 时把已创建的资源销毁）

## 模式 C · 长寿沙箱 + Pause/Resume 语义

```
sandbox 不是一次性的容器
工作目录跨多轮消息保留
用户离开 → pause (省 CPU 不省内存)
用户回来 → resume (内存状态完整)
```

**核心做法**：
- **每对话一个 sandbox，sandbox 生命周期 = 对话生命周期**（不是消息生命周期）
- 工作目录是 volume mount，跨重启保留
- pause = SIGSTOP（freeze 进程状态，保留内存）
- resume = SIGCONT（从冻结点继续）

**好处**：
- LLM 在 sandbox 里跑 `pip install pandas` 这种慢操作，下一条消息还能用
- 用户隔夜回来对话不丢，sandbox 状态完整
- 计费上可以按"运行时长"算（pause 期不算）

**适用**：
- ✅ **编程类 agent**（编辑器、IDE 助手、AI software engineer）
- ✅ **数据分析 agent**（跨多轮维护 dataframe）
- ✅ **长跑实验 agent**（开了个 jupyter 不能每次新起）

**不适用**：
- ❌ **stateless 问答** —— 没必要维护工作目录
- ❌ **单次任务 agent** —— 用完就销毁，pause 是浪费

### 怎么抄

1. 把 sandbox 抽象成"有生命周期的对象"，**不是 request-scoped**
2. pause/resume API 必须有，否则长时间不用的 sandbox 占资源
3. 决定 pause 期能撑多久（OpenHands 是小时级，你的产品可能要天级 → 那就要做"pause 期持久化状态到磁盘 + 真正 stop 容器，resume 时重建"）
4. 给 sandbox 配 inactive timeout（30 分钟没消息自动 pause），别让用户忘了关而吃资源

## 何时全套抄 OpenHands sandbox 模式

✅ **强烈推荐抄**：
- 你的产品要让 LLM 跑**未审查的代码**（用户提交的脚本、agent 自己写的代码）
- 多用户场景（你必须隔离用户 A 和用户 B 的 workspace）
- LLM 工具操作的**潜在破坏力大**（删文件、装包、调外部 API）

⚠️ **抄一部分就够**：
- 你只需要**单进程隔离**（一个用户一个 workspace）—— 只抄 Process backend 即可，别引入 Docker 复杂度
- 你不需要 pause/resume（每对话短任务）—— 抽象基类 + 一个简单实现就行

❌ **别抄**：
- 你的 agent **只读不写**（搜索 / 总结 / 翻译 类）—— sandbox 是浪费
- 你的工具集**只有 HTTP 调用**（没本地执行）—— 不需要隔离层

## 实践要点

### Process backend：知道它不是真 sandbox

OpenHands 的 ProcessSandboxService 名字误导。它**只是 silo 不是 sandbox**——没 namespace 隔离、没 chroot、没文件系统限制。Agent 完全能读你的 `~/.ssh/`。

抄过来时记住三点：
1. **生产别用 Process backend**，只用 Docker / 真隔离方案
2. **本地 dev 用 Process backend 时，不要给 agent 高权限工具**（限制工具集到只读类）
3. **如果一定要用 Process backend 跑写操作，至少加个 path 白名单**：所有文件操作只允许在 working_dir 下

### Docker backend：必加资源限制

OpenHands 默认 `docker.containers.run()` 调用**没设资源限制**。生产必加：

```python
mem_limit='2g',
memswap_limit='2g',  # 防 swap 滥用
cpu_quota=100000,     # 100ms per 100ms = 1 core
pids_limit=512,       # 防 fork bomb
network_mode='internal',  # 默认禁外网
```

不加这些等于裸奔。

### 网络出站策略

OpenHands 默认 sandbox 能 curl 全网。**这是个产品决策不是 bug**——它需要让 LLM 装 pypi 包、克隆 GitHub 仓库。

但是：
- LLM 跑别人写的恶意代码 → 数据外泄
- 用户提供的 prompt 注入 → LLM 自己 curl 出去

生产必须想清楚网络策略：
- **完全断网**：极安全，但失去装包等能力
- **允许列表**：只允许 pypi / npm / GitHub —— 平衡
- **完全开放**：用户必须信任你不会泄露他们的数据

OpenHands 把这个决策**推给部署方**，没在代码里强制。你抄时必须明确选一边。

### Session API key：每 sandbox 一把

OpenHands 给每个 sandbox 生成独立的 96-bit session key（`docker_sandbox_service.py:387-392`）。**这点必抄**：
- 即使 sandbox 因为某种原因被外部访问到，没 key 也进不去
- key 绑定 status=RUNNING，pause/stop 后自动失效
- 日志里别打印这个 key

## 反例：哪些不要抄

- ❌ **每条消息一个 sandbox**。容器启动开销 1-5 秒，吃掉所有响应时间。OpenHands 是**每对话一个**，跨多轮复用。
- ❌ **同步等待 sandbox ready**。容器启动慢，HTTP 请求挂着等会 timeout。OpenHands 立即返回 `STARTING`，调用方按需 `wait_for_sandbox_running`。
- ❌ **状态只存内存**。Process backend 重启丢——这是 OpenHands 已知缺陷。生产要 DB / Redis 持久化 sandbox metadata。
- ❌ **App Server 直接 exec 进 sandbox**（比如直接 docker exec）。一旦这么干，App Server 就被绑到 Docker 后端了，无法切其它实现。OpenHands 始终走 HTTP → Agent Server → 进程，保持后端可换。

## 跟我这个项目里其它 demo 的关系

- [`production/05-tool-guardrails`](../../production/05-tool-guardrails)：工具调用的 4 层安全围栏（路径 / 参数 / 速率 / 确认）。这是**应用层**防护。sandbox 是**进程/系统层**防护。两者叠加才是完整方案。
- [`production/02-a2a-protocol`](../../production/02-a2a-protocol)：agent-to-agent HTTP 通信。OpenHands App Server ↔ Agent Server 就是这个模式的特殊化（同进程组 + session key 鉴权）。
- [`02-openhands-architecture`](../02-openhands-architecture)：本案例是 02 的"sandbox 那一块"专题深挖。先看 02 拿到整体定位再看 03 拿深度。

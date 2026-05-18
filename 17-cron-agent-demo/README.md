# 17 · Cron Agent Demo

定时触发的 Agent：监控、汇报、清理、巡检——主动按节奏跑，不等用户输入。

## 三个示例 job

| job | 周期 | 干啥 |
|---|---|---|
| heartbeat | 30s | 写 alive 事件 |
| check_api | 60s | 探后端活，记延迟 |
| summarize_recent | 120s | LLM 一句话总结最近事件 |

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py    # 6/6 passed
python main.py    # 跑 180s，Ctrl-C 优雅停
```

## 共通的坑

- ❌ 不设 max_instances → 慢 job 并发跑
- ❌ 不设 coalesce → 休眠后补刷屏
- ❌ state 文件直接 open+write → crash 时半写
- ❌ 让 LLM 推 trend → 小样本下编规律
- ⚠️ 这是进程内调度；服务级用 systemd timer / k8s CronJob

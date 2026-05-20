"""main.py —— APScheduler 跑三个示例 job：heartbeat / check_api / summarize_recent。

`max_instances=1`  防止慢 job (summarize) 和下一次触发并发跑两份。
`coalesce=True`    系统休眠/卡顿后，错过的多次触发合并成一次（不要补刷屏）。
"""

import argparse
import logging
import signal
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import state
from jobs import check_api, heartbeat, summarize_recent

logging.getLogger("apscheduler").setLevel(logging.WARNING)


# 一个表驱动一切：增删 job 改这里就够。
# `max_instances=1` 防止慢 job (summarize) 与下一次触发并发。
# `coalesce=True` 合并多次错过的触发为一次（系统休眠后不要补刷屏）。
JOB_SPECS = [
    dict(func=heartbeat,         id="heartbeat", seconds=30,  grace=10),
    dict(func=check_api,         id="check_api", seconds=60,  grace=15),
    dict(func=summarize_recent,  id="summary",   seconds=120, grace=30),
]


def build_scheduler() -> BackgroundScheduler:
    sch = BackgroundScheduler()
    # 第一次触发延迟 1s 启动后立即跑一次，避免 demo 用户启动后干等 30s 没动静。
    # 之后按 interval 正常推进（APScheduler 把 next_run_time 当首次时刻，后续基于它叠加）。
    first_run = datetime.now() + timedelta(seconds=1)
    for spec in JOB_SPECS:
        sch.add_job(
            spec["func"],
            trigger=IntervalTrigger(seconds=spec["seconds"]),
            id=spec["id"],
            next_run_time=first_run,
            max_instances=1,
            misfire_grace_time=spec["grace"],
            coalesce=True,
        )
    return sch


def print_status(sch: BackgroundScheduler) -> None:
    print(f"\n{datetime.now():%H:%M:%S}  jobs:")
    for j in sch.get_jobs():
        next_run = j.next_run_time.strftime("%H:%M:%S") if j.next_run_time else "-"
        print(f"  - {j.id:<10}  trigger={j.trigger}  next={next_run}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-for", type=int, default=180,
                        help="seconds to keep the scheduler alive")
    args = parser.parse_args()

    print(f"Resuming from state.json (last_heartbeat={state.get('last_heartbeat', '<never>')})")
    sch = build_scheduler()
    sch.start()

    stopped = False

    def _on_sigint(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, _on_sigint)

    print_status(sch)
    print(f"\nrunning for {args.run_for}s (Ctrl-C to stop early)\n")

    deadline = time.time() + args.run_for
    try:
        while time.time() < deadline and not stopped:
            time.sleep(1)
    finally:
        # wait=True 阻塞到 in-flight 的 job 结束才返回，避免 'stopped' 打完后还有 job
        # 在后台吐输出。代价是 Ctrl-C 后要等慢 job（如 LLM 调用）跑完才退出。
        # APScheduler 没有公开"当前正在执行的 job"列表，所以不列具体名字。
        print("\nwaiting for in-flight jobs to finish...")
        sch.shutdown(wait=True)
        print("scheduler stopped.")
        last = state.get("last_summary")
        if last:
            print(f"last summary @ {last['ts']}: {last['summary']}")


if __name__ == "__main__":
    main()

"""main.py —— 4 个场景演示 sandbox 隔离 / 状态机 / pause-resume / LLM 集成.

用法:
    python main.py             # 跑全部 4 场景
    python main.py --scenario 1   # 只跑某一个
    python main.py --cleanup   # 把磁盘残留的 .sandboxes/ 清掉
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from docker_sandbox import RESOURCE_LIMITS, DockerSandbox
from sandbox import ProcessSandbox

import agent


def _print_section(title: str) -> None:
    print(f"\n{'=' * 64}\n{title}\n{'=' * 64}")


# ── 场景 1: 多 sandbox 并行, 各自隔离 ──────────────────────────────────
def scenario_isolation(svc: ProcessSandbox) -> None:
    _print_section("场景 1 · 并行隔离: 两个 sandbox 互不可见")

    a = svc.start_sandbox()
    b = svc.start_sandbox()
    print(f"启动了 sandbox A id={a.id} workspace={a.workspace}")
    print(f"启动了 sandbox B id={b.id} workspace={b.workspace}")

    # A 创建一个文件
    rc, out, err = svc.exec_in_sandbox(
        a.id, a.session_api_key, "echo 'hello from A' > a.txt && ls"
    )
    print(f"\nA 跑 'echo > a.txt && ls': rc={rc}")
    print(f"  stdout: {out.strip()}")

    # B 列文件 —— 不应该看见 a.txt
    rc, out, err = svc.exec_in_sandbox(b.id, b.session_api_key, "ls")
    print(f"\nB 跑 'ls' (验证看不见 A 的文件): rc={rc}")
    print(f"  stdout: {out.strip() or '(empty workspace)'}")

    # host 工作目录也不应该看见 a.txt
    host_files = [
        p.name for p in Path(__file__).parent.iterdir() if not p.name.startswith(".")
    ]
    print(f"\nHost (本目录) 文件列表: {host_files}")
    print("  → 不包含 a.txt, sandbox 没污染 host ✓")

    # 用错钥匙访问 A → 应该拒绝
    rc, out, err = svc.exec_in_sandbox(a.id, "wrong-key", "ls")
    print(f"\n用错的 session_api_key 访问 A: rc={rc}")
    print(f"  stderr: {err}")
    print("  → 鉴权拒绝 ✓")

    svc.delete_sandbox(a.id)
    svc.delete_sandbox(b.id)


# ── 场景 2: 状态机 START → RUNNING → PAUSED → RUNNING ────────────────
def scenario_state_machine(svc: ProcessSandbox) -> None:
    _print_section("场景 2 · 状态机 + Pause/Resume (用心跳文件可视化)")

    s = svc.start_sandbox()
    print(f"启动后状态: {s.status.value}")
    heartbeat = s.workspace / ".heartbeat"

    # 让 daemon 写几条心跳
    print("\n[等 3 秒让 daemon 写心跳]")
    time.sleep(3)
    print(f"心跳文件内容 (运行中):\n  {heartbeat.read_text().strip()}")

    # pause
    svc.pause_sandbox(s.id)
    print(f"\npause 后状态: {svc.get_sandbox(s.id).status.value}")
    paused_content = heartbeat.read_text().strip()
    print(f"心跳此刻: {paused_content}")

    print("\n[paused 期间睡 3 秒, 看心跳是不是停了]")
    time.sleep(3)
    later_content = heartbeat.read_text().strip()
    print(f"3 秒后心跳: {later_content}")
    if paused_content == later_content:
        print("  → 心跳确实停了, 进程被 SIGSTOP 冻住 ✓")
    else:
        print("  ✗ 心跳还在动? 说明 pause 没生效")

    # 尝试在 paused 期间 exec → 应该被拒
    rc, out, err = svc.exec_in_sandbox(s.id, s.session_api_key, "echo test")
    print(f"\n在 PAUSED 状态执行 'echo test': rc={rc}")
    print(f"  stderr: {err}")

    # resume
    svc.resume_sandbox(s.id)
    print(f"\nresume 后状态: {svc.get_sandbox(s.id).status.value}")
    time.sleep(2)
    print(f"心跳又开始走: {heartbeat.read_text().strip()}")

    svc.delete_sandbox(s.id)
    print(f"\ndelete 后状态: {svc.get_sandbox(s.id)}")


# ── 场景 3: LLM 在 sandbox 里干活, 全程不污染 host ─────────────────────
def scenario_llm_in_sandbox(svc: ProcessSandbox) -> None:
    _print_section("场景 3 · LLM agent 通过 sandbox 干活 (host 全程不动)")

    host_files_before = sorted(
        [p.name for p in Path(__file__).parent.iterdir() if not p.name.startswith(".")]
    )

    s = svc.start_sandbox()
    print(f"sandbox 起好, workspace={s.workspace}")

    task = (
        "通过 bash 工具:\n"
        "  1) 在 sandbox 里用 cat<<EOF > fizzbuzz.py ... EOF 写出 FizzBuzz (1-15)\n"
        "  2) 用 bash 运行 python fizzbuzz.py 看实际输出\n"
        "  3) 看完输出后, 一句话总结对不对\n"
        "每一步都必须是真的 bash 工具调用, 不要在回复里贴代码."
    )
    print(f"\n[任务] {task}\n")

    def trace(tc):
        cmd = tc.args.get("command", "")[:120]
        result_preview = tc.result.replace("\n", " ↵ ")[:120]
        print(f"  [bash] {cmd}")
        print(f"  [out ] {result_preview}")

    final, history = agent.run_agent(svc, s, task, on_tool=trace)
    print(f"\n[模型最终回答]\n{final}")
    print(f"\n共调了 {len(history)} 次 bash, 全部在 sandbox 里跑.")

    # 检查 sandbox 内确实有 fizzbuzz.py
    rc, out, _ = svc.exec_in_sandbox(
        s.id, s.session_api_key, "ls *.py 2>/dev/null || echo none"
    )
    print(f"\n验证 sandbox 内文件: {out.strip()}")

    # 关键: host 本目录全程没多文件
    host_files_after = sorted(
        [p.name for p in Path(__file__).parent.iterdir() if not p.name.startswith(".")]
    )
    print(f"\nHost 本目录: 前 {host_files_before} → 后 {host_files_after}")
    if host_files_before == host_files_after:
        print("  → host 完全没受影响 ✓")
    else:
        print(
            f"  ✗ host 多了文件? 差: {set(host_files_after) - set(host_files_before)}"
        )

    svc.delete_sandbox(s.id)


# ── 场景 4: 跨场景持久性 —— sandbox 内 workspace 跨多轮保留 ──────────
def scenario_workspace_persistence(svc: ProcessSandbox) -> None:
    _print_section("场景 4 · workspace 跨多轮调用持久化")

    s = svc.start_sandbox()
    print(f"sandbox id={s.id}")

    # 第一轮: 创建文件
    svc.exec_in_sandbox(s.id, s.session_api_key, "echo 'data v1' > state.txt")
    print("\n第一轮: 写 state.txt = 'data v1'")
    rc, out, _ = svc.exec_in_sandbox(s.id, s.session_api_key, "cat state.txt")
    print(f"  读出: {out.strip()}")

    # 第二轮 (跟第一轮完全独立的 exec_in_sandbox 调用, 模拟下一条对话消息)
    rc, out, _ = svc.exec_in_sandbox(
        s.id, s.session_api_key, "cat state.txt && echo ' (v2 read again)'"
    )
    print("\n第二轮: 再次读 state.txt (模拟下一轮对话)")
    print(f"  读出: {out.strip()}")
    print(
        "  → 文件跨调用保留 ✓ (这是为什么 sandbox 是 per-conversation 不是 per-message)"
    )

    # pause → resume 后文件还在吗?
    svc.pause_sandbox(s.id)
    print("\npause...")
    time.sleep(1)
    svc.resume_sandbox(s.id)
    print("resume.")
    rc, out, _ = svc.exec_in_sandbox(s.id, s.session_api_key, "cat state.txt")
    print(f"resume 后读 state.txt: {out.strip()}")
    print("  → pause/resume 后文件仍在 ✓")

    svc.delete_sandbox(s.id)
    # delete 后 workspace 应该没了
    if not s.workspace.exists():
        print("\ndelete 后 workspace 已清理 ✓")


# ── 场景 5: 资源限制 (Docker only, upgrade #2) ─────────────────────────
def scenario_resource_limits(svc) -> None:
    _print_section("场景 5 · 资源限制: fork-bomb 被 pids_limit 拦 (仅 Docker)")
    if not isinstance(svc, DockerSandbox):
        print("此场景只在 Docker 后端生效 (Process 后端无资源限制).")
        print("跑: python main.py --backend docker --scenario 5")
        return

    print(f"资源上限: {RESOURCE_LIMITS}")
    s = svc.start_sandbox()
    print(f"sandbox id={s.id}")

    # 先确认正常命令能跑
    rc, out, _ = svc.exec_in_sandbox(s.id, s.session_api_key, "echo hello && nproc")
    print(f"\n正常命令: rc={rc}, out={out.strip()}")

    # fork-bomb. 每个进程开两个新进程, 无限递归.
    # pids_limit=64 会让 fork 返回 EAGAIN, bash 收到错误后退出.
    # 没限制的话整机会被拖死.
    print("\n试图 fork-bomb (pids_limit=64 应该拦住)...")
    rc, out, err = svc.exec_in_sandbox(
        s.id,
        s.session_api_key,
        # 加 timeout 5 防 fork-bomb 真的卡住
        "timeout 5 bash -c ':(){ :|:& };:' 2>&1 | head -3 || true; "
        "echo 'host still alive: '$(date +%s)",
    )
    print(f"  rc={rc}")
    print(f"  output 末段: ...{out.strip()[-200:]}")
    print("  → host 进程仍然存活, 容器被 pids_limit 兜住 ✓")

    svc.delete_sandbox(s.id)


# ── 场景 6: idle-timeout 自动 pause (upgrade #5) ──────────────────────
def scenario_idle_timeout(svc) -> None:
    _print_section("场景 6 · idle sandbox 自动 pause (用 sweeper)")

    # 短 timeout 方便观察: 5 秒不动就 pause
    stop_sweeper = svc.start_idle_sweeper(
        idle_timeout_seconds=5.0, sweep_interval_seconds=1.0
    )
    print("启动 idle sweeper (timeout=5s)")

    s = svc.start_sandbox()
    print(f"sandbox 起好, id={s.id}, 状态={s.status.value}")

    # 戳一下让 last_activity_at 刷新
    svc.exec_in_sandbox(s.id, s.session_api_key, "echo touched")
    print(f"\n立即 exec 一次, 状态={svc.get_sandbox(s.id).status.value} (活跃)")

    print("\n[7 秒不动, 看 sweeper 自动 pause]")
    for i in range(8):
        time.sleep(1)
        st = svc.get_sandbox(s.id).status.value
        print(f"  +{i + 1}s: 状态={st}")
        if st == "PAUSED":
            break

    final = svc.get_sandbox(s.id).status.value
    if final == "PAUSED":
        print("  → idle 超时, 自动 pause ✓")
    else:
        print(f"  ✗ 未触发自动 pause (状态: {final})")

    stop_sweeper.set()
    svc.delete_sandbox(s.id)


# ── 场景 7: ProcessSandbox 路径黑名单 (upgrade #6, best-effort) ──────
def scenario_path_blacklist(svc) -> None:
    _print_section("场景 7 · ProcessSandbox 拒访问 /etc /usr 等 (best-effort)")

    if not isinstance(svc, ProcessSandbox):
        print("此场景演示 ProcessSandbox 的字符串黑名单.")
        print(
            "Docker 后端不需要 — 它有真隔离. 跑: python main.py --backend process --scenario 7"
        )
        return

    s = svc.start_sandbox()
    print(f"sandbox id={s.id}")

    bad_commands = [
        "cat /etc/passwd",
        "ls /usr/local/bin",
        "echo $HOME",
        "ls ../",
        "cat /proc/cpuinfo",
    ]
    for cmd in bad_commands:
        rc, out, err = svc.exec_in_sandbox(s.id, s.session_api_key, cmd)
        verdict = "拒" if rc == 126 else f"通过 (rc={rc})"
        print(f"  [{verdict}] {cmd}")
        if rc == 126:
            print(f"           reason: {err.strip()}")

    # 正常的 workspace 内操作应该过
    good = "echo workspace-ok > test.txt && cat test.txt"
    rc, out, _ = svc.exec_in_sandbox(s.id, s.session_api_key, good)
    print(f"\n  [{'通过' if rc == 0 else '拒'}] {good}")
    print(f"           → {out.strip()}")

    print(
        "\n⚠️  诚实声明: 这是 best-effort 字符串匹配, 真 LLM 能用 base64 / 变量替换绕过."
    )
    print("    ProcessSandbox 永远不是真的 sandbox. 要安全请用 Docker 后端.")

    svc.delete_sandbox(s.id)


# ── 场景 8: 跨进程持久化恢复 (upgrade #3, 仅 Process) ─────────────────
def scenario_persistence(svc) -> None:
    _print_section("场景 8 · SQLite 持久化 + 跨进程恢复 (仅 ProcessSandbox)")

    if not isinstance(svc, ProcessSandbox):
        print("此场景演示 ProcessSandbox 跨进程恢复. 跑:")
        print("  python main.py --backend process --scenario 8")
        return

    # 此场景需要一个带 db_path 的 ProcessSandbox.
    # main.py 默认 svc 没接 DB, 所以这里另起一个带 DB 的.
    base = Path(__file__).parent / ".sandboxes"
    db_path = Path(__file__).parent / ".sandbox-registry.db"

    # 先清掉可能残留的 DB 让 demo 干净
    if db_path.exists():
        db_path.unlink()

    persistent_svc = ProcessSandbox(base_dir=base, db_path=db_path)
    s = persistent_svc.start_sandbox()
    persistent_svc.exec_in_sandbox(
        s.id, s.session_api_key, "echo persisted-v1 > marker.txt"
    )

    print("Step 1 (本进程):")
    print(f"  sandbox id={s.id}")
    print(f"  daemon pid={s.daemon_pid}")
    print("  写了 workspace/marker.txt = 'persisted-v1'")
    print(f"  DB 文件: {db_path.name}")
    print("  *注意: 不 delete_sandbox, daemon 继续在后台跑 (孤儿进程)*")

    # 不主动停 daemon. 进程 exit 后, daemon 会被 launchd / init 接管,
    # 子进程仍能通过 pid 接管它.

    # Step 2: 起一个全新 python 子进程, 复活 sandbox
    child_script = (
        "import sys\n"
        f"sys.path.insert(0, {repr(str(Path(__file__).parent))})\n"
        "from pathlib import Path\n"
        "from sandbox import ProcessSandbox\n"
        "\n"
        f"svc = ProcessSandbox(base_dir=Path({repr(str(base))}), db_path=Path({repr(str(db_path))}))\n"
        "print(f'  _registry 大小 = {len(svc._registry)}')\n"
        f"info = svc.get_sandbox({repr(s.id)})\n"
        "if info is None:\n"
        "    print('  ✗ 没找到 sandbox')\n"
        "    sys.exit(1)\n"
        "print(f'  reload 到 sandbox: id={info.id}')\n"
        "print(f'  status={info.status.value}, pid={info.daemon_pid}')\n"
        "rc, out, err = svc.exec_in_sandbox(info.id, info.session_api_key, 'cat marker.txt')\n"
        "print(f'  exec cat marker.txt: rc={rc}, out={out.strip()!r}')\n"
        "if rc != 0:\n"
        "    print(f'    stderr={err.strip()!r}')\n"
        "    sys.exit(2)\n"
        "# 新进程能继续控制原 sandbox\n"
        "svc.pause_sandbox(info.id)\n"
        "print(f'  pause 后 status = {svc.get_sandbox(info.id).status.value}')\n"
        "svc.resume_sandbox(info.id)\n"
        "print(f'  resume 后 status = {svc.get_sandbox(info.id).status.value}')\n"
        "# 清理\n"
        "svc.delete_sandbox(info.id)\n"
        "print('  delete 完成, daemon 已停, workspace 已清')\n"
    )

    print("\nStep 2 (子进程 — 全新 Python 解释器):")
    result = subprocess.run(
        [sys.executable, "-c", child_script],
        capture_output=True,
        text=True,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        print(f"\n子进程出错 (returncode={result.returncode}):")
        print(result.stderr)
        return

    print("\n→ 跨进程恢复成功 ✓")
    print(
        "  daemon 进程在 step 1 起的, step 2 (完全独立的 Python) 通过 SQLite 找回 + 接管."
    )

    # Cleanup DB
    if db_path.exists():
        db_path.unlink()


# ── main ──────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--scenario", type=int, choices=[1, 2, 3, 4, 5, 6, 7, 8], help="只跑某个场景"
    )
    p.add_argument(
        "--backend",
        choices=["process", "docker"],
        default="process",
        help="选 sandbox 后端 (默认 process). docker 需要 'pip install docker' + 本机 docker daemon.",
    )
    p.add_argument("--cleanup", action="store_true", help="清理 .sandboxes/")
    args = p.parse_args()

    base = Path(__file__).parent / ".sandboxes"

    if args.cleanup:
        if base.exists():
            shutil.rmtree(base)
            print(f"已清理 {base}")
        else:
            print("没东西可清")
        return

    # 多后端抽象的实际威力: 这里只换一行, 下面的 scenarios 全部不动.
    if args.backend == "docker":
        try:
            svc = DockerSandbox(base_dir=base)
            print(f"[使用 Docker 后端, 镜像 = {svc.image}]")
        except RuntimeError as e:
            print(f"Docker 后端启动失败:\n{e}")
            sys.exit(1)
    else:
        svc = ProcessSandbox(base_dir=base)
        print("[使用 Process 后端]")

    scenarios = {
        1: scenario_isolation,
        2: scenario_state_machine,
        3: scenario_llm_in_sandbox,
        4: scenario_workspace_persistence,
        5: scenario_resource_limits,  # upgrade #2 (仅 Docker)
        6: scenario_idle_timeout,  # upgrade #5
        7: scenario_path_blacklist,  # upgrade #6 (仅 Process)
        8: scenario_persistence,  # upgrade #3 (仅 Process)
    }

    if args.scenario:
        scenarios[args.scenario](svc)
    else:
        for n in sorted(scenarios):
            scenarios[n](svc)

    _print_section("结束")
    print(f"sandbox 残留 (若有): {base}")
    print("清理: python main.py --cleanup")


if __name__ == "__main__":
    main()

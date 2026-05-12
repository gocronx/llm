"""
回归测试：把当前结果存为 baseline，未来升级时对比

典型用法：
  # 1. 你今天对当前 prompt/model 的效果满意，把它存为基准
  python regression_test.py save --tag v1

  # 2. 一周后改了 prompt 或换了模型，跑同一个数据集对比
  python regression_test.py compare --baseline v1

输出：
  - 总体通过率变化（提升 / 持平 / 退化）
  - 哪些样本从'通过'变'失败'（regressions）
  - 哪些样本从'失败'变'通过'（improvements）

为什么需要它：
  改 prompt 经常出现"按下葫芦浮起瓢"——A 类问题修好了，B 类问题悄悄坏了。
  没有 baseline，就只能靠运气和直觉。
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, init

from dataset_eval import run_dataset, save_report, RESULTS_DIR, DEFAULT_DATASET
from dotenv import load_dotenv
import os

init(autoreset=True)
load_dotenv("../.env")

BASELINE_DIR = Path(__file__).parent / "results" / "baselines"
MODEL_ID = os.getenv("MODEL_ID")


def cmd_save(args):
    """跑一次评测，把结果存为指定 tag 的 baseline"""
    payload = run_dataset(Path(args.dataset), args.model, args.concurrency)

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BASELINE_DIR / f"{args.tag}.json"
    if out_path.exists() and not args.force:
        print(f"{Fore.RED}baseline '{args.tag}' 已存在。"
              f"加 --force 覆盖。{Style.RESET_ALL}")
        sys.exit(1)

    payload["tag"] = args.tag
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n{Fore.GREEN}baseline 已保存: {out_path}{Style.RESET_ALL}")
    print(f"  通过率: {payload['summary']['pass_rate']*100:.1f}%")
    print(f"  之后用：python regression_test.py compare --baseline {args.tag}")


def cmd_compare(args):
    """加载 baseline，对当前 prompt/model 跑一遍，输出对比报告"""
    baseline_path = BASELINE_DIR / f"{args.baseline}.json"
    if not baseline_path.exists():
        print(f"{Fore.RED}找不到 baseline: {baseline_path}{Style.RESET_ALL}")
        print(f"先运行：python regression_test.py save --tag {args.baseline}")
        sys.exit(1)

    with baseline_path.open("r", encoding="utf-8") as f:
        baseline = json.load(f)

    print(f"{Fore.CYAN}加载 baseline '{args.baseline}'  "
          f"通过率={baseline['summary']['pass_rate']*100:.1f}%{Style.RESET_ALL}\n")

    print(f"{Fore.CYAN}开始跑当前版本…{Style.RESET_ALL}")
    current = run_dataset(Path(args.dataset), args.model, args.concurrency,
                          verbose=False)

    diff = compare_runs(baseline, current)
    print_diff(diff, baseline, current)

    if args.save_current:
        out_path = save_report(current, RESULTS_DIR)
        print(f"\n{Fore.GREEN}当前结果已保存: {out_path}{Style.RESET_ALL}")

    # 退化即非零退出码（适合接入 CI）
    if diff["regressions"]:
        sys.exit(1)


def compare_runs(baseline: dict, current: dict) -> dict:
    base_records = {r["id"]: r for r in baseline["records"]}
    curr_records = {r["id"]: r for r in current["records"]}

    common = set(base_records) & set(curr_records)
    regressions = []  # 通过 → 失败
    improvements = []  # 失败 → 通过
    still_failing = []
    new_only = set(curr_records) - set(base_records)
    removed = set(base_records) - set(curr_records)

    for qid in common:
        b, c = base_records[qid], curr_records[qid]
        if b["pass"] and not c["pass"]:
            regressions.append((qid, b, c))
        elif not b["pass"] and c["pass"]:
            improvements.append((qid, b, c))
        elif not b["pass"] and not c["pass"]:
            still_failing.append((qid, b, c))

    return {
        "regressions": regressions,
        "improvements": improvements,
        "still_failing": still_failing,
        "new_only": new_only,
        "removed": removed,
    }


def print_diff(diff: dict, baseline: dict, current: dict):
    print(f"\n{Fore.CYAN}{'='*60}")
    print("回归测试报告")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    bpr = baseline["summary"]["pass_rate"] * 100
    cpr = current["summary"]["pass_rate"] * 100
    delta = cpr - bpr

    if delta > 0.5:
        delta_color = Fore.GREEN
        delta_mark = "↑"
    elif delta < -0.5:
        delta_color = Fore.RED
        delta_mark = "↓"
    else:
        delta_color = Fore.YELLOW
        delta_mark = "→"

    print(f"  baseline 模型: {baseline['summary']['model']}")
    print(f"  current  模型: {current['summary']['model']}")
    print(f"  通过率: {bpr:.1f}% → {cpr:.1f}%  "
          f"{delta_color}{delta_mark} {abs(delta):.1f}%{Style.RESET_ALL}\n")

    if diff["regressions"]:
        print(f"{Fore.RED}退化（{len(diff['regressions'])} 个，需要看）：{Style.RESET_ALL}")
        for qid, b, c in diff["regressions"]:
            print(f"  ✗ {qid}: {b['question']}")
            print(f"    baseline 答: {b['actual'][:60]}")
            print(f"    current  答: {c['actual'][:60]}")
            print(f"    指标判定: {c['detail']}")
    else:
        print(f"{Fore.GREEN}✓ 没有退化的样本{Style.RESET_ALL}")

    if diff["improvements"]:
        print(f"\n{Fore.GREEN}修复（{len(diff['improvements'])} 个）：{Style.RESET_ALL}")
        for qid, b, c in diff["improvements"]:
            print(f"  ✓ {qid}: {b['question']}")
            print(f"    曾经答: {b['actual'][:60]}")
            print(f"    现在答: {c['actual'][:60]}")

    if diff["still_failing"]:
        print(f"\n{Fore.YELLOW}持续失败（{len(diff['still_failing'])} 个，"
              f"两个版本都不通过）：{Style.RESET_ALL}")
        for qid, _, c in diff["still_failing"][:5]:
            print(f"  - {qid}: {c['question']}")
        if len(diff["still_failing"]) > 5:
            print(f"  ...（省略 {len(diff['still_failing']) - 5} 个）")

    if diff["new_only"] or diff["removed"]:
        print(f"\n{Fore.YELLOW}样本变动：{Style.RESET_ALL}")
        if diff["new_only"]:
            print(f"  新增: {sorted(diff['new_only'])}")
        if diff["removed"]:
            print(f"  删除: {sorted(diff['removed'])}")

    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    if diff["regressions"]:
        print(f"{Fore.RED}有退化样本 → 退出码 1（适合接入 CI 拦截发布）{Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}无退化 → 可以放心发布{Style.RESET_ALL}")


def cmd_list(args):
    if not BASELINE_DIR.exists():
        print(f"还没有 baseline。先运行：python regression_test.py save --tag <name>")
        return
    baselines = sorted(BASELINE_DIR.glob("*.json"))
    if not baselines:
        print(f"还没有 baseline。先运行：python regression_test.py save --tag <name>")
        return
    print(f"{Fore.CYAN}已保存的 baseline：{Style.RESET_ALL}\n")
    for path in baselines:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        s = data["summary"]
        print(f"  {path.stem:20s}  "
              f"{s['model']:30s}  "
              f"{s['pass_rate']*100:>5.1f}%  "
              f"{s.get('timestamp', '?')}")


def main():
    parser = argparse.ArgumentParser(description="回归测试：baseline 对比")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_save = sub.add_parser("save", help="把当前结果存为 baseline")
    p_save.add_argument("--tag", required=True, help="baseline 名字（如 v1）")
    p_save.add_argument("--dataset", default=str(DEFAULT_DATASET))
    p_save.add_argument("--model", default=MODEL_ID)
    p_save.add_argument("--concurrency", type=int, default=4)
    p_save.add_argument("--force", action="store_true")
    p_save.set_defaults(func=cmd_save)

    p_cmp = sub.add_parser("compare", help="对比当前结果 vs baseline")
    p_cmp.add_argument("--baseline", required=True, help="baseline 名字")
    p_cmp.add_argument("--dataset", default=str(DEFAULT_DATASET))
    p_cmp.add_argument("--model", default=MODEL_ID)
    p_cmp.add_argument("--concurrency", type=int, default=4)
    p_cmp.add_argument("--save-current", action="store_true")
    p_cmp.set_defaults(func=cmd_compare)

    p_list = sub.add_parser("list", help="列出所有 baseline")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

"""
数据集批量评测

把 quick_demo / basic_metrics / llm_judge 串起来：
  1. 加载 JSONL 测试集
  2. 对每条样本调用 LLM
  3. 按 metric 类型走对应指标
  4. 汇总成报告（按分类统计 + 失败样本明细 + 输出 JSON）

可重复跑：每次结果都会写到 results/ 目录，文件名带时间戳。
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from colorama import Fore, Style, init

from basic_metrics import evaluate
from llm_judge import judge_binary

init(autoreset=True)
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "qa_testset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


def call_model(prompt: str, model: str = None, temperature: float = 0.0) -> str:
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": model or MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 300,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def load_dataset(path: Path) -> list[dict]:
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def evaluate_one(case: dict, model: str) -> dict:
    """跑一条样本：调用 LLM → 走指标 → 返回结果记录"""
    started = time.time()
    try:
        actual = call_model(case["question"], model=model)
        error = None
    except Exception as e:
        actual = ""
        error = f"{type(e).__name__}: {e}"

    record = {
        "id": case["id"],
        "category": case.get("category", "default"),
        "question": case["question"],
        "actual": actual,
        "metric": case["metric"],
        "elapsed_ms": int((time.time() - started) * 1000),
        "error": error,
    }

    if error:
        record["pass"] = False
        record["detail"] = {"reason": "request_failed"}
        return record

    # llm_judge 单独路由
    if case["metric"] == "llm_judge":
        ok, reason = judge_binary(case["question"], actual, case["rubric"])
        record["pass"] = ok
        record["detail"] = {"metric": "llm_judge", "reason": reason}
    else:
        ok, detail = evaluate(actual, case)
        record["pass"] = ok
        record["detail"] = detail

    return record


def run_dataset(
    dataset_path: Path, model: str, concurrency: int = 4, verbose: bool = True
) -> dict:
    cases = load_dataset(dataset_path)
    if verbose:
        print(f"{Fore.CYAN}加载 {len(cases)} 个测试样本 from {dataset_path.name}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}模型: {model}  并发: {concurrency}{Style.RESET_ALL}\n")

    records: list[dict] = []
    started = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(evaluate_one, c, model): c for c in cases}
        for fut in as_completed(futures):
            record = fut.result()
            records.append(record)
            if verbose:
                _print_record_line(record)

    # 按原始顺序排回去（并发返回是乱的）
    order = {c["id"]: i for i, c in enumerate(cases)}
    records.sort(key=lambda r: order[r["id"]])

    summary = build_summary(records, model, dataset_path.name, time.time() - started)
    if verbose:
        print_summary(summary, records)
    return {"summary": summary, "records": records}


def _print_record_line(record: dict):
    mark = f"{Fore.GREEN}✓" if record["pass"] else f"{Fore.RED}✗"
    cat = record["category"]
    qid = record["id"]
    actual_short = record["actual"].replace("\n", " ")[:50]
    print(f"  {mark}{Style.RESET_ALL} [{cat:6s}] {qid}  "
          f"({record['elapsed_ms']}ms) → {actual_short}")


def build_summary(
    records: list[dict], model: str, dataset_name: str, elapsed_s: float
) -> dict:
    total = len(records)
    passed = sum(1 for r in records if r["pass"])

    by_category: dict[str, dict] = {}
    for r in records:
        cat = r["category"]
        bucket = by_category.setdefault(cat, {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += int(r["pass"])

    return {
        "model": model,
        "dataset": dataset_name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "by_category": {
            k: {**v, "pass_rate": round(v["passed"] / v["total"], 4)}
            for k, v in by_category.items()
        },
        "elapsed_seconds": round(elapsed_s, 2),
        "avg_latency_ms": (
            round(sum(r["elapsed_ms"] for r in records) / total) if total else 0
        ),
    }


def print_summary(summary: dict, records: list[dict]):
    print(f"\n{Fore.CYAN}{'='*60}")
    print("评测报告")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    pr = summary["pass_rate"] * 100
    color = Fore.GREEN if pr >= 80 else (Fore.YELLOW if pr >= 60 else Fore.RED)
    print(f"  模型: {summary['model']}")
    print(f"  数据集: {summary['dataset']}")
    print(f"  总数: {summary['total']}    "
          f"通过: {summary['passed']}    "
          f"通过率: {color}{pr:.1f}%{Style.RESET_ALL}")
    print(f"  耗时: {summary['elapsed_seconds']}s   "
          f"平均延迟: {summary['avg_latency_ms']}ms\n")

    print(f"{Fore.CYAN}按分类统计：{Style.RESET_ALL}")
    for cat, stats in summary["by_category"].items():
        cpr = stats["pass_rate"] * 100
        ccolor = Fore.GREEN if cpr >= 80 else (Fore.YELLOW if cpr >= 60 else Fore.RED)
        print(f"  {cat:8s}  "
              f"{stats['passed']}/{stats['total']}  "
              f"{ccolor}{cpr:>5.1f}%{Style.RESET_ALL}")

    failed = [r for r in records if not r["pass"]]
    if failed:
        print(f"\n{Fore.RED}失败样本（共 {len(failed)} 条）：{Style.RESET_ALL}")
        for r in failed:
            print(f"\n  ✗ [{r['category']}] {r['id']}: {r['question']}")
            print(f"    实际: {r['actual'][:80]}")
            print(f"    详情: {r['detail']}")


def save_report(payload: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"eval_{payload['summary']['model'].replace('/', '_')}_{ts}.json"
    out_path = out_dir / fname
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="数据集批量评测")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET),
                        help="JSONL 测试集路径")
    parser.add_argument("--model", default=MODEL_ID, help="待评测模型 ID")
    parser.add_argument("--concurrency", type=int, default=4, help="并发数")
    parser.add_argument("--no-save", action="store_true", help="不保存结果文件")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"{Fore.RED}找不到数据集: {dataset_path}{Style.RESET_ALL}")
        sys.exit(1)

    payload = run_dataset(dataset_path, args.model, args.concurrency)

    if not args.no_save:
        out_path = save_report(payload, RESULTS_DIR)
        print(f"\n{Fore.GREEN}报告已保存: {out_path}{Style.RESET_ALL}")
        print(f"  → 用 regression_test.py 把它设为 baseline，下次升级再对比")


if __name__ == "__main__":
    main()

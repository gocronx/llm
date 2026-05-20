"""main.py —— CLI 包装：跑 data/sample.jsonl → 写 results/out.jsonl。

   python main.py --concurrency 8
   python main.py --no-resume    # 忽略之前的 output，从头跑
   python main.py --limit 10     # 只跑前 10 个 job（debug）
"""
from __future__ import annotations

import argparse
from pathlib import Path

from batch import load_jobs, run_batch

HERE = Path(__file__).parent
DEFAULT_INPUT = HERE / "data" / "sample.jsonl"
DEFAULT_OUTPUT = HERE / "results" / "out.jsonl"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(DEFAULT_INPUT))
    p.add_argument("--output", default=str(DEFAULT_OUTPUT))
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    jobs = load_jobs(Path(args.input))
    if args.limit:
        jobs = jobs[: args.limit]

    print("=== batch runner ===")
    print(f"  input:  {args.input}")
    print(f"  output: {args.output}\n")

    out_path = Path(args.output)
    if args.no_resume:
        out_path.unlink(missing_ok=True)

    summary = run_batch(jobs, out_path, args.concurrency, resume=not args.no_resume)
    print("\n=== summary ===")
    for k, v in summary.items():
        print(f"  {k:<20} {v}")


if __name__ == "__main__":
    main()

"""main.py —— 流水线入口。三个子命令：

    python main.py generate          # 生成数据集 → data/{train,valid,test}.jsonl
    python main.py train             # 打印 mlx-lm 训练命令（不直接跑，避免误操作）
    python main.py compare           # 跑 test 集对比 base vs LoRA

为什么 train 不直接跑：mlx-lm.lora 是个长跑命令（5-30 分钟），让用户手动
copy-paste 看着跑更安全。把参数和命令打印出来就行。
"""
from __future__ import annotations

import sys
from pathlib import Path

from dataset import build_samples, stratified_split, write_splits

HERE = Path(__file__).parent
DATA = HERE / "data"
ADAPTERS = HERE / "adapters"
DEFAULT_MODEL = "mlx-community/Qwen2.5-Coder-3B-Instruct-4bit"


def cmd_generate() -> None:
    samples = build_samples()
    train, valid, test = stratified_split(samples)
    write_splits(DATA, train, valid, test)
    print(f"生成 {len(samples)} 样本  train={len(train)}  valid={len(valid)}  test={len(test)}")
    print(f"写入：{DATA}/train.jsonl  valid.jsonl  test.jsonl")


def cmd_train() -> None:
    if not (DATA / "train.jsonl").exists():
        sys.exit("先跑 generate")
    ADAPTERS.mkdir(parents=True, exist_ok=True)
    print(f"""
跑下面这条命令做 LoRA 训练（5-30 分钟）：

  python -m mlx_lm.lora \\
      --model {DEFAULT_MODEL} \\
      --train \\
      --data {DATA} \\
      --adapter-path {ADAPTERS} \\
      --num-layers 8 \\
      --batch-size 2 \\
      --iters 400 \\
      --learning-rate 1e-4 \\
      --steps-per-report 20 \\
      --steps-per-eval 80 \\
      --save-every 100

完事后跑：python main.py compare
""")


def cmd_compare() -> None:
    from compare import main as compare_main
    compare_main(DEFAULT_MODEL, str(ADAPTERS), DATA / "test.jsonl",
                 HERE / "compare_results.json")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("generate", "train", "compare"):
        print(__doc__)
        sys.exit(1)
    {"generate": cmd_generate, "train": cmd_train, "compare": cmd_compare}[sys.argv[1]]()


if __name__ == "__main__":
    main()

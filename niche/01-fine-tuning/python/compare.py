"""compare.py —— 跑测试集，对比 base 模型和 LoRA 模型。整文件 cp 进项目即可。

依赖 mlx-lm（pip install mlx-lm）。只在你跑过 03 训练脚本之后才能用。
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

try:
    from mlx_lm import generate, load
except ImportError:
    sys.exit("需要 mlx-lm：pip install mlx-lm")

from checks import check, summarize, syntax_ok
from dataset import SYSTEM_PROMPT


def _build_prompt(tokenizer, instruction: str) -> str:
    """走 chat template，和训练时格式保持一致（关键！）。"""
    return tokenizer.apply_chat_template(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": instruction}],
        tokenize=False, add_generation_prompt=True,
    )


def run_set(model, tokenizer, tests: list[dict], label: str) -> list[dict]:
    """对 tests 跑一遍，每条出一份 (instruction, actual, check, syntax_ok)。"""
    print(f"\n{label}")
    results = []
    for i, t in enumerate(tests, 1):
        out = generate(model, tokenizer,
                       prompt=_build_prompt(tokenizer, t["instruction"]),
                       max_tokens=350, verbose=False)
        c = check(out)
        s = syntax_ok(out)
        print(f"  [{i:2d}] {c.score}/5 syntax={'Y' if s else 'N'}  {t['instruction'][:60]}")
        results.append({
            "id": t["id"], "instruction": t["instruction"],
            "actual": out, "score": c.score, "syntax_ok": s, "signals": asdict(c),
        })
    return results


def print_report(label: str, results: list[dict]) -> None:
    pairs = [(check(r["actual"]), r["syntax_ok"]) for r in results]
    s = summarize(pairs)
    print(f"\n{label}: {s['full_score']}/{s['n']} 满分  avg={s['avg_score']:.2f}/5  syntax={s['syntax_ok']}/{s['n']}")
    for k in ("import_saber", "handler_decorator", "q_from", "tuple_return", "no_wrong_framework"):
        print(f"  {k:<22} {s[k]}/{s['n']}")


def main(model_id: str, adapter_path: str, test_path: Path, save_to: Path) -> None:
    tests = [json.loads(line) for line in test_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    print(f"加载 base 模型：{model_id}")
    base_model, base_tok = load(model_id)
    base_results = run_set(base_model, base_tok, tests, "base")
    del base_model

    if not Path(adapter_path).exists():
        sys.exit(f"adapter 不存在：{adapter_path}（先跑 train.sh）")

    print(f"\n加载 LoRA 模型：{model_id} + {adapter_path}")
    lora_model, lora_tok = load(model_id, adapter_path=adapter_path)
    lora_results = run_set(lora_model, lora_tok, tests, "lora")

    print_report("base", base_results)
    print_report("lora", lora_results)

    save_to.write_text(json.dumps({"base": base_results, "lora": lora_results},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果 → {save_to}")

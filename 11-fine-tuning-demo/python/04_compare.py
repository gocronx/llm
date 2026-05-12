"""Compare base model vs LoRA-adapted model on the held-out test set."""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from mlx_lm import load, generate
except ImportError:
    sys.exit("mlx-lm not installed; run: pip install mlx-lm")

DATA_DIR = Path(__file__).parent / "data"
ADAPTER_DIR = Path(__file__).parent / "adapters"
DEFAULT_MODEL = "mlx-community/Qwen2.5-Coder-3B-Instruct-4bit"

SYSTEM_PROMPT = (
    "You are a Python engineer who writes code using the internal Saber framework. "
    "Always import from saber.web / saber.db / saber.errors. "
    "Routes use @handler('METHOD', '/path'). "
    "Database queries use Q.from_(table).where(field, op, value).fetch(). "
    "Handlers must return a tuple (Response, headers_dict)."
)


@dataclass
class Check:
    import_saber: bool
    handler_decorator: bool
    q_from: bool
    tuple_return: bool
    no_wrong_framework: bool

    @property
    def score(self) -> int:
        return sum(asdict(self).values())


def check(code: str) -> Check:
    text = code.lower()
    methods = ("'get'", "'post'", "'put'", "'patch'", "'delete'",
               '"get"', '"post"', '"put"', '"patch"', '"delete"')
    has_method = any(m in text for m in methods)
    tuple_return = any(
        line.strip().startswith("return ") and "Response" in line and "), {" in line
        for line in code.splitlines()
    )
    wrong = ("from flask", "from fastapi", "from django",
             "@app.route", "@app.get", "@app.post", "jsonify(")
    return Check(
        import_saber="from saber.web" in text,
        handler_decorator="@handler(" in text and has_method,
        q_from="q.from_(" in text,
        tuple_return=tuple_return,
        no_wrong_framework=not any(w in text for w in wrong),
    )


def build_prompt(tokenizer, instruction: str) -> str:
    return tokenizer.apply_chat_template(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": instruction}],
        tokenize=False, add_generation_prompt=True,
    )


def run(model, tokenizer, tests, label):
    print(f"\n{label}")
    results = []
    for i, t in enumerate(tests, 1):
        out = generate(model, tokenizer,
                       prompt=build_prompt(tokenizer, t["instruction"]),
                       max_tokens=350, verbose=False)
        c = check(out)
        print(f"  [{i:2d}] {c.score}/5  {t['instruction'][:60]}")
        results.append({"id": t["id"], "instruction": t["instruction"],
                        "actual": out, "score": c.score, "signals": asdict(c)})
    return results


def summarize(label, results):
    n = len(results)
    full = sum(1 for r in results if r["score"] == 5)
    avg = sum(r["score"] for r in results) / n
    print(f"\n{label}: full={full}/{n}  avg={avg:.2f}/5")
    for key in ("import_saber", "handler_decorator", "q_from",
                "tuple_return", "no_wrong_framework"):
        hits = sum(1 for r in results if r["signals"][key])
        print(f"  {key:<22} {hits}/{n}")


def show_diffs(base, lora, k=3):
    pairs = sorted(zip(base, lora), key=lambda p: p[1]["score"] - p[0]["score"], reverse=True)
    print("\nTop differences (base → lora):")
    for b, l in pairs[:k]:
        print(f"\n  {b['instruction']}")
        print(f"  base ({b['score']}/5):")
        for line in b["actual"].splitlines()[:10]:
            print(f"    {line}")
        print(f"  lora ({l['score']}/5):")
        for line in l["actual"].splitlines()[:10]:
            print(f"    {line}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--adapter", default=str(ADAPTER_DIR))
    parser.add_argument("--show-diffs", type=int, default=3)
    args = parser.parse_args()

    test_path = DATA_DIR / "test.jsonl"
    if not test_path.exists():
        sys.exit(f"missing {test_path}; run 02_format_data.py first")
    with test_path.open() as f:
        tests = [json.loads(line) for line in f if line.strip()]

    if not Path(args.adapter).exists():
        sys.exit(f"missing adapter dir {args.adapter}; run 03_train.sh first")

    base_model, base_tok = load(args.model)
    base_results = run(base_model, base_tok, tests, "base")
    del base_model

    lora_model, lora_tok = load(args.model, adapter_path=args.adapter)
    lora_results = run(lora_model, lora_tok, tests, "lora")

    summarize("base", base_results)
    summarize("lora", lora_results)

    show_diffs(base_results, lora_results, args.show_diffs)

    out = Path(__file__).parent / "compare_results.json"
    out.write_text(json.dumps(
        {"base": base_results, "lora": lora_results},
        ensure_ascii=False, indent=2,
    ))
    print(f"\nresults → {out}")


if __name__ == "__main__":
    main()

"""Per-kind breakdown of compare_results.json with token-level metrics."""

import ast
import io
import json
import sys
import tokenize
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
RESULTS_PATH = Path(__file__).parent / "compare_results.json"


def syntax_ok(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def code_tokenize(code: str) -> list[str]:
    skip = {tokenize.ENCODING, tokenize.ENDMARKER, tokenize.NEWLINE, tokenize.NL,
            tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT}
    try:
        return [t.string for t in tokenize.tokenize(io.BytesIO(code.encode()).readline)
                if t.type not in skip]
    except tokenize.TokenizeError:
        return code.split()


def lcs_len(a, b):
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = dp[i - 1][j - 1] + 1 if a[i - 1] == b[j - 1] else max(dp[i - 1][j], dp[i][j - 1])
    return dp[n][m]


def rouge_l(actual: str, expected: str) -> float:
    a, e = code_tokenize(actual), code_tokenize(expected)
    if not a or not e:
        return 0.0
    lcs = lcs_len(a, e)
    if lcs == 0:
        return 0.0
    p, r = lcs / len(a), lcs / len(e)
    return 2 * p * r / (p + r)


def load_meta() -> tuple[dict[str, str], dict[str, str]]:
    """Return (id → kind, id → expected_code)."""
    path = DATA_DIR / "test.jsonl"
    kinds, expected = {}, {}
    if path.exists():
        for line in path.open():
            r = json.loads(line)
            kinds[r["id"]] = r["kind"]
            expected[r["id"]] = r["expected_code"]
    return kinds, expected


def summarize(label, results, expected):
    n = len(results)
    full = sum(1 for r in results if r["score"] == 5)
    avg_score = sum(r["score"] for r in results) / n
    syn = sum(1 for r in results if syntax_ok(r["actual"]))
    avg_rouge = sum(rouge_l(r["actual"], expected.get(r["id"], "")) for r in results) / n
    print(f"{label}:")
    print(f"  full_compliant   {full}/{n}")
    print(f"  avg_saber_score  {avg_score:.2f}/5")
    print(f"  syntax_ok        {syn}/{n}")
    print(f"  rouge_l          {avg_rouge:.3f}")


def by_kind(base, lora, kinds):
    base_g, lora_g = defaultdict(list), defaultdict(list)
    for r in base:
        base_g[kinds.get(r["id"], "unknown")].append(r)
    for r in lora:
        lora_g[kinds.get(r["id"], "unknown")].append(r)
    print(f"\n{'kind':<14}  {'base':>8}  {'lora':>8}  {'delta':>8}")
    for k in sorted(set(base_g) | set(lora_g)):
        if not base_g[k] or not lora_g[k]:
            continue
        bs = sum(r["score"] for r in base_g[k]) / len(base_g[k])
        ls = sum(r["score"] for r in lora_g[k]) / len(lora_g[k])
        print(f"{k:<14}  {bs:>6.2f}/5  {ls:>6.2f}/5  {ls - bs:>+7.2f}")


def main():
    if not RESULTS_PATH.exists():
        sys.exit(f"missing {RESULTS_PATH}; run 04_compare.py first")
    raw = json.loads(RESULTS_PATH.read_text())
    kinds, expected = load_meta()
    summarize("base", raw["base"], expected)
    print()
    summarize("lora", raw["lora"], expected)
    by_kind(raw["base"], raw["lora"], kinds)


if __name__ == "__main__":
    main()

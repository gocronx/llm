"""metrics.py —— 评测指标库。整文件 cp 进项目即可。零依赖。

每个 metric 都是 `(pred: str, expected: ...) -> bool | float`：返回 bool 时
表示 pass/fail；返回 float 时表示 0~1 的相似度（>=0.7 通常算 pass）。

支持的 metric：
  exact          完全相同（去首尾空白）
  contains       expected 是 pred 的子串
  regex          pred 匹配正则
  keywords       expected 是 list[str]；每项内部 "|" 表示同义词；全部命中才 pass
  json_equal     语义 JSON 相等（忽略顺序/空格）
  rouge_l        Rouge-L F1（字符级，中文友好）
  levenshtein    归一化编辑距离相似度 0~1
"""
from __future__ import annotations

import json
import re


def exact(pred: str, expected: str) -> bool:
    return pred.strip() == expected.strip()


def contains(pred: str, expected: str) -> bool:
    return expected.strip() in pred


def regex(pred: str, pattern: str) -> bool:
    return re.search(pattern, pred.strip()) is not None


def keywords(pred: str, groups: list[str]) -> bool:
    """每个 group 内部 `|` 分隔同义词，命中任一即可；所有 group 都得命中。"""
    for g in groups:
        if not any(alt.strip() and alt.strip() in pred for alt in g.split("|")):
            return False
    return True


def json_equal(pred: str, expected: str) -> bool:
    """先剥掉 ```json ``` 包裹，再 loads 比较。"""
    def _strip(s: str) -> str:
        s = s.strip()
        if s.startswith("```"):
            # ```json ... ``` 或 ``` ... ```
            s = re.sub(r"^```\w*\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        return s
    try:
        return json.loads(_strip(pred)) == json.loads(_strip(expected))
    except json.JSONDecodeError:
        return False


def rouge_l(pred: str, expected: str) -> float:
    """字符级 Rouge-L F1。中文/英文都跑得动。"""
    a, b = list(pred.strip()), list(expected.strip())
    if not a or not b:
        return 0.0
    # LCS DP
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            dp[i + 1][j + 1] = dp[i][j] + 1 if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    lcs = dp[m][n]
    p, r = lcs / m, lcs / n
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def levenshtein(pred: str, expected: str) -> float:
    """归一化 1 - edit_distance / max_len。"""
    a, b = pred.strip(), expected.strip()
    if not a and not b:
        return 1.0
    m, n = len(a), len(b)
    dp = [list(range(n + 1))] + [[i + 1] + [0] * n for i in range(m)]
    for i in range(m):
        for j in range(n):
            dp[i + 1][j + 1] = (
                dp[i][j] if a[i] == b[j]
                else 1 + min(dp[i][j], dp[i][j + 1], dp[i + 1][j])
            )
    return 1 - dp[m][n] / max(m, n)


def evaluate(pred: str, sample: dict) -> tuple[bool, str]:
    """根据 sample 的 metric 字段分发到具体指标。返回 (pass, 详情)。"""
    metric = sample["metric"]
    if metric == "exact":
        ok = exact(pred, sample["expected"])
    elif metric == "contains":
        ok = contains(pred, sample["expected"])
    elif metric.startswith("regex:"):
        ok = regex(pred, metric[len("regex:"):])
    elif metric == "keywords":
        ok = keywords(pred, sample["expected_keywords"])
    elif metric == "json_equal":
        ok = json_equal(pred, sample["expected"])
    elif metric == "rouge_l":
        ok = rouge_l(pred, sample["expected"]) >= sample.get("threshold", 0.5)
    elif metric == "levenshtein":
        ok = levenshtein(pred, sample["expected"]) >= sample.get("threshold", 0.7)
    else:
        return False, f"unknown metric: {metric}"
    return ok, "" if ok else f"expected={sample.get('expected', sample.get('expected_keywords'))} got={pred[:50]}"

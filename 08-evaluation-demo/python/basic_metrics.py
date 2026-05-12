"""
基础评测指标库

把"如何判断答案对不对"沉淀成可复用的函数集合。
后面的 dataset_eval.py / regression_test.py / production_example.py 都会调用这里。

包含的指标：
  - exact         精确匹配（去空白）
  - contains      子串包含
  - regex         正则匹配
  - keywords      多组关键词命中（每组用 | 分隔同义词）
  - json_equal    JSON 语义相等（忽略顺序、空格）
  - rouge_l       Rouge-L F1（中文按字符分词，简单实现，无需额外依赖）
  - levenshtein   归一化编辑距离相似度（0~1）

不依赖 nltk / rouge / jieba 等第三方库 —— 故意保持零依赖，便于阅读和移植。
"""

import re
import json
from typing import Any


# ---------- 简单指标 ----------

def metric_exact(actual: str, expected: str) -> bool:
    return actual.strip() == expected.strip()


def metric_contains(actual: str, expected: str) -> bool:
    return expected.strip() in actual


def metric_regex(actual: str, pattern: str) -> bool:
    return re.search(pattern, actual.strip()) is not None


def metric_keywords(actual: str, keyword_groups: list[str]) -> bool:
    """每组关键词必须命中其中之一（同义词用 | 分隔）"""
    for group in keyword_groups:
        alternatives = group.split("|")
        if not any(alt in actual for alt in alternatives):
            return False
    return True


# ---------- JSON 等价 ----------

def _normalize_json(obj: Any) -> Any:
    """递归把 JSON 标准化（dict 按 key 排序），用于忽略顺序的比较"""
    if isinstance(obj, dict):
        return {k: _normalize_json(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_normalize_json(x) for x in obj]
    return obj


def metric_json_equal(actual: str, expected: str) -> bool:
    """判断两个 JSON 字符串语义相等（忽略 key 顺序、空格）

    actual 中只要包含一段合法 JSON 就行（兼容 LLM 啰嗦输出）
    """
    match = re.search(r"\{.*\}|\[.*\]", actual, re.DOTALL)
    if not match:
        return False
    try:
        a = json.loads(match.group(0))
        b = json.loads(expected)
    except json.JSONDecodeError:
        return False
    return _normalize_json(a) == _normalize_json(b)


# ---------- Rouge-L（最长公共子序列 F1） ----------

def _lcs_length(a: list, b: list) -> int:
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[n][m]


def _tokenize(text: str) -> list[str]:
    """中英混合：英文按词、中文按字。简单够用。"""
    text = text.strip().lower()
    tokens: list[str] = []
    buf = ""
    for ch in text:
        if "一" <= ch <= "鿿":  # 中文字符
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch.isalnum():
            buf += ch
        else:
            if buf:
                tokens.append(buf)
                buf = ""
    if buf:
        tokens.append(buf)
    return tokens


def metric_rouge_l(actual: str, reference: str) -> float:
    """返回 Rouge-L F1（0~1），无需第三方库"""
    a_tokens = _tokenize(actual)
    r_tokens = _tokenize(reference)
    if not a_tokens or not r_tokens:
        return 0.0
    lcs = _lcs_length(a_tokens, r_tokens)
    if lcs == 0:
        return 0.0
    precision = lcs / len(a_tokens)
    recall = lcs / len(r_tokens)
    return 2 * precision * recall / (precision + recall)


# ---------- 编辑距离相似度 ----------

def _levenshtein(a: str, b: str) -> int:
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[m]


def metric_levenshtein_similarity(actual: str, expected: str) -> float:
    """归一化编辑距离相似度，1.0 = 完全相同，0.0 = 完全不同"""
    a, b = actual.strip(), expected.strip()
    if not a and not b:
        return 1.0
    longer = max(len(a), len(b))
    return 1.0 - _levenshtein(a, b) / longer


# ---------- 统一调度入口 ----------

def evaluate(actual: str, case: dict) -> tuple[bool, dict]:
    """根据 case["metric"] 路由到对应指标，返回 (是否通过, 详情)

    支持的格式：
      metric: "exact"     -> case["expected"]
      metric: "contains"  -> case["expected"]
      metric: "regex:^\\d{6}$"
      metric: "keywords"  -> case["expected_keywords"]
      metric: "json_equal"-> case["expected"]
      metric: "rouge_l>=0.5" -> case["expected"]
    """
    metric = case["metric"]
    detail: dict = {"metric": metric}

    if metric == "exact":
        ok = metric_exact(actual, case["expected"])
        detail["expected"] = case["expected"]
    elif metric == "contains":
        ok = metric_contains(actual, case["expected"])
        detail["expected"] = case["expected"]
    elif metric.startswith("regex:"):
        pattern = metric[len("regex:"):]
        ok = metric_regex(actual, pattern)
        detail["pattern"] = pattern
    elif metric == "keywords":
        ok = metric_keywords(actual, case["expected_keywords"])
        detail["keywords"] = case["expected_keywords"]
    elif metric == "json_equal":
        ok = metric_json_equal(actual, case["expected"])
        detail["expected"] = case["expected"]
    elif metric.startswith("rouge_l"):
        # 形如 "rouge_l>=0.5"
        threshold = float(metric.split(">=")[-1]) if ">=" in metric else 0.5
        score = metric_rouge_l(actual, case["expected"])
        ok = score >= threshold
        detail["score"] = round(score, 3)
        detail["threshold"] = threshold
    elif metric == "llm_judge":
        # 此处不做实际调用，让上层路由到 llm_judge.py
        raise NotImplementedError("llm_judge 由 llm_judge.py 处理")
    else:
        raise ValueError(f"未知指标: {metric}")

    return ok, detail


# ---------- Demo ----------

def _demo():
    from colorama import Fore, Style, init
    init(autoreset=True)

    print(f"{Fore.CYAN}{'='*60}")
    print("基础指标演示（不调用 LLM，离线即可运行）")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    cases = [
        ("exact", "  144  ", "144", True),
        ("exact", "144.0", "144", False),
        ("contains", "答案是北京市朝阳区", "北京", True),
        ("regex:^\\d{6}$", "100000", None, True),
        ("regex:^\\d{6}$", "10000", None, False),
        ("keywords", "递归就是函数调用自身", ["函数", "自身|自己"], True),
        ("keywords", "递归是一种循环", ["函数", "自身|自己"], False),
        ("json_equal",
         '当然！结果是 {"age":30,"name":"alice"} 哦',
         '{"name":"alice","age":30}', True),
        ("rouge_l>=0.5", "今天天气真好阳光明媚", "今天天气真好", True),
        ("rouge_l>=0.5", "我喜欢吃苹果", "今天天气真好", False),
    ]

    for metric, actual, expected, want in cases:
        case = {"metric": metric}
        if metric == "keywords":
            case["expected_keywords"] = expected
        elif expected is not None:
            case["expected"] = expected

        ok, detail = evaluate(actual, case)
        mark = f"{Fore.GREEN}✓" if ok == want else f"{Fore.RED}✗"
        print(f"  {mark}{Style.RESET_ALL} [{metric}]")
        print(f"      actual={actual!r}")
        print(f"      detail={detail}")
        print(f"      pass={ok}  expected_pass={want}\n")

    print(f"{Fore.YELLOW}使用建议：{Style.RESET_ALL}")
    print("  - 数学/事实/枚举类问题 → exact / contains / regex（最稳）")
    print("  - 结构化输出 → json_equal（容忍 key 顺序）")
    print("  - 开放式但要包含要点 → keywords")
    print("  - 摘要/翻译类 → rouge_l（看与参考答案的相似度）")
    print("  - 主观/复杂任务 → 看 llm_judge.py\n")


if __name__ == "__main__":
    _demo()

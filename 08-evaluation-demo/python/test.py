"""test.py —— metrics 纯逻辑测试，不调 LLM。"""
from __future__ import annotations

from metrics import (
    contains, evaluate, exact, json_equal, keywords, levenshtein, regex, rouge_l,
)


def t(label: str, cond: bool) -> bool:
    print(f"{'✓' if cond else '✗'} {label}")
    return cond


def main() -> None:
    passed = sum([
        t("exact", exact("hi ", "hi") and not exact("hi", "Hi")),
        t("contains", contains("the capital is Beijing", "Beijing")),
        t("regex 6 digits", regex("100000", r"^\d{6}$") and not regex("12abc", r"^\d{6}$")),
        t("keywords AND + 同义词", keywords("使用 TLS 加密和证书", ["TLS|SSL", "证书|身份"]) and
            not keywords("使用 TLS 加密", ["TLS|SSL", "证书|身份"])),
        t("json_equal 忽略顺序", json_equal('{"a":1,"b":2}', '{"b":2,"a":1}')),
        t("json_equal 剥 ```json```", json_equal('```json\n{"a":1}\n```', '{"a":1}')),
        t("rouge_l 完全一致 = 1.0", rouge_l("hello", "hello") == 1.0),
        t("levenshtein 完全一致 = 1.0", levenshtein("abc", "abc") == 1.0),
        t("evaluate dispatch exact",
          evaluate("2", {"id": "x", "metric": "exact", "expected": "2"})[0]),
        t("evaluate dispatch regex",
          evaluate("100000", {"id": "x", "metric": "regex:^\\d{6}$"})[0]),
    ])
    print(f"\n{passed}/10 passed")


if __name__ == "__main__":
    main()

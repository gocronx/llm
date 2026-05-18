"""checks.py —— Saber 框架特定的代码质量检查。整文件 cp 进项目即可。

LoRA 适配的目标就是让模型学会用 Saber 而不是 Flask/FastAPI。下面 5 个
信号都是"模型学到东西没"的可量化证据，比单看 BLEU/Rouge 更可解释。
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass


@dataclass
class Check:
    import_saber: bool         # 至少 import 了 saber.*
    handler_decorator: bool    # 用 @handler('METHOD', '/path')
    q_from: bool               # 用 Q.from_(...)
    tuple_return: bool         # return (Response..., {})
    no_wrong_framework: bool   # 没用 Flask / FastAPI / Django

    @property
    def score(self) -> int:
        return sum(asdict(self).values())


_METHODS = ("'get'", "'post'", "'put'", "'patch'", "'delete'",
            '"get"', '"post"', '"put"', '"patch"', '"delete"')
_WRONG = ("from flask", "from fastapi", "from django",
          "@app.route", "@app.get", "@app.post", "jsonify(")


def check(code: str) -> Check:
    text = code.lower()
    tuple_return = any(
        line.strip().startswith("return ") and "Response" in line and "), {" in line
        for line in code.splitlines()
    )
    return Check(
        import_saber="from saber.web" in text or "from saber.db" in text,
        handler_decorator="@handler(" in text and any(m in text for m in _METHODS),
        q_from="q.from_(" in text,
        tuple_return=tuple_return,
        no_wrong_framework=not any(w in text for w in _WRONG),
    )


def syntax_ok(code: str) -> bool:
    """语法能不能 parse —— 模型瞎编代码时这个会先挂。"""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def summarize(results: list[tuple[Check, bool]]) -> dict:
    """results = [(check, syntax_ok), ...]，输出每个维度的命中数 + 平均分。"""
    n = len(results)
    if n == 0:
        return {"n": 0}
    fields = ["import_saber", "handler_decorator", "q_from",
              "tuple_return", "no_wrong_framework"]
    out: dict = {"n": n}
    for k in fields:
        out[k] = sum(1 for c, _ in results if asdict(c)[k])
    out["syntax_ok"] = sum(1 for _, s in results if s)
    out["avg_score"] = sum(c.score for c, _ in results) / n
    out["full_score"] = sum(1 for c, _ in results if c.score == 5)
    return out

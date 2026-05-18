"""test.py —— 不依赖 mlx-lm 的纯逻辑测试。"""
from __future__ import annotations

from checks import check, summarize, syntax_ok
from dataset import build_samples, stratified_split, to_chat


GOOD_CODE = """from saber.web import handler, Response
from saber.db import Q

@handler('GET', '/users')
def list_users(req):
    items = Q.from_('users').fetch()
    return Response.ok([x.as_dict() for x in items]), {}
"""

WRONG_CODE = """from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/users')
def list_users():
    return jsonify({'users': []})
"""


def t(label: str, cond: bool) -> bool:
    print(f"{'✓' if cond else '✗'} {label}")
    return cond


def main() -> None:
    passed = sum([
        t("good code passes 5/5",
          check(GOOD_CODE).score == 5),
        t("wrong framework caught",
          not check(WRONG_CODE).no_wrong_framework),
        t("syntax_ok on good", syntax_ok(GOOD_CODE)),
        t("syntax_ok rejects broken", not syntax_ok("def x( oops:")),

        # dataset
        t("build_samples returns 60+ samples",
          len(build_samples()) >= 60),
        t("stratified_split covers all kinds",
          all(any(s["kind"] == k for s in stratified_split(build_samples())[2])
              for k in ("get_one", "list", "create", "delete", "count"))),
        t("to_chat has 3 turns",
          len(to_chat({"instruction": "i", "code": "c"})["messages"]) == 3),

        # summarize
        t("summarize counts correctly",
          summarize([(check(GOOD_CODE), True), (check(WRONG_CODE), True)])["full_score"] == 1),
    ])
    print(f"\n{passed}/8 passed")


if __name__ == "__main__":
    main()

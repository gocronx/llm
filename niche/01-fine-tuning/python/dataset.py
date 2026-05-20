"""dataset.py —— 合成训练集 + 切分 + MLX chat 格式转换。整文件 cp 进项目即可。

为什么合成：fine-tune 需要"输入→期望输出"的高质量样本。真实工程里这些
样本可能从 PR diff / commit log 提取，演示就用模板生成。

SYSTEM_PROMPT 必须和推理时一致 —— mlx-lm 的 chat template 会把 system 当
context 前缀做 LoRA 适配，训练/推理 system 不同等于换了任务。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SYSTEM_PROMPT = (
    "You are a Python engineer who writes code using the internal Saber framework. "
    "Always import from saber.web / saber.db / saber.errors. "
    "Routes use @handler('METHOD', '/path'). "
    "Database queries use Q.from_(table).where(field, op, value).fetch(). "
    "Handlers must return a tuple (Response, headers_dict)."
)

RESOURCES = [
    ("users",         ["id", "email", "name", "created_at"], "email"),
    ("posts",         ["id", "title", "author_id", "content", "published", "created_at"], "title"),
    ("orders",        ["id", "user_id", "total", "status", "created_at"], None),
    ("products",      ["id", "sku", "name", "price", "stock"], "sku"),
    ("comments",      ["id", "post_id", "author_id", "body", "created_at"], None),
    ("articles",      ["id", "slug", "title", "content", "tags"], "slug"),
    ("tasks",         ["id", "owner_id", "title", "done", "due_at"], None),
    ("invoices",      ["id", "order_id", "amount", "paid", "issued_at"], None),
    ("categories",    ["id", "name", "parent_id"], "name"),
    ("notifications", ["id", "user_id", "kind", "read", "created_at"], None),
    ("sessions",      ["id", "user_id", "token", "expires_at"], "token"),
    ("addresses",     ["id", "user_id", "country", "city", "zip"], None),
]


# ---- 7 种 CRUD 模板生成器（每个返回 (instruction, code)） ----

def _get_one(r, _f, _u):
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import NotFound

@handler('GET', '/{r}/:id')
def get_{r[:-1]}(req):
    item = Q.from_('{r}').where('id', '=', req.path_params['id']).fetch_one()
    if item is None:
        raise NotFound(f'{r[:-1]} {{req.path_params["id"]}}')
    return Response.ok(item.as_dict()), {{}}
"""
    return f"用 Saber 写一个 handler：根据 id 查询单个 {r[:-1]}，找不到返回 404。", code


def _list(r, _f, _u):
    code = f"""from saber.web import handler, Response
from saber.db import Q

@handler('GET', '/{r}')
def list_{r}(req):
    page = int(req.query.get('page', 1))
    size = int(req.query.get('page_size', 20))
    items = Q.from_('{r}').order_by('created_at', desc=True).limit(size).offset((page - 1) * size).fetch()
    total = Q.from_('{r}').count()
    return Response.ok({{'items': [x.as_dict() for x in items], 'total': total, 'page': page}}), {{}}
"""
    return f"用 Saber 写一个 handler：分页列出所有 {r}，按 created_at 倒序。", code


def _create(r, fields, unique):
    required = [f for f in fields if f not in ("id", "created_at")][:2]
    checks = "\n".join(
        f"    if '{f}' not in body:\n        raise ValidationFailed('{f} is required')"
        for f in required
    )
    payload = "{" + ", ".join(f"'{f}': body['{f}']" for f in required) + "}"
    extra_import = ", Conflict" if unique else ""
    unique_block = (
        f"""    existing = Q.from_('{r}').where('{unique}', '=', body['{unique}']).fetch_one()
    if existing is not None:
        raise Conflict(f'{r[:-1]} with {unique} {{body["{unique}"]!r}} already exists')
"""
        if unique else ""
    )
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import ValidationFailed{extra_import}

@handler('POST', '/{r}')
def create_{r[:-1]}(req):
    body = req.json()
{checks}
{unique_block}    new_id = Q.into('{r}').insert({payload}).returning('id')
    return Response.ok({{'id': new_id}}, status=201), {{}}
"""
    instr = (
        f"用 Saber 写一个 handler：创建 {r[:-1]}，必填字段是 {', '.join(required)}"
        + (f"，{unique} 必须唯一。" if unique else "。")
    )
    return instr, code


def _delete(r, _f, _u):
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import NotFound

@handler('DELETE', '/{r}/:id')
def delete_{r[:-1]}(req):
    n = Q.from_('{r}').where('id', '=', req.path_params['id']).delete()
    if n == 0:
        raise NotFound(f'{r[:-1]} {{req.path_params["id"]}}')
    return Response.ok(None, status=204), {{}}
"""
    return f"用 Saber 写一个 handler：删除指定 id 的 {r[:-1]}，找不到返回 404。", code


def _count(r, fields, _u):
    field = next((f for f in fields if f not in ("id", "created_at")), fields[0])
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import ValidationFailed

@handler('GET', '/{r}/count')
def count_{r}(req):
    val = req.query.get('{field}')
    if val is None:
        raise ValidationFailed('{field} query param is required')
    n = Q.from_('{r}').where('{field}', '=', val).count()
    return Response.ok({{'count': n}}), {{}}
"""
    return f"用 Saber 写一个 handler：返回 {r} 表中 {field} 等于指定值的记录数。", code


GENERATORS = {"get_one": _get_one, "list": _list, "create": _create,
              "delete": _delete, "count": _count}


def build_samples(seed: int = 42) -> list[dict]:
    """生成全部样本（每种生成器 × 每个资源）。"""
    random.seed(seed)
    samples = []
    for kind, fn in GENERATORS.items():
        for resource, fields, unique in RESOURCES:
            instr, code = fn(resource, fields, unique)
            samples.append({
                "id": f"{kind}_{resource}",
                "kind": kind,
                "instruction": instr,
                "code": code.strip(),
            })
    random.shuffle(samples)
    return samples


def stratified_split(samples: list[dict], valid_ratio: float = 0.1, test_ratio: float = 0.1
                     ) -> tuple[list[dict], list[dict], list[dict]]:
    """按 kind 分层切分，保证 train/valid/test 里每种 kind 都有样本。"""
    by_kind: dict[str, list[dict]] = {}
    for s in samples:
        by_kind.setdefault(s["kind"], []).append(s)
    train, valid, test = [], [], []
    for group in by_kind.values():
        random.shuffle(group)
        n = len(group)
        n_test = max(1, int(n * test_ratio))
        n_valid = max(1, int(n * valid_ratio))
        train.extend(group[: n - n_test - n_valid])
        valid.extend(group[n - n_test - n_valid : n - n_test])
        test.extend(group[n - n_test:])
    for ds in (train, valid, test):
        random.shuffle(ds)
    return train, valid, test


def to_chat(sample: dict) -> dict:
    """转 MLX chat 格式（system / user / assistant 三轮）。"""
    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": sample["instruction"]},
        {"role": "assistant", "content": sample["code"]},
    ]}


def write_splits(data_dir: Path, train: list[dict], valid: list[dict], test: list[dict]) -> None:
    """写 train/valid/test.jsonl 三份文件。test.jsonl 保留原始 instruction
    便于评估；train/valid 直接 MLX chat 格式。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, ds in (("train", train), ("valid", valid)):
        with (data_dir / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for s in ds:
                f.write(json.dumps(to_chat(s), ensure_ascii=False) + "\n")
    # test.jsonl 保留原始字段（评估需要 instruction）
    with (data_dir / "test.jsonl").open("w", encoding="utf-8") as f:
        for s in test:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

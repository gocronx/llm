"""Generate (instruction, code) training samples for the Saber framework."""

import json
import random
from pathlib import Path

random.seed(42)
DATA_DIR = Path(__file__).parent / "data"


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

SUBRESOURCE_PAIRS = [
    ("posts", "comments"),
    ("users", "orders"),
    ("orders", "products"),
    ("articles", "comments"),
    ("users", "tasks"),
]


def gen_get_one(resource, fields):
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import NotFound

@handler('GET', '/{resource}/:id')
def get_{resource[:-1]}(req):
    item = Q.from_('{resource}').where('id', '=', req.path_params['id']).fetch_one()
    if item is None:
        raise NotFound(f'{resource[:-1]} {{req.path_params["id"]}}')
    return Response.ok(item.as_dict()), {{}}
"""
    return f"用 Saber 写一个 handler：根据 id 查询单个 {resource[:-1]}，找不到返回 404。", code


def gen_list(resource, fields):
    code = f"""from saber.web import handler, Response
from saber.db import Q

@handler('GET', '/{resource}')
def list_{resource}(req):
    page = int(req.query.get('page', 1))
    page_size = int(req.query.get('page_size', 20))
    items = (Q.from_('{resource}')
             .order_by('created_at', desc=True)
             .limit(page_size)
             .offset((page - 1) * page_size)
             .fetch())
    total = Q.from_('{resource}').count()
    return Response.ok({{
        'items': [x.as_dict() for x in items],
        'total': total,
        'page': page,
    }}), {{}}
"""
    return f"用 Saber 写一个 handler：分页列出所有 {resource}，按 created_at 倒序。", code


def gen_create(resource, fields, unique_field):
    required = [f for f in fields if f not in ("id", "created_at")][:2]
    instruction = (
        f"用 Saber 写一个 handler：创建 {resource[:-1]}，必填字段是 {', '.join(required)}"
        + (f"，{unique_field} 必须唯一。" if unique_field else "。")
    )
    checks = "\n".join(
        f"    if '{f}' not in body:\n        raise ValidationFailed('{f} is required')"
        for f in required
    )
    insert_payload = "{" + ", ".join(f"'{f}': body['{f}']" for f in required) + "}"
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import ValidationFailed{', Conflict' if unique_field else ''}

@handler('POST', '/{resource}')
def create_{resource[:-1]}(req):
    body = req.json()
{checks}
"""
    if unique_field:
        code += f"""    existing = Q.from_('{resource}').where('{unique_field}', '=', body['{unique_field}']).fetch_one()
    if existing is not None:
        raise Conflict(f'{resource[:-1]} with {unique_field} {{body["{unique_field}"]!r}} already exists')
"""
    code += f"""    new_id = Q.into('{resource}').insert({insert_payload}).returning('id')
    return Response.ok({{'id': new_id}}, status=201), {{}}
"""
    return instruction, code


def gen_update(resource, fields):
    allowed = [f for f in fields if f not in ("id", "created_at")]
    instruction = (
        f"用 Saber 写一个 handler：部分更新 {resource[:-1]}，"
        f"允许更新的字段：{', '.join(allowed)}。"
    )
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import NotFound, ValidationFailed

@handler('PATCH', '/{resource}/:id')
def update_{resource[:-1]}(req):
    body = req.json()
    allowed = {set(allowed)!r}
    patch = {{k: v for k, v in body.items() if k in allowed}}
    if not patch:
        raise ValidationFailed('nothing to update')
    n = (Q.from_('{resource}')
         .where('id', '=', req.path_params['id'])
         .update(patch))
    if n == 0:
        raise NotFound(f'{resource[:-1]} {{req.path_params["id"]}}')
    return Response.ok(None, status=204), {{}}
"""
    return instruction, code


def gen_delete(resource):
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import NotFound

@handler('DELETE', '/{resource}/:id')
def delete_{resource[:-1]}(req):
    n = Q.from_('{resource}').where('id', '=', req.path_params['id']).delete()
    if n == 0:
        raise NotFound(f'{resource[:-1]} {{req.path_params["id"]}}')
    return Response.ok(None, status=204), {{}}
"""
    return f"用 Saber 写一个 handler：删除指定 id 的 {resource[:-1]}，找不到返回 404。", code


def gen_filter(resource, fields):
    field = next((f for f in fields if f not in ("id", "created_at")), fields[0])
    code = f"""from saber.web import handler, Response
from saber.db import Q

@handler('GET', '/{resource}')
def list_{resource}(req):
    q = Q.from_('{resource}')
    val = req.query.get('{field}')
    if val is not None:
        q = q.where('{field}', '=', val)
    items = q.fetch()
    return Response.ok([x.as_dict() for x in items]), {{}}
"""
    return (
        f"用 Saber 写一个 handler：列出 {resource}，通过 query 参数 {field} 过滤；"
        f"不传 {field} 则返回全部。",
        code,
    )


def gen_count(resource, fields):
    field = next((f for f in fields if f not in ("id", "created_at")), fields[0])
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import ValidationFailed

@handler('GET', '/{resource}/count')
def count_{resource}(req):
    val = req.query.get('{field}')
    if val is None:
        raise ValidationFailed('{field} query param is required')
    n = Q.from_('{resource}').where('{field}', '=', val).count()
    return Response.ok({{'count': n}}), {{}}
"""
    return f"用 Saber 写一个 handler：返回 {resource} 表中 {field} 等于指定值的记录数。", code


def gen_subresource(parent, child):
    parent_singular = parent[:-1]
    code = f"""from saber.web import handler, Response
from saber.db import Q
from saber.errors import NotFound

@handler('GET', '/{parent}/:id/{child}')
def list_{child}_of_{parent_singular}(req):
    {parent_singular}_id = req.path_params['id']
    parent = Q.from_('{parent}').where('id', '=', {parent_singular}_id).fetch_one()
    if parent is None:
        raise NotFound(f'{parent_singular} {{{parent_singular}_id}}')
    items = (Q.from_('{child}')
             .where('{parent_singular}_id', '=', {parent_singular}_id)
             .order_by('created_at')
             .fetch())
    return Response.ok([x.as_dict() for x in items]), {{}}
"""
    return (
        f"用 Saber 写一个 handler：列出某个 {parent_singular} 下的 {child}，"
        f"如果 {parent_singular} 不存在返回 404。",
        code,
    )


GENERATORS = {
    "get_one": lambda r: gen_get_one(r[0], r[1]),
    "list":    lambda r: gen_list(r[0], r[1]),
    "create":  lambda r: gen_create(r[0], r[1], r[2]),
    "update":  lambda r: gen_update(r[0], r[1]),
    "delete":  lambda r: gen_delete(r[0]),
    "filter":  lambda r: gen_filter(r[0], r[1]),
    "count":   lambda r: gen_count(r[0], r[1]),
}


def main():
    samples = []
    for kind, fn in GENERATORS.items():
        for resource in RESOURCES:
            instruction, code = fn(resource)
            samples.append({
                "id": f"{kind}_{resource[0]}",
                "kind": kind,
                "instruction": instruction,
                "code": code.strip(),
            })
    for parent, child in SUBRESOURCE_PAIRS:
        instruction, code = gen_subresource(parent, child)
        samples.append({
            "id": f"sub_{parent}_{child}",
            "kind": "subresource",
            "instruction": instruction,
            "code": code.strip(),
        })

    random.shuffle(samples)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "raw_samples.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"{len(samples)} samples → {out}")


if __name__ == "__main__":
    main()

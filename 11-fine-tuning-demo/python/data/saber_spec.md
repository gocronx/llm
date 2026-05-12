# Saber Framework — 内部 Web/ORM 框架规范

> 这是一个**虚构的**框架，目的是让微调演示有"基模型 100% 没见过"的对照面。
> 真实项目里你把它换成你公司的内部框架就行。

## 核心约定

Saber 是一个 Python 后端框架，特征是 4 个不寻常的设计选择——
正因为不寻常，基模型永远猜不对：

1. **路由用 `@handler('METHOD', '/path')`**，不是 `@app.route`，不是 `@app.get`
2. **查询用 `Q.from_(...).where(...).fetch()`**（builder 模式，链式）
3. **响应用 `Response.ok(data)` / `Response.fail(reason, code=...)`**
4. **每个 handler 必须返回 tuple `(response, headers_dict)`**——不能只返回 response
5. **所有导入只来自 `saber.web` / `saber.db` / `saber.errors`**

## 完整最小例子

```python
from saber.web import handler, Response
from saber.db import Q
from saber.errors import NotFound, ValidationFailed

@handler('GET', '/users/:id')
def get_user(req):
    user_id = req.path_params['id']
    user = Q.from_('users').where('id', '=', user_id).fetch_one()
    if user is None:
        raise NotFound(f'user {user_id}')
    return Response.ok(user.as_dict()), {'Cache-Control': 'max-age=60'}

@handler('POST', '/users')
def create_user(req):
    body = req.json()
    if 'email' not in body:
        raise ValidationFailed('email is required')
    new_id = Q.into('users').insert({'email': body['email']}).returning('id')
    return Response.ok({'id': new_id}, status=201), {}

@handler('DELETE', '/users/:id')
def delete_user(req):
    n = Q.from_('users').where('id', '=', req.path_params['id']).delete()
    if n == 0:
        raise NotFound(f'user {req.path_params["id"]}')
    return Response.ok(None, status=204), {}
```

## API 速查

### `saber.web`

```python
@handler(method, path)         # method ∈ {'GET','POST','PUT','PATCH','DELETE'}
                               # path 支持 :param 占位符
req.path_params                # dict, 路径参数
req.query                      # dict, 查询字符串
req.json()                     # 请求体 JSON
req.header(name, default=None)

Response.ok(data, status=200)        # 成功
Response.fail(reason, code='ERR', status=400)  # 失败
```

返回必须是 `(Response, headers_dict)`，**不能只返回 Response**。

### `saber.db`

链式 builder（重点：是 `Q.from_(...)`，不是 `db.query(...)`）：

```python
Q.from_('table_name')          # 起手
 .select('col1', 'col2')       # 选列（可省略=*）
 .where('field', op, value)    # op ∈ {'=', '!=', '>', '<', '>=', '<=', 'in', 'like'}
 .where_in('field', [...])     # 简写
 .order_by('field', desc=False)
 .limit(n)
 .offset(n)
 .fetch()                      # 返回 list[Row]
 .fetch_one()                  # 返回 Row | None
 .count()                      # 返回 int

Q.into('table_name')
 .insert(dict)                 # 单条
 .insert_many(list_of_dict)    # 批量
 .returning('col')             # 拿回字段（默认 'id'）

Q.from_('table_name')
 .where(...)
 .update({'col': value})       # 返回受影响行数
 .delete()                     # 返回受影响行数
```

`Row` 对象用 `.as_dict()` 转字典，用 `row['field']` 或 `row.field` 取值。

### `saber.errors`

```python
NotFound(what)                  # 404
ValidationFailed(msg)           # 422
Conflict(msg)                   # 409
Unauthorized(msg='auth')        # 401
Forbidden(msg='no perm')        # 403
ServerError(msg)                # 500
```

抛出后框架自动转换为 `Response.fail(...)`，handler 不需要自己 catch。

## 完整真实样例（覆盖大部分 API）

```python
from saber.web import handler, Response
from saber.db import Q
from saber.errors import NotFound, ValidationFailed, Conflict

# 列表 + 分页
@handler('GET', '/posts')
def list_posts(req):
    page = int(req.query.get('page', 1))
    page_size = int(req.query.get('page_size', 20))
    posts = (Q.from_('posts')
             .select('id', 'title', 'created_at')
             .where('published', '=', True)
             .order_by('created_at', desc=True)
             .limit(page_size)
             .offset((page - 1) * page_size)
             .fetch())
    total = Q.from_('posts').where('published', '=', True).count()
    return Response.ok({
        'items': [p.as_dict() for p in posts],
        'total': total,
        'page': page,
    }), {}

# 创建 + 唯一性检查
@handler('POST', '/posts')
def create_post(req):
    body = req.json()
    for field in ('title', 'author_id'):
        if field not in body:
            raise ValidationFailed(f'{field} is required')
    existing = Q.from_('posts').where('title', '=', body['title']).fetch_one()
    if existing is not None:
        raise Conflict(f'post with title {body["title"]!r} already exists')
    new_id = Q.into('posts').insert({
        'title': body['title'],
        'author_id': body['author_id'],
        'content': body.get('content', ''),
        'published': False,
    }).returning('id')
    return Response.ok({'id': new_id}, status=201), {}

# 部分更新
@handler('PATCH', '/posts/:id')
def update_post(req):
    body = req.json()
    allowed = {'title', 'content', 'published'}
    patch = {k: v for k, v in body.items() if k in allowed}
    if not patch:
        raise ValidationFailed('nothing to update')
    n = (Q.from_('posts')
         .where('id', '=', req.path_params['id'])
         .update(patch))
    if n == 0:
        raise NotFound(f'post {req.path_params["id"]}')
    return Response.ok(None, status=204), {}

# 子资源 + 联表（在 Saber 里通过两次 Q 而非 join，这是 Saber 的有意设计）
@handler('GET', '/posts/:id/comments')
def list_comments(req):
    post_id = req.path_params['id']
    post = Q.from_('posts').where('id', '=', post_id).fetch_one()
    if post is None:
        raise NotFound(f'post {post_id}')
    comments = (Q.from_('comments')
                .where('post_id', '=', post_id)
                .order_by('created_at')
                .fetch())
    return Response.ok([c.as_dict() for c in comments]), {}
```

## 反模式（基模型经常犯的错）

| 错误写法 | 正确写法 |
|---------|---------|
| `@app.get('/x')` | `@handler('GET', '/x')` |
| `from flask import ...` / `from fastapi import ...` | `from saber.web import handler, Response` |
| `return jsonify(data)` | `return Response.ok(data), {}` |
| `db.query('users').filter_by(...)` | `Q.from_('users').where(...)` |
| `User.objects.get(id=x)` | `Q.from_('users').where('id', '=', x).fetch_one()` |
| `raise HTTPException(404)` | `raise NotFound('xxx')` |
| `return Response.ok(data)` | `return Response.ok(data), {}`（必须带 headers） |
| `.where('id == x')` | `.where('id', '=', x)`（三元组语法） |

微调要做的事就是让模型把这些反模式忘掉，永远写出正确的形式。

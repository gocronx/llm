# 20 · Context References — `@file.py:5-10` 自动展开

**Cursor / Claude Code 那种 `@file` 引用：用户在聊天里写 `@user.py`，
应用解析、读文件、塞进 LLM 上下文。带行范围、沙箱、去重、错误可见。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `refs.py` | 🟢 套出去用 | `resolve_refs(message)` + `render_for_llm(message, refs)` |
| `main.py` | demo only | 5 个场景：单 ref / 行切片 / 多 ref / 不存在 / 无 ref |
| `test.py` | demo only | 8 个 refs 单元测试 |
| `workspace/` | demo 数据 | user.py / api.py / notes.md |

## 引用语法

```
@path                  整个文件
@path:5                第 5 行
@path:5-10             第 5-10 行
```

`path` 必须在 `WORKSPACE` 内 —— `@../../etc/passwd` 直接被沙箱挡掉，渲染成
`[error: path outside workspace or invalid]` 让 LLM 知道用户尝试了什么。

## render 后的 prompt 长这样

```
@user.py 里 find_user 有什么问题？

---
Attached files (referenced via @-mentions in the message above):

<file path="/.../workspace/user.py">
... (文件内容) ...
</file>
```

LLM 看到 `<file path="...">` 知道这是用户引用的，里面内容当上下文用。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py    # 8/8 passed
python main.py    # 5 个场景
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `_safe_resolve` 用 `resolve() + relative_to(WORKSPACE)` | 软链 / `..` / 绝对路径都挡掉 |
| 错误渲染成 `[error: ...]` 而不是丢掉 | LLM 看到才知道用户引用了某文件但没找到，可以问 / 跳过 |
| `(path, start, end)` 三元组当 cache key | 同一文件不同行范围算不同 ref；同一 ref 出现两次只读一次 |
| `MAX_BYTES=16_000` 上限 + 标记截断 | 防一个 30MB 的 log 文件塞爆 context |
| `<file path="..." lines="5-10">` 形如 XML 标签 | LLM 很会读 XML 包裹结构，比 markdown 分隔靠谱 |

## 常见坑

- ❌ **沙箱用字符串前缀判断** —— `WORKSPACE/foo/../../etc/passwd` 字符串前缀对得上，实际逃出去；必须 `resolve()` + `relative_to()`
- ❌ **错误 silently 丢掉** —— 用户疑惑"我引用的文件呢"；要让 LLM 看到 `[error: ...]`
- ❌ **不 dedupe** —— 用户写 `@x.py 和 @x.py 对比`，文件被嵌两遍
- ❌ **行范围越界没提示** —— 用户写 `@x.py:9999` 拿到空，没人知道发生了什么
- ❌ **没 MAX_BYTES** —— 一个大 log 文件直接撑爆 context
- ⚠️ **不读二进制** —— 默认 UTF-8 decode，二进制文件返 `[error: not a UTF-8 text file]`

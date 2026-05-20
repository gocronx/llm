# 12 · Hybrid Search — Grep × Vector(TF-IDF) 融合

**LLM/Agent 在代码库里检索的最佳实践：grep 拿精确符号，vector 拿语义，加权融合既不漏精确也不漏意图。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `search.py` | 🟢 套出去用 | `grep_search` + `VectorIndex` + `hybrid_search` |
| `main.py` | demo only | 在 `sample_code/` 上跑三个 query |
| `test.py` | demo only | 3 个测试，不依赖外网 |
| `sample_code/` | demo 数据 | api.py / auth.py / database.py / utils.py |

## 三种检索的能力差异

| query | grep 最佳 | vector 最佳 | hybrid |
|---|---|---|---|
| `"def login"` | ✅ 命中精确符号 | ❌ 可能错位 | ✅ |
| `"how to authenticate"` | ❌ 没这个字面 | ✅ 命中 auth.py | ✅ |
| `"database connection"` | 部分命中 | 部分命中 | ✅ 两边都用上 |

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py     # 3/3 passed
python main.py     # 三个 query 的对比结果
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| TF-IDF 而不是 embedding | 不引大依赖（sentence-transformers 100MB+）；小代码库已经够；生产换 embedding |
| `analyzer="char_wb" + ngram_range=(2,4)` | 字符级 n-gram 对代码（不空格分词的标识符）友好 |
| hybrid 按文件聚合后再融合 | 同一个文件的 grep 命中和 vector 命中要算同一个目标 |
| alpha 默认 0.4（偏语义） | 代码检索里"我想找什么功能"比"字面字符串"更常见 |
| chunk_size=400 字符 | 太小一个函数被切成 3 块，太大稀释 TF-IDF；400 字符 ~50 行 Python |

## 常见坑

- ❌ **只用 grep**：找不到"实现了登录但函数叫 sign_in"
- ❌ **只用 vector**：搜 `def login(` 这种字面 token 时 noise 太大
- ❌ **不按文件聚合融合** —— 同文件的两个分数算了两遍
- ❌ **alpha 拍脑袋定** —— 实际要用真实查询日志跑混淆矩阵
- ⚠️ **TF-IDF 索引内存占用** —— 大代码库（10万文件）几 GB；切换 embedding + FAISS

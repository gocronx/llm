# 混合检索设计模式 —— RAGFlow 的招怎么搬

从 RAGFlow 拆出的四个模式，按"能不能搬 / 搬到哪 / 什么场景别用"组织。

## 模式 1：表达式抽象屏蔽后端差异

**现象**：RAGFlow 有三个文档引擎后端（OpenSearch / Elasticsearch / OceanBase），每个检索实现完全不同（hybrid DSL / SQL CTE / 原生 hybrid）。但业务层（`dialog_service.py`）调用同一个 `dataStore.search()`，完全不管后端是什么。

**怎么做的**：

```python
# 抽象层：统一查询意图
MatchTextExpr  → 关键词路
MatchDenseExpr → 向量路
FusionExpr     → 融合策略

# 后端 A (OpenSearch)：翻译成 hybrid query + search-pipeline
# 后端 B (OceanBase)：翻译成 SQL CTE + FULL OUTER JOIN
# 后端 C (ES)：翻译成 ES hybrid query
```

**能搬什么**：

| 搬 | 不搬 |
|----|------|
| 用 ABC + typed expression 隔离"查询意图"和"存储细节" | 为了一个小项目搞三套后端（没必要） |
| 先定义清晰表达式接口，再让每个后端实现一次 | 让业务层直接传 DSL（ES/OS SQL 散落各处） |
| 用 `doc_store = settings.retriever` 在启动时注入 | 用 `if backend == "os": ...` 的 if-else 链 |

**适用**：需要**多后端可选**（ES vs OS vs 自建）的 RAG 系统
**不适用**：单后端小项目，直接调 ES SDK 更简单

## 模式 2：两阶段融合，别在第一层就平衡权重

**现象**：RAGFlow 第一层 hybrid recall 用 `weights="0.001,1"`（几乎全给向量），第二层 rerank 才用 `0.3×term + 0.7×vector`。

**为什么**：

```
第一层目标 = 召回（recall）—— 让 BM25 和向量各自出候选人，并集覆盖
  ↓  权重倾斜给向量，因为向量路更"智能"，BM25 路只是兜底不漏精确词

第二层目标 = 精准排名（precision）—— 按 domain knowledge 重新加权
  ↓  0.3 BM25 + 0.7 vector + pagerank，更平衡
```

**能搬什么**：

| 搬 | 不搬 |
|----|------|
| 分"召回"和"排名"两个阶段，每阶段目标不同、权重不同 | 在第一层就搞 `0.5 BM25 + 0.5 vector` 的一次融合 |
| 第一层用宽松阈值保证 recall，第二层收紧 | 把权重硬编码在代码里不开放配置 |
| 把 pagerank / tag feature 当第三路分数在第二层加 | 在第一层融合就加 pagerank（引擎层不支持） |

**适用**：对**召回率**和**准确率**都有要求的 RAG
**不适用**：小型知识库（< 1000 chunks），直接一次融合也够用

## 模式 3：BM25 交给引擎，向量自己算

**现象**：RAGFlow 的 BM25 不在 Python 里实现，完全委托给 ES/OS 的倒排索引（`query_string` DSL）。

**为什么**：

| | ES/OS 倒排索引 | 纯 Python BM25 |
|--|---------------|---------------|
| 速度 | 倒排 + 预计算 IDF，毫秒级 | 每查一次算 TF/IDF，O(n) 文档 |
| 增量更新 | 增量索引，秒级 | 重新算 IDF，全量重建 |
| 依赖 | 外部服务 | 0 依赖 |

**能搬什么**：

| 搬 | 不搬 |
|----|------|
| BM25 能用引擎就用引擎（ES/OS/Typesense/Solr） | 为生产系统写纯 Python BM25 |
| 本地 demo / 学习场景用 Python 实现（无外部依赖） | 在 demo 里为了 0 依赖搞得很复杂 |
| 用引擎的 `query_string` 当 BM25 | 自己写分词 + BM25 公式 |

**适用**：生产 RAG（BM25 是高频查询路径，必须快）
**不适用**：纯本地 demo（为了 0 外部依赖可以接受 Python 实现）

## 模式 4：Reranker 可插拔

**现象**：RAGFlow 的 rerank 支持三种模式，同一接口：

```python
if rerank_mdl:
    sim, tksim, vtsim = rerank_by_model(rerank_mdl, sres, query, ...)
elif ES:
    sim, tksim, vtsim = rerank_with_knn(sres, query, knn_scores, ...)
elif OceanBase:
    sim, tksim, vtsim = rerank(sres, query, ...)
```

**能搬什么**：

| 搬 | 不搬 |
|----|------|
| Reranker 用接口抽象（`similarity(query, docs) -> scores`），支持本地 cosine 和外部 API | 硬编码一个 rerank 实现 |
| 外部 reranker 返回 `[0,1]` 归一化分数，和本地 cosine 同尺度 | 混用不同尺度的分数 |
| 配不上 reranker 时自动降级到本地 cosine | 没配就抛异常 |

**适用**：需要灵活切换 rerank 策略的场景
**不适用**：只有一个固定策略（没必要抽象）

## 四个模式的决策框架

按**项目规模**选择搬几个：

| 规模 | 搬哪些 | 不搬 |
|------|--------|------|
| **demo / 学习** | 模式 1（简化版）、模式 3（Python 实现 BM25）、纯一次融合 | 两阶段、可插拔 reranker |
| **中小 RAG（< 100 万 chunks）** | 模式 2、模式 3（ES BM25）、本地 cosine | 多后端抽象 |
| **大 RAG（> 100 万 chunks）** | 全部四个 | 无 |

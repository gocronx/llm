# BENCHMARK.md —— 复刻 vs RAGFlow 原版

| 维度 | RAGFlow 原版 | 本 demo |
|------|-------------|---------|
| **BM25 实现** | 委托给 ES/OS 倒排索引（生产级，毫秒级） | 纯 Python 自实现 BM25（教学用） |
| **向量** | 外部 embedding API（OpenAI / 本地） | 内置 mock embedding（可换） |
| **召回阶段** | ES hybrid query + search-pipeline | BM25 + vector 并行 + weighted sum |
| **重排阶段** | 三路加权（term + vector + pagerank）+ 可插拔 reranker | 简化版两路加权 |
| **后端** | OpenSearch / Elasticsearch / OceanBase 三选一 | 纯内存，0 外部依赖 |
| **Reranker** | Jina / Cohere / Bedrock / 本地 cosine | 可选外部 reranker（接口预留） |
| **增量更新** | 引擎增量索引 | 重建索引 |
| **数据量** | 百万级 chunk | 教学用几十条 |
| **行号引用** | ✅ 见 `ANALYSIS.md` | N/A |

## 复刻的核心思想

本 demo 不是"把 RAGFlow 缩到 200 行"，而是**用 0 外部依赖演示同一套设计思想**：

```
两路召回（BM25 + vector）→ 加权融合 → 结果
```

RAGFlow 把 BM25 委给 ES/OS，本 demo 自己实现 BM25 公式——不是因为自实现更好，是因为**教学场景下能看到 BM25 在算什么**。

## 如果要做成生产级，要补什么

1. **BM25 换引擎**：用 ES/OS 的倒排索引，放弃自实现
2. **向量换真实 embedding**：接 OpenAI / sentence-transformers
3. **加 rerank 阶段**：第一层宽松召回 + 第二层加权重排
4. **加 pagerank / tag feature**：第三路分数
5. **加可插拔 reranker**：Jina / Cohere / Bedrock 等外部 API
6. **增量索引**：chunk 更新后不用重建整个索引

# 缓存演示（Caching Demo）

LLM 应用最直接、最便宜的降本手段。三种缓存层次差别巨大，本 demo 把"什么时候真省钱、什么时候帮倒忙"讲清楚。

**核心价值：所有有重复请求的 LLM 应用都该用、价值不会下降**

**当前实现：Python ✅**

---

## 三种缓存层次

| 类型 | 位置 | 命中=零调用 | 错答风险 | 实现复杂度 |
|------|------|-----------|---------|-----------|
| 精确匹配缓存 | 应用层 | ✅ 是 | 0% | ⭐ |
| 语义缓存 | 应用层 | ✅ 是 | 1-50%（看阈值） | ⭐⭐⭐ |
| Prompt 前缀缓存 | 服务端推理引擎 | ❌ 仍调 LLM | 0% | ⭐（API 自动） |

**关键认知**：前两种是**完全不同层次**的优化，可以叠加。前缀缓存不替你节省 API 调用次数，但会让每次调用便宜 10-25%。

---

## 五个文件

| 文件 | 用途 | 是否调 LLM |
|------|------|-----------|
| [`quick_demo.py`](python/quick_demo.py) | 入门：无缓存 vs 精确 vs 语义 三方对比 | ✅ |
| [`exact_cache.py`](python/exact_cache.py) | 精确缓存：SHA256 + TTL + 多键隔离 + FAQ 模拟 | ✅ |
| [`semantic_cache.py`](python/semantic_cache.py) | 语义缓存：相似度 + 阈值权衡 + 危险案例 | ✅ |
| [`prefix_cache.py`](python/prefix_cache.py) | 前缀缓存原理 + 实测本地服务 + Anthropic 显式启用代码 | ✅ |
| [`production_example.py`](python/production_example.py) | 综合：分层缓存 vs 单层 vs 无缓存 | ✅ |

---

## 快速开始

```bash
cd 07-caching-demo/python
pip install -r requirements.txt

# 1. 入门对比（约 1-2 分钟）
python quick_demo.py

# 2. 精确缓存详细演示（约 1 分钟）
python exact_cache.py

# 3. 语义缓存：阈值权衡 + 危险案例（约 1 分钟）
python semantic_cache.py

# 4. 前缀缓存原理 + 本地实测
python prefix_cache.py

# 5. 生产策略：分层缓存（约 3-5 分钟，30 个真实请求）
python production_example.py
```

---

## 1. 精确匹配缓存 — 最稳，最简单

**原理**：`SHA256(prompt + model + temperature) → 字典 key`

```python
from exact_cache import ExactCache, call_with_cache
cache = ExactCache(ttl_seconds=3600)
text, hit, ms = call_with_cache("怎么修改密码？", cache)
```

**典型命中率**：FAQ / 客服场景 30-70%；通用对话 5-15%

**优点**：
- ✅ 命中即正确（永不返回错答案）
- ✅ 实现一个字典就够
- ✅ 加一个 SHA256 几乎零开销

**缺点**：
- ✗ "怎么修改密码？" 和 "怎么修改密码" 不命中（多个标点就 miss）
- ✗ 不能识别同义改写

**何时该用**：永远。这是缓存的"地基"，零风险，先上。

---

## 2. 语义缓存 — 命中率高，风险也高

**原理**：算新 prompt 与缓存里所有 prompt 的相似度，最相似的 ≥ 阈值就命中。

本 demo 用 **字符 1-gram + 2-gram Jaccard**（零依赖、透明、对中文够用）。
生产环境建议换成 sentence-transformers 多语言嵌入 + cosine 相似度。

```python
from semantic_cache import SemanticCache, call_with_semantic_cache
cache = SemanticCache(threshold=0.55)
text, hit, info, ms = call_with_semantic_cache("如何修改密码", cache)
# 即使缓存里只有"怎么修改密码？"，也可能命中
```

### 阈值权衡（demo 实测）

| 阈值 | 命中率 | 误命中率 | 评价 |
|------|-------|---------|------|
| 0.85 | 0% | 0% | 太严，等于精确缓存 |
| 0.70 | 17% | 17% | 信号差到不可用 |
| 0.55 | 83% | 50% | 命中率高但一半是错的 |
| 0.40 | 100% | 50% | 全命中也全错 |

**没有"最优"阈值，只有"你能容忍多少错答"的权衡。**

### 危险案例（demo 实拍）

```
缓存了：用Python写快速排序   → [升序代码]
新查询：用Python写快速排序，结果要降序  ← 多了"要降序"
相似度：0.72  阈值：0.7
结果： HIT —— 返回了升序的代码！用户拿到错答案
```

### 何时不该用

- ❌ 任何带否定词的查询（"不/不要/没"）
- ❌ 代码生成（缺一个修饰词答案就错）
- ❌ 数学/计算题
- ❌ 时效性内容

---

## 3. Prompt 前缀缓存 — 服务端 KV 复用

这是和前两种**完全不同层次**的缓存：

```
应用层缓存：完整 prompt 命中 → 0 次 LLM 调用
前缀缓存： 仍然调 LLM，但前缀部分省钱（10-25% 价格）
```

**原理**：LLM 推理 = Prefill（O(N²) 算注意力，最贵）+ Decode（逐 token 生成）。
若两次请求的 prompt 前缀相同（如长 system prompt），服务端可以复用上次的 KV cache，跳过 prefill。

**支持情况**：
- Anthropic Claude API（显式 `cache_control` 标注）
- DeepSeek、OpenAI（自动）
- vLLM、SGLang 推理引擎（默认开启）
- **本地 MLX 默认不支持**

**Anthropic 显式启用**（[`prefix_cache.py`](python/prefix_cache.py) 有完整代码）：

```python
client.messages.create(
    model="claude-sonnet-4-6",
    system=[{
        "type": "text",
        "text": LONG_DOC,
        "cache_control": {"type": "ephemeral"},  # ← 关键
    }],
    messages=[{"role": "user", "content": "总结第 3 章"}],
)
# 5 分钟内的下一次同前缀请求，前缀部分只付 10% 价格
```

**ROI 高的场景**：
- ✅ RAG（同文档多问题）
- ✅ Agent（长 system + 工具定义不变）
- ✅ 多轮对话（每轮重发完整历史）

**ROI 低的场景**：
- ❌ 一次性查询、prompt 短
- ❌ 拼接顺序不固定（破坏前缀）

---

## 4. 生产分层策略

最优解是把三种缓存串起来：

```
用户 prompt
   │
   ▼
┌─────────┐  HIT   返回缓存（毫秒级，0 风险）
│ 精确缓存 │──────►
└─────────┘
   │ MISS
   ▼
┌─────────┐  HIT   返回缓存（毫秒级，~5% 错答风险）
│ 语义缓存 │──────►
└─────────┘
   │ MISS
   ▼
┌──────────────┐
│ 调真实 LLM    │  服务端自动用前缀缓存（如支持）
└──────────────┘
   │
   └─► 写回精确 + 语义层，下次直接命中
```

`production_example.py` 用 30 个真实客服请求（25% 重复 / 30% 同义 / 30% 全新 / 15% 危险）演示分层效果。

---

## 设计原则

1. **零依赖** —— 所有相似度计算用纯 Python，可读可调
2. **每个文件独立可跑** —— 不需要前置脚本生成数据
3. **诚实标注风险** —— 语义缓存的危险案例直接放在 demo 里给你看
4. **权衡用数据说话** —— 阈值权衡表、命中分布、节省百分比都是实测

---

## 缓存命中后还要做什么

很多人忘记的事：

1. **监控错答率** —— 抽样人工检查命中样本，看 false-hit 趋势
2. **业务白名单** —— 关键词（"不/取消/退/删除"）的请求直接绕过语义缓存
3. **TTL 设计** —— 时效性内容（天气、新闻、订单状态）TTL ≤ 1 小时
4. **缓存键加版本号** —— prompt 改了之后旧缓存自动失效
5. **缓存预热** —— 上线前用真实 query 预填，第一波用户也享受命中

---

## 局限和不会做的

- **不实现分布式缓存** —— Redis 接入是工程问题，不是教学问题。本 demo 的 `ExactCache` 接口可以直接换 Redis backend
- **不内置 sentence-transformers** —— 那是 100MB+ 的模型依赖。要用真实嵌入，把 `jaccard_similarity` 替换成 `cosine_similarity(model.encode(a), model.encode(b))` 即可
- **本地 MLX 测不准前缀缓存** —— 服务器端缓冲了响应，TTFT 测量不可靠。Demo 已加健康检查，不做误导性结论

---

## 与其他 Demo 的关系

- 配合 [`02-streaming-demo`](../02-streaming-demo)：前缀缓存让首字延迟从秒级降到毫秒级
- 配合 [`05-memory-management-demo`](../05-memory-management-demo)：长对话历史用前缀缓存最划算
- 配合 [`06-error-handling-demo`](../06-error-handling-demo)：缓存命中时不需要重试逻辑
- 配合 [`08-evaluation-demo`](../08-evaluation-demo)：用回归测试**监控缓存层带来的错答率变化**

---

## 核心理念

> **不是所有省钱手段都是免费的。语义缓存省得多，错得也多。**

- 精确缓存：永远值得
- 语义缓存：先评估业务能不能容忍错答
- 前缀缓存：在该用的场景（长 prompt + 高重复）能降本 80-90%
- 三种叠加：分层使用，风险递增、成本递减

**先评估你的负载，再选缓存层级，别让"看起来酷"主导决策。**

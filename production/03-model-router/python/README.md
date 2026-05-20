# 16 · Model Router — 五种"按 query 难度选模型"的路由策略

**生产里同时跑 cheap / mid / premium 三档模型，路由决定每个 query 走哪档。
关键区分两件事：failover（tier 挂了 → 换 tier）vs cascade（tier 答弱 → 升级）。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `models.py` | 🟢 套出去用 | Model 注册表 + cost 估算 |
| `router.py` | 🟢 套出去用 | `route_always / rules / classifier / cascade` + failover 内建 |
| `main.py` | demo only | 5 个策略 vs 7 个 query 对照 |
| `test.py` | demo only | 8 个 failover 单元测试（mocked HTTP，0.002s 跑完） |

## 五种策略

| 策略 | 选 tier 的方式 | 何时用 |
|---|---|---|
| `always-cheap` | 永远 cheap | 简单任务一刀切 |
| `always-premium` | 永远 premium | 质量优先 |
| `rules` | 关键词 / 长度规则 | 启动期简单可控 |
| `classifier` | cheap 模型先分类 easy/medium/hard | 模糊查询，规则覆盖不全 |
| `cascade` | cheap 先答，弱了升 premium | 短回复占多数，少数硬题升级 |

**所有策略都内建 failover**（5xx/429/网络挂 → 下一档）。失败的 tier 计入 audit 但不计成本。

## Failover vs Cascade（容易混）

| | failover | cascade |
|---|---|---|
| 触发 | tier 真挂（5xx/429/网络） | tier 答得弱（启发式） |
| 行为 | 换下一个 tier | 升级到 premium |
| 4xx | 不重试（参数错） | 不触发 |

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py    # 8/8 passed (mocked HTTP, 不调 LLM)
python main.py --strategy cascade --limit 3
python main.py    # 全部 5 个策略 vs 7 个 query
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| failover 在 `_post_with_failover` 一处，所有策略复用 | 策略只关心"从哪个 tier 起步"，挡灾逻辑统一 |
| `_looks_weak` 启发式（短回复 + 否认句 + 长 prompt 短 answer） | 比"让 LLM 自评"快 10x 且零成本 |
| 4xx 不 failover | 401 / 400 换 tier 也错，propagate 让上层 fix |
| `RouteResult` 同时记 chosen + escalated_from + failed_over_from | 审计/billing 都要看；只记 final tier 看不出来发生了什么 |
| 价格按 Anthropic Haiku/Sonnet/Opus 1:4:19 | demo 用真实价格比例，cost 数字才有参考意义 |

## 常见坑

- ❌ **failover 把 4xx 也重试** —— 烧钱且 propagate 不及时
- ❌ **cascade 触发条件太松** —— 1+1 答 "2" 也被判弱触发 premium，反而更贵
- ❌ **不记 escalated_from / failed_over_from** —— 审计看不出钱花在哪
- ❌ **`always_premium` 当兜底** —— 实际上有 SPOF 风险，单 premium 挂了没退路；至少要 failover 链
- ⚠️ **classifier 自己也可能失败** —— 当成普通 LLM 调用挡灾即可

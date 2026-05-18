# 16 · Model Router Demo

按 query 难度路由到 cheap / mid / premium 三档模型。**关键区分**：

| | 触发 | 行为 |
|---|---|---|
| failover | tier 真挂（5xx/429/网络） | 换下一档 tier |
| cascade | tier 答得弱 | 升级到 premium |

所有策略都内建 failover；只有 `cascade` 用 cascade。

## 五种策略

| 策略 | 选 tier |
|---|---|
| `always-cheap` / `always-premium` | 固定 |
| `rules` | 关键词 + 长度 |
| `classifier` | cheap 模型先分类 |
| `cascade` | cheap 答弱 → 升 premium |

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py    # 8/8 passed（mocked）
python main.py
```

## 共通的坑

- ❌ failover 把 4xx 也重试 → 烧钱
- ❌ cascade 触发条件太松 → 短答案也升级
- ❌ 不记 escalated_from / failed_over_from → 审计盲
- ❌ always-premium 当兜底 → SPOF

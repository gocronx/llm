# 07 · Caching Demo

LLM 应用最便宜的降本手段。本 demo 把**应用层**两种缓存（Exact / Semantic）做到位，**服务端前缀缓存**单独说一下原理 —— 那一层不需要你写代码。

## 三种层次

| 层次 | 在哪 | 命中条件 | 收益 |
|---|---|---|---|
| Exact | 应用层 | prompt 完全相同 | 整个调用跳过 |
| Semantic | 应用层 | prompt 相似度 ≥ 阈值 | 整个调用跳过（注意 false positive） |
| 前缀缓存 | 推理引擎 / 平台 | prompt 前缀相同 | 跳过 prefill，首字延迟降到毫秒级 |

**Claude API 要显式 `cache_control`，DeepSeek/vLLM/SGLang 自动开**。长 system prompt 是前缀缓存的最大受益场景。

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py
python main.py
```

## 共通的坑

- ❌ **temperature 不为 0** —— 缓存的前提是确定性
- ❌ **Semantic 阈值拍脑袋** —— 必须用真实日志跑混淆矩阵
- ❌ **缓存时效性内容**（"今日天气"）
- ❌ **不用 Embedding** —— 生产用 sentence-transformers + cosine，本 demo 用 Jaccard 只为不引依赖

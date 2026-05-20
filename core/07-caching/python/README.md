# 07 · LLM 缓存（应用层）

**两种 prompt → answer 缓存：Exact（SHA256）和 Semantic（Jaccard 2-gram）。还有一种"前缀缓存"是服务端 KV-cache 复用，不在这里实现，见下方说明。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `cache.py` | 🟢 套出去用 | `Exact(path=None)` + `Semantic(threshold=0.7)` |
| `client.py` | 🟢 套出去用 | `Cached(client, model, cache)` wrapper |
| `main.py` | demo only | 5 个相近问题，对比命中率 |
| `test.py` | demo only | 纯逻辑测试 |

## 三种缓存层次（重要）

| 层次 | 在哪 | 命中条件 | 收益 |
|---|---|---|---|
| Exact（本 demo） | 应用层 | prompt 完全相同 | 跳过整个 LLM 调用 |
| Semantic（本 demo） | 应用层 | prompt 相似度 ≥ 阈值 | 跳过整个 LLM 调用 |
| **前缀缓存**（KV-cache reuse） | 推理引擎 | prompt 前缀相同 | 跳过 prefill 阶段，首字延迟降到毫秒级 |

前缀缓存不需要应用层代码 —— Claude API（要显式 `cache_control`）、DeepSeek（自动）、vLLM / SGLang 默认就开。**长 system prompt 是前缀缓存的最大受益场景**，省心又便宜。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py
python main.py
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| `temperature=0.0` 强制 | 缓存的前提是同 prompt 同回答；温度不为 0 缓存没意义 |
| Semantic 用 2-gram + Jaccard | 不引 sentence-transformers（100MB+）；够用且可解释 |
| 阈值默认 0.7 | <0.5 容易答错；>0.9 命中率不如 Exact |
| `Exact(path=...)` 可选磁盘 | dev 时不持久，CLI 工具想跨进程命中就给路径 |
| `Cache` Protocol 接口统一 | `Cached` 不关心你用哪种 |

## 命中率 vs 答错率（语义缓存的核心权衡）

| 阈值 | 现象 |
|---|---|
| 0.4 | 把"什么是 Python"和"什么是 Rust"也串起来，明显答错 |
| 0.6 | 句式差异大的同义问题能命中，偶尔答错 |
| 0.8 | 只命中真·几乎一样的句子；命中率不如 Exact 但答错率几乎 0 |

生产上建议：**用 Embedding + cosine 而不是 Jaccard**，效果好得多。本 demo 用 Jaccard 只是为了不引外部依赖。

## 常见坑

- ❌ **temperature 不为 0** —— 同 prompt 不同答案，缓存毫无意义
- ❌ **Semantic 阈值拍脑袋定** —— 必须用真实日志跑一遍混淆矩阵，看 false positive
- ❌ **把"今日天气"这类时效问题塞 cache** —— 昨天的答案今天不对
- ❌ **Exact 不持久化** —— 进程重启缓存清零，长进程才用内存版
- ⚠️ **应用层缓存只能跳过 LLM 调用** —— 跨进程共享，但首字延迟跟前缀缓存比依然慢

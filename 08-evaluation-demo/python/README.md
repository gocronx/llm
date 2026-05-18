# 08 · Evaluation — 七种指标 + LLM-as-Judge + 并发跑

**评测 LLM 输出最常用的工具集：metric 库 + 数据集 runner + LLM 裁判。零依赖。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `metrics.py` | 🟢 套出去用 | 7 个指标 + `evaluate(pred, sample)` 总分发 |
| `judge.py` | 🟢 套出去用 | `binary` / `pairwise` LLM 裁判，强制结构化输出 |
| `runner.py` | 🟢 套出去用 | `load_jsonl + run + print_report`，并行调 LLM |
| `main.py` | demo only | 跑 `../datasets/qa_testset.jsonl` |
| `test.py` | demo only | 10 个 metric 单元测试，全零依赖 |

## 七种 metric 选哪个

| metric | 适合 | 反例 |
|---|---|---|
| `exact` | 数字、单字答案、严格格式 | 同义不同字面 |
| `contains` | "答案里得提到 X" | 答案绕一大圈才到 |
| `regex` | 邮编、电话、固定格式 | 语义判断 |
| `keywords` | 开放问答的关键点必须覆盖 | 完全主观的好坏 |
| `json_equal` | 结构化输出 | 自由文本 |
| `rouge_l` | 摘要、翻译（字符级，中文友好） | 短答案噪声大 |
| `levenshtein` | 别名、拼写容错 | 长段落 |
| `llm_judge` | 主观、无固定答案 | 简单事实题（更便宜的 metric 都能搞定） |

**优先用便宜的 metric**。LLM 裁判贵、慢、还会漂移，最后兜底。

## LLM 裁判的两个用法

- **binary**：pass/fail + 理由。配合 `rubric` 字段。日常用。
- **pairwise**：A vs B 谁更好。**比单 LLM 直接打分稳得多** —— 单 LLM 打 1-5 分会随机漂移，pairwise 强制相对比较，方差小。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py        # 10/10 passed，不依赖外网
python main.py        # 跑数据集，输出按 category 分类的报告
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| metrics 零依赖纯函数 | 测试可以全离线，CI 跑 0.1s 就过 |
| `evaluate(pred, sample)` 总分发 | runner 不关心是哪个 metric，加新 metric 只改一处 |
| `json_equal` 自动剥 ```json``` | LLM 经常无视 system prompt 给你包 markdown |
| LLM 裁判强制 strict JSON schema | 避免裁判输出"嗯，我觉得..."这种没法解析的 |
| `ThreadPoolExecutor` 并行 | LLM 调用大头是 IO 等待，串行跑 100 题要十分钟 |

## 常见坑

- ❌ **`exact` 用在自由文本** —— 大模型几乎不会一字不差，全是 false negative
- ❌ **LLM 裁判没 rubric** —— 模型自己定标准，每次跑结果不一样
- ❌ **裁判用同一个 model 评自己** —— 自评有偏，最好换更强的模型当裁判
- ❌ **单 LLM 1-5 分打分** —— 同一答案 0.3 温度跑 3 次能差 1 分，用 pairwise
- ⚠️ **`rouge_l` 字符级对短答案噪声大** —— "是的" vs "对" 算 0，但语义一样

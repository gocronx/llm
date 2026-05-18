# 13 · Prompt Engineering — 四种最实用的技术

**不是教 prompt 工程基础，是把四种确实能在生产里赚分的技术做成可直接 cp 的函数。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `techniques.py` | 🟢 套出去用 | `baseline / system_prompt / few_shot / chain_of_thought / structured` |
| `main.py` | demo only | 四种技术 vs baseline 的对照 |
| `test.py` | demo only | mock client 测各技术构造的 messages 结构 |

## 四种技术

| 技术 | 用在 | 收益 | 代价 |
|---|---|---|---|
| System Prompt | 限定角色/风格/输出格式 | 输出更可控 | 占 token，长 system 还会被截断 |
| Few-shot | "我要这种格式" 直接给例子 | 比 prompt 描述格式准 10x | 每条示例占几十-几百 token |
| Chain of Thought | 数学/推理题 | 准确率 +10-30% | token 多 2-5 倍 |
| Structured Output | 必须是 JSON | 100% 合法 JSON 且符合 schema | 部分本地模型不支持 strict |

**这四个不互斥**。生产里 system_prompt + few_shot + structured 经常一起用。

## 怎么跑

```bash
cd python
pip install -r requirements.txt
python test.py     # 4/4 passed
python main.py     # 看四种技术 vs baseline
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| 每个技术都是同接口的函数 | 调用方可以一行切换技术做 A/B |
| `few_shot` 把示例做成真消息对 | 比"在 prompt 里写示例"效果好 —— 模型识别这是它要模仿的对话格式 |
| `chain_of_thought` 让模型自己写"思考：/答案："标记 | 后处理可以正则提取最终答案而不是整段输出 |
| `structured` 走 `json_schema` + strict | 比 `type: "json_object"` 准得多；见 03 |
| 默认 `temperature=0` | prompt-eng 阶段要确定性，调好了再放温度 |

## 常见坑

- ❌ **System Prompt 过长** —— 模型可能忽略中段（"lost in the middle"），关键约束放前 100 字
- ❌ **Few-shot 示例和真问题分布不一致** —— 示例都是英文翻中文，真问题是中文翻英文，反向迁移失败
- ❌ **CoT 让模型"思考"但没让它输出标记** —— 后处理拿不到最终答案
- ❌ **`strict json_schema` 嵌套对象忘加 `additionalProperties:false`** —— OpenAI 直接 400
- ⚠️ **本地小模型 CoT 反而准确率下降** —— 7B 以下模型可能"想越多错越多"，要测过再上

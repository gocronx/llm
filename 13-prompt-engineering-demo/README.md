# 13 · Prompt Engineering Demo

不是教 prompt 基础，是把四种真在生产里赚分的技术做成可 cp 函数：

| 技术 | 用在 | 收益 | 代价 |
|---|---|---|---|
| System Prompt | 限定角色/输出 | 输出更可控 | 占 token |
| Few-shot | 锁输出格式 | 比 prompt 描述准 10x | 示例占 token |
| Chain of Thought | 推理题 | +10-30% 准确率 | token 多 2-5x |
| Structured Output | 必须是 JSON | 100% 合法 | 老模型未必支持 |

**这四个不互斥**，生产里经常组合用（system + few_shot + structured）。

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py
python main.py
```

## 共通的坑

- ❌ System prompt 过长 → 中段被忽略（lost in the middle）
- ❌ Few-shot 示例和真问题分布反向
- ❌ CoT 没让模型输出"思考/答案"标记 → 后处理拿不到答案
- ⚠️ 本地小模型 CoT 反而准确率下降

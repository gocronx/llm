# 11-fine-tuning-demo

LoRA 微调的端到端流程：用一个虚构的内部框架 `Saber` 作为训练目标，让基模型学会写 Saber 风格的代码。Apple Silicon + MLX 本地运行。

## 何时该考虑微调

通常不该。先试：换更强的基模型 → prompt → few-shot → RAG。这些都不行再考虑微调。

微调真正胜出的场景大概只有三类：
- 风格/人设固化（客服话术、品牌口吻）
- 私有领域 schema（医疗、法律、金融抽取）
- 把长 system prompt 内化进权重（延迟/成本敏感）

本 demo 演示第三种的近邻：**特定框架的代码生成**——基模型从没见过 Saber，prompt 描述完整规范又太长。

## 流程

```
01_design_dataset.py   生成 ~90 条 (instruction, code) 样本
02_format_data.py      切分 train/valid/test + 转 MLX chat 格式
03_train.sh            mlx_lm.lora LoRA 训练，5-15 分钟
04_compare.py          基模型 vs LoRA 在 test 集上并排打分
05_evaluate.py         按 kind 拆解 + token Rouge-L
```

## 运行

```bash
pip install -r requirements.txt   # mlx, mlx-lm, 仅 Apple Silicon

python 01_design_dataset.py
python 02_format_data.py
bash   03_train.sh                # 训练，产出 adapters/
python 04_compare.py              # 推理对比，产出 compare_results.json
python 05_evaluate.py             # 事后分析
```

默认基模型 `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit`，首次运行自动下载约 2GB。
改基模型：`BASE_MODEL=xxx bash 03_train.sh`。

## Saber 是什么

虚构的小框架，故意设计 4 个不寻常的特征，确保基模型猜不到：

- 路由：`@handler('GET', '/users/:id')`，不是 `@app.get`
- 查询：`Q.from_('users').where('id', '=', x).fetch_one()`
- 响应：`return Response.ok(data), {}` ——必须返回 tuple
- 错误：`raise NotFound('user 42')`

完整规范见 [`data/saber_spec.md`](python/data/saber_spec.md)。生产中把 Saber 换成你公司的内部框架即可。

## 关键超参（03_train.sh）

| 参数 | 默认 | 说明 |
|---|---|---|
| `NUM_LAYERS` | 8 | 在最后 N 层加 LoRA |
| `BATCH_SIZE` | 2 | MPS 内存吃紧用小批量 |
| `ITERS` | 400 | 73 train × 400/(73/2) ≈ 11 epoch |
| `LEARNING_RATE` | 1e-4 | 太大跑飞，太小学不动 |

判断是否训成功：04 输出里 LoRA 的 `full_compliant` ≥ 60%。低了通常是数据太少（< 50 条）或 iters 不够。

## 几个注意事项

- 模板生成的训练集泛化能力弱，生产请用真实数据
- LoRA 会让模型在窄分布上偏移，写其他框架可能变差；可在训练集里混 10-20% 通用样本对冲
- 4-bit 量化基模型上的 LoRA 是工程妥协，收敛慢于 fp16
- 微调资产不是模型，是**数据集和评估管道**——模型迭代后用同样的数据重训即可

## 相关 demo

- `08-evaluation-demo`：用回归测试框架持续监控微调模型是否退化
- `13-prompt-engineering-demo`：微调前先验证 prompt 解不开问题
- `07-caching-demo`：长 system prompt 用前缀缓存，是微调的便宜替代

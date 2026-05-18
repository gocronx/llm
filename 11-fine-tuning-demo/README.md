# 11 · LoRA Fine-Tuning Demo

让通用模型学会用你公司的"内部框架"。本 demo 用虚构的 Saber 框架做例子，端到端跑 LoRA 流水线（Apple Silicon + MLX）。

## 何时考虑 fine-tune

- ✅ 通用模型不认识你的内部 API（公司内部框架、私有 SDK）
- ✅ 一致风格的输出（公司文风、特定模板）
- ✅ 小模型 + 微调 vs 大模型 + prompt-engineering，前者更便宜更快
- ❌ 知识更新（用 RAG，不要 fine-tune）
- ❌ 简单几条规则能搞定（用 prompt + few-shot）

## 流水线

```
generate (合成 60+ 样本，分层切 train/valid/test)
   ↓
train (mlx-lm.lora，~5-30 分钟手动跑)
   ↓
compare (base vs LoRA 跑 test 集，按 5 个 Saber 信号打分)
```

## 跑起来

```bash
cd python
pip install -r requirements.txt
python test.py        # 8/8 passed，不需要 mlx
python main.py generate
python main.py train  # 复制打印出来的命令到 shell 跑
python main.py compare
```

## 期待差距

base 模型平均 2.8/5（不知道 Saber），LoRA 后平均 4.9/5（学会了）。差距 ≥1.5 分。

## 共通的坑

- ❌ 训练/推理 SYSTEM_PROMPT 不一致
- ❌ 不分层切分，某种 kind 全在 train
- ❌ 用 BLEU/Rouge 评代码（变量名不同就 0 分）
- ❌ num-layers 拉满 → 过拟合

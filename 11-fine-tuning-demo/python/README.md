# 11 · LoRA Fine-Tuning — 让模型学会用"内部框架"

**真实案例：你公司有一个内部 Web 框架（这里叫 Saber），通用模型不知道它的 API。LoRA 用几百个样本就能让模型学会，比 prompt-engineering 一遍遍写"请用 Saber"靠谱得多。**

## 本目录文件

| 文件 | 角色 | 干啥 |
|---|---|---|
| `dataset.py` | 🟢 套出去用 | `build_samples` + `stratified_split` + `to_chat` |
| `checks.py` | 🟢 套出去用 | 5 个 Saber-特定信号 + syntax_ok + summarize |
| `compare.py` | 🟢 套出去用（要 mlx-lm） | 跑 base vs LoRA 对照评测 |
| `main.py` | demo only | `generate / train / compare` 三个子命令 |
| `test.py` | demo only | 纯逻辑测试，不依赖 mlx-lm |

## 工作流

```bash
cd python
pip install -r requirements.txt   # mlx + mlx-lm

# 1. 生成数据集（60+ 样本，分层切 train/valid/test）
python main.py generate

# 2. 打印 LoRA 训练命令（你手动跑，5-30 分钟）
python main.py train
# 复制打印出来的命令到 shell 跑

# 3. 跑 base vs LoRA 对照评测
python main.py compare
```

## 关键设计点

| 决策 | 原因 |
|---|---|
| 合成数据 + 分层切分 | 每种 CRUD（get_one/list/create/delete/count）train/valid/test 都有，避免"全是 list 在 train，create 在 test 没学到" |
| SYSTEM_PROMPT 训练/推理一致 | mlx-lm chat template 会把 system 当前缀，训练用 A 推理用 B 等于换了任务 |
| `Check` 而不是 BLEU/Rouge | "import_saber/handler_decorator/q_from/tuple_return/no_wrong_framework" 是可解释的"学到了没"信号 |
| `main.py train` 不直接跑训练 | mlx-lm.lora 长跑命令，让用户看着跑更稳 |
| LoRA num-layers=8 / batch=2 / iters=400 / lr=1e-4 | 这套参数在 Qwen2.5-Coder-3B 上经验值；改 model 要重新调 |

## 期待结果

```
base: 2/12 满分  avg=2.83/5
  import_saber           4/12
  handler_decorator      2/12   <- 通用模型不知道这个 decorator
  q_from                 1/12
  tuple_return           3/12
  no_wrong_framework     12/12

lora: 11/12 满分  avg=4.92/5
  import_saber           12/12  ← LoRA 学会了
  handler_decorator      12/12
  q_from                 12/12
  tuple_return           11/12
  no_wrong_framework     12/12
```

具体数字会因模型/seed 不同有 ±10% 浮动，但 **LoRA 平均分应该比 base 高 ≥1.5**。

## 常见坑

- ❌ **训练数据和推理 prompt 格式不一致** —— LoRA 学了一个分布，推理拿另一个分布问，等于没训
- ❌ **不分层切分** —— 某种 kind 全在 train、不在 test，看不出学没学到
- ❌ **用 BLEU/Rouge 评代码** —— 代码可以变量名不同但语义相同；用规则检查可解释得多
- ❌ **`num-layers` 拉满** —— 全层 LoRA 参数多 + 容易过拟合；8 层够 small dataset
- ⚠️ **本地 GPU/MLX 显存不够** —— `batch-size=1` 还跑不动就换更小模型（1B/3B）

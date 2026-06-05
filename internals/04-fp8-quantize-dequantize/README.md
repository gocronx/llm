# 04 · FP8 + Q8 量化反量化

LLM-70B 用 fp16 是 140 GB, 一张 H100-80G 装不下. 把权重 / KV cache / activation 压成 8-bit, 显存和带宽都翻倍, 还能用 H100 的 Tensor Core FP8 算力 (~2× fp16).

<p align="center"><img src="assets/fp8-illustrations/02-overview-card.png" width="420" alt="压缩最怕异常值（知识卡）"></p>

抽自 ds4.c:
- `dsv4_e4m3fn_value_cpu` / `dsv4_e4m3fn_dequant_cpu` (line 1590, 1608) — FP8 E4M3FN
- `dsv4_fp8_kv_quantize_row_inplace_cpu` (line 1640) — per-64 block FP8
- `ds4_quantize_row_q8_K` (line 1660) — Q8 per-block (对照)

## 两条路线

### FP8 E4M3FN (硬件浮点 8-bit)

```
[sign 1bit][exp 4bit][mantissa 3bit]   (no NaN, no Inf, 称 "FN" = Finite)
```

| 字段 | bits | 作用 |
|------|------|------|
| sign | 1 | 正负 |
| exp  | 4 | 数量级 (bias=7, 范围 2^-6 ~ 2^8) |
| mant | 3 | 精度 (1.xxx 的 3 位) |

可表示值: 254 个 (从 0 到 ±448). H100/B200 原生硬件支持, 2024+ LLM 推理标配.

### Q8 per-block (整数 + 共享 scale)

每 32 (或 64) 个 fp32 共享一个 fp32 scale:

```
block = [x0, x1, ..., x31]                     scale = amax / 127
codes = [round(xi/scale)]   ∈ int8
```

存储: 32 byte (codes) + 4 byte (scale) = 1.125 byte/value. 算术全是整数乘加, 没 FP8 硬件的卡上比 FP8 软件实现快.

## 对比

| | FP8 E4M3FN | Q8 per-block |
|--|-----------|---------------|
| 单值开销 | 1.0 byte | 1.125 byte (block=32) |
| 表示精度 | 大数值差 (mant 3 bit), 小数值好 (subnormal) | 跟 block 内分布均匀 |
| Outlier 抗性 | **强** (exp 自适应) | **弱** (1 个 outlier 让 scale 拉爆, small 砸到 0) |
| 算术成本 | 浮点 (需硬件支持) | 整数 (universal) |
| 现状 | H100/B200 原生; LLM 推理 (vLLM/TensorRT-LLM) | GGUF 老牌 (llama.cpp), CPU 推理友好 |

实测 (本 demo 随机 N(0, 10²)):

| 量化 | P50 相对误差 | P95 相对误差 |
|------|------------|------------|
| FP8 (block=64) | ~3% | ~14% |
| Q8 (block=32) | ~0.4% | ~1.7% |

Q8 平均更准, 但 FP8 在 outlier 场景下不崩 —— 见下:

```
63 个 small (σ=0.1) + 1 个 outlier=100:
   原 outlier 100.0:   FP8 还原 96.0       Q8 还原 99.21
   原 small  -0.0589:  FP8 还原 -0.0586    Q8 还原 -0.0000  ← Q8 砸 0 了!
```

Q8 的 scale 被 outlier 拉到 100/127 ≈ 0.79, small values 都映射到 |code|=0. FP8 用 exp 自适应每个值的数量级, 不会出这种事.

## 关键工程细节

### 1. FP8 E4M3FN 表的非线性

```
i=0:   value=0.000000   gap=0.001953
i=8:   value=0.015625   gap=0.001953    ← subnormal/normal 边界
i=16:  value=0.031250   gap=0.003906    ← gap 翻倍
i=64:  value=2.000000   gap=0.250000    ← exp 增大 gap 指数级长
i=120: value=320.000    gap=32.000
```

越大的值, **gap 越大** (mantissa 只 3 bit, 表 1.xxx). 这意味着:
- 量化 1.05 / 1.1 / 1.15 / 1.2 都不准 (mantissa 步长 0.125)
- 量化 100 → 跳到 96 或 112 (最近的 representable)

### 2. Power-of-2 Scale

```python
scale = 2 ** ceil(log2(amax / 448))
```

为什么用 power-of-2: 硬件做 `x / scale` 时, 如果 scale 是 2^k, 就是简单的指数位减法 (1 个 cycle), 不需要除法器. ds4.c 在 GPU shader 里这么写, 比浮点除法快 ×4.

### 3. Round-to-nearest-even

二分搜索找最近 representable 时, 距离相等的情况下选**偶数索引** (IEEE 754 标准). 长期统计误差期望 = 0, 否则偶数路径累积 bias.

ds4.c 的实现:
```c
if (next_diff < best_diff
    || (next_diff == best_diff && ((best + 1) & 1) == 0 && (best & 1) != 0)) {
    best++;
}
```

### 4. Per-block 而不是 per-tensor

为什么不全 tensor 一个 scale? **因为 LLM 的 activation 有很强的 outlier 偏态** —— 个别 channel 数值是均值的 100×. 全 tensor 一个 scale 会让 99% 的 small 值砸 0. Per-block 把 outlier 限制在它自己的 block 里, 不影响别的.

## 目录

```
.
├── python/
│   ├── quant.py        # 🟢 fp8_e4m3_value/quantize + q8_quantize_block + roundtrip
│   ├── main.py         # FP8 表非线性 + 误差直方图 + outlier 对比 + 存储开销
│   ├── test.py         # 9 个测试: 表正确 / clamping / idempotent / 精度 / outlier
│   └── requirements.txt
└── README.md
```

## 跑起来

```bash
cd python && pip install -r requirements.txt
python test.py    # 9/9 passed
python main.py    # 看 FP8 表非线性 + 误差分布
```

## 常见坑

- ❌ **FP8 表的 i=127 拿来用** → ds4 / IEEE 都把 i=127 留给特殊 (NaN/Inf 或预留), 越界
- ❌ **block_size 跨 SIMD 边界** → block=32 vs 64 vs 128 对 GPU kernel 性能影响巨大, 跟 warp/wave 大小对齐
- ❌ **amax=0 不处理** → scale=0 时除法 = inf, 必须有下限 (ds4.c 用 1e-4)
- ❌ **scale 用 fp16 存** → fp16 表示不下大 scale (e.g. amax=1000 时 scale 也 1000, fp16 OK; 但 amax=1e5 时 fp16 溢出). 用 fp32 存
- ❌ **量化 + 反量化 + 量化 (cascade)** → 累积误差快速放大, 一次 round-trip 后别再量化
- ⚠️ **混合精度训练用 FP8 weight + FP16 grad** → 反向需要 fp16 精度, 别全压成 FP8
- ⚠️ **outlier-aware 量化 (e.g. AWQ / SmoothQuant)** → 教学版没实现, 生产中比朴素 per-block 准很多, 大模型必备

## 跟 ds4.c 原版的对照

| ds4.c | 这里 (numpy) |
|-------|-------------|
| `dsv4_e4m3fn_value_cpu(i)` | `fp8_e4m3_value(i)` 1:1 |
| 二分搜索 lo/hi/mid 找最近 | `np.searchsorted` (二分的库函数) |
| `ldexpf(1.0f, ceilf(log2f(amax/448)))` | `2 ** np.ceil(np.log2(amax/448))` |
| inplace 写回 `x[off + i]` | 返回新数组 (教学版优先可读) |
| Q8_K `bsums` (16 个 partial sum) | 教学版省略 (对 dot product 有用, 量化本身不用) |
| `int8_t qs[]` 紧凑存 | `np.int8` array |

算法等价, 数值结果匹配 (subject to round-to-even tie 实现细节).

![小黑把流动的水倒进只有几格的冰格冻成方块, 用时再化回水但边角阶梯状有损, 旁边一个超大冰块撑爆了格子](assets/fp8-illustrations/01-quantize.png)

#!/usr/bin/env bash
# LoRA fine-tuning via mlx-lm. Requires: pip install mlx-lm
set -euo pipefail

BASE_MODEL="${BASE_MODEL:-mlx-community/Qwen2.5-Coder-3B-Instruct-4bit}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$HERE/data"
ADAPTER_DIR="$HERE/adapters"

NUM_LAYERS=8
BATCH_SIZE=2
ITERS=400
LEARNING_RATE=1e-4

mkdir -p "$ADAPTER_DIR"

python -m mlx_lm.lora \
    --model "$BASE_MODEL" \
    --train \
    --data "$DATA_DIR" \
    --adapter-path "$ADAPTER_DIR" \
    --num-layers "$NUM_LAYERS" \
    --batch-size "$BATCH_SIZE" \
    --iters "$ITERS" \
    --learning-rate "$LEARNING_RATE" \
    --steps-per-report 20 \
    --steps-per-eval 80 \
    --save-every 100

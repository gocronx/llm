"""Model registry. Prices match Anthropic Haiku 3.5 / Sonnet 4 / Opus 4 (1 : 4 : 19 input ratio)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Model:
    tier: str
    id: str
    input_per_1k: float
    output_per_1k: float
    quality: int
    context_window: int


REGISTRY: list[Model] = [
    Model(
        tier="cheap",
        id=os.getenv("MODEL_CHEAP", "GLM-4.7-Flash-4bit"),
        input_per_1k=0.0008,        # Anthropic Haiku 3.5: $0.80 / 1M
        output_per_1k=0.004,         # $4.00 / 1M
        quality=5,
        context_window=200_000,
    ),
    Model(
        tier="mid",
        id=os.getenv("MODEL_MID", "Qwen3.5-27B-Claude-4.6-Opus-Distilled-MLX-4bit"),
        input_per_1k=0.003,          # Anthropic Sonnet 4: $3 / 1M
        output_per_1k=0.015,          # $15 / 1M
        quality=7,
        context_window=200_000,
    ),
    Model(
        tier="premium",
        id=os.getenv("MODEL_PREMIUM", "Qwen3.6-40B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking-8bit"),
        input_per_1k=0.015,           # Anthropic Opus 4: $15 / 1M
        output_per_1k=0.075,           # $75 / 1M
        quality=9,
        context_window=200_000,
    ),
]

BY_TIER: dict[str, Model] = {m.tier: m for m in REGISTRY}


def estimate_tokens(text: str) -> int:
    # Rough Chinese-heavy estimate: 2 chars/token.
    return max(1, len(text) // 2)


def estimate_cost(model: Model, prompt: str, completion: str) -> float:
    return (
        estimate_tokens(prompt) / 1000 * model.input_per_1k
        + estimate_tokens(completion) / 1000 * model.output_per_1k
    )

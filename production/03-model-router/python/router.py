"""Five routing strategies for picking which model handles a request.

Two distinct concepts compose here:
  - failover  : tier IS DOWN (5xx/429/network)         → try next tier
  - cascade   : tier's ANSWER is WEAK (heuristic)      → escalate to premium

Every strategy benefits from failover; only `cascade` deliberately escalates on weak output.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from dotenv import load_dotenv

from models import BY_TIER, Model, estimate_cost

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")

TIERS_IN_ORDER = ["cheap", "mid", "premium"]


class AllTiersFailed(RuntimeError):
    """Raised when failover exhausts every tier downstream of the starting one."""


@dataclass
class RouteResult:
    answer: str
    chosen: Model
    elapsed_ms: int
    cost: float
    rationale: str
    escalated_from: Model | None = None
    failed_over_from: list[Model] = field(default_factory=list)


def _post_raw(model: Model, prompt: str, max_tokens: int = 500,
              system: str | None = None) -> tuple[str, int]:
    """One HTTP call. Raises requests.HTTPError on 4xx, Timeout/ConnectionError on network."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    started = time.time()
    resp = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": model.id,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    return text, int((time.time() - started) * 1000)


def _is_failover_worthy(exc: Exception) -> bool:
    """5xx, 429, network failures — switching tier might help.
    4xx (bad request, auth, model not found) — switching tier won't help, propagate."""
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def _post_with_failover(
    starting_tier: str,
    prompt: str,
    max_tokens: int = 500,
    system: str | None = None,
) -> tuple[str, int, Model, list[Model]]:
    """Try `starting_tier` first, fall over to each subsequent tier on transient failure.

    Returns (answer, elapsed_ms_of_successful_call, model_used, models_that_failed).
    Failed calls don't add to elapsed_ms — callers shouldn't bill latency for errors.
    """
    start = TIERS_IN_ORDER.index(starting_tier)
    failed: list[Model] = []
    last_exc: Exception | None = None

    for tier in TIERS_IN_ORDER[start:]:
        model = BY_TIER[tier]
        try:
            answer, ms = _post_raw(model, prompt, max_tokens, system)
            return answer, ms, model, failed
        except Exception as e:
            if not _is_failover_worthy(e):
                raise
            failed.append(model)
            last_exc = e

    raise AllTiersFailed(
        f"all tiers from {starting_tier} downstream failed; last error: {last_exc}"
    )


def _build_result(
    answer: str,
    chosen: Model,
    elapsed_ms: int,
    prompt: str,
    rationale: str,
    extra_cost: float = 0.0,
    escalated_from: Model | None = None,
    failed_over_from: list[Model] | None = None,
) -> RouteResult:
    return RouteResult(
        answer=answer,
        chosen=chosen,
        elapsed_ms=elapsed_ms,
        cost=estimate_cost(chosen, prompt, answer) + extra_cost,
        rationale=rationale,
        escalated_from=escalated_from,
        failed_over_from=failed_over_from or [],
    )


def route_always(tier: str, prompt: str) -> RouteResult:
    answer, ms, chosen, failed = _post_with_failover(tier, prompt)
    return _build_result(answer, chosen, ms, prompt,
                         rationale=f"always-{tier}", failed_over_from=failed)


_HARD = re.compile(
    r"\b(design|architecture|distributed|optimize|prove|analyze|complex|"
    r"explain in detail|step by step|reasoning|算法|架构|证明|推导|深入|详细分析)\b",
    re.IGNORECASE,
)
_EASY = re.compile(
    r"\b(translate|hello|你好|hi|thanks|谢谢|what time|what date|"
    r"翻译|今天几号|多少|等于)\b",
    re.IGNORECASE,
)


def route_rules(prompt: str) -> RouteResult:
    tok_estimate = len(prompt) // 2
    if _HARD.search(prompt) or tok_estimate > 1500:
        tier, why = "premium", "hard keyword or long prompt"
    elif _EASY.search(prompt) or tok_estimate < 30:
        tier, why = "cheap", "easy keyword or short prompt"
    else:
        tier, why = "mid", "default"

    answer, ms, chosen, failed = _post_with_failover(tier, prompt)
    return _build_result(answer, chosen, ms, prompt,
                         rationale=f"rules → {tier} ({why})", failed_over_from=failed)


_CLASSIFIER_SYS = (
    "You are a query difficulty classifier. Output exactly one word: easy, medium, or hard.\n"
    "- easy: trivia, greetings, simple translation, basic math, definitions\n"
    "- medium: short coding, summarization, structured Q&A\n"
    "- hard: complex reasoning, system design, multi-step analysis"
)
_LABEL_TO_TIER = {"easy": "cheap", "medium": "mid", "hard": "premium"}


def _classify(prompt: str) -> tuple[str, float]:
    """Returns (label, cost_of_classifier_call)."""
    classifier = BY_TIER["cheap"]
    text, _ = _post_raw(classifier, prompt[:500], max_tokens=10, system=_CLASSIFIER_SYS)
    label = next((lab for lab in ("easy", "medium", "hard") if lab in text.lower()), "medium")
    return label, estimate_cost(classifier, prompt[:500], label)


def route_classifier(prompt: str) -> RouteResult:
    label, classifier_cost = _classify(prompt)
    starting_tier = _LABEL_TO_TIER[label]
    answer, ms, chosen, failed = _post_with_failover(starting_tier, prompt)
    return _build_result(
        answer, chosen, ms, prompt,
        rationale=f"classifier → {label} → {chosen.tier}",
        extra_cost=classifier_cost,
        failed_over_from=failed,
    )


_WEAK_TEXT = re.compile(
    r"(i don't know|i'm not sure|cannot answer|not enough information|"
    r"unable to|无法回答|不知道|没把握|信息不足)",
    re.IGNORECASE,
)


def _looks_weak(answer: str, prompt: str) -> bool:
    """Cheap-and-conservative weakness heuristic. Errs toward accepting answers
    so that legitimately short replies (e.g. '2') don't trigger escalation."""
    if _WEAK_TEXT.search(answer):
        return True
    if len(answer.strip()) < 5:
        return True
    if len(prompt) > 200 and len(answer) < len(prompt) / 4:
        return True
    return False


def route_cascade(prompt: str) -> RouteResult:
    """Try cheap (with failover up), and if the answer looks weak, escalate to premium
    (also with failover). The 'cheap call is sunk cost' on escalation."""
    answer, ms, chosen, failed_first = _post_with_failover("cheap", prompt)
    first_cost = estimate_cost(chosen, prompt, answer)

    if not _looks_weak(answer, prompt):
        return RouteResult(
            answer=answer, chosen=chosen, elapsed_ms=ms,
            cost=first_cost, rationale="cascade → cheap (kept)",
            failed_over_from=failed_first,
        )

    cheap_first = chosen
    answer2, ms2, chosen2, failed_second = _post_with_failover("premium", prompt)
    return RouteResult(
        answer=answer2, chosen=chosen2, elapsed_ms=ms + ms2,
        cost=first_cost + estimate_cost(chosen2, prompt, answer2),
        rationale="cascade → cheap weak → premium",
        escalated_from=cheap_first,
        failed_over_from=failed_first + failed_second,
    )

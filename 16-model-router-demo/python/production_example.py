"""Offline cost simulation comparing routing strategies on a synthetic workload."""

import random
from dataclasses import dataclass

from colorama import Fore, Style, init

from models import BY_TIER, estimate_cost

init(autoreset=True)
random.seed(42)


WORKLOAD = [
    ("easy",   70, 40,  60),
    ("medium", 25, 300, 800),
    ("hard",   5,  800, 2500),
]
LABEL_TO_TIER = {"easy": "cheap", "medium": "mid", "hard": "premium"}
CASCADE_KEEP_RATE = {"easy": 0.95, "medium": 0.40, "hard": 0.10}
CLASSIFIER_OVERHEAD = 0.00005


@dataclass(frozen=True)
class FakeRequest:
    label: str
    prompt_chars: int
    answer_chars: int

    @property
    def prompt(self) -> str:
        return "x" * self.prompt_chars

    @property
    def answer(self) -> str:
        return "y" * self.answer_chars


def build_workload() -> list[FakeRequest]:
    reqs: list[FakeRequest] = []
    for label, n, pc, ac in WORKLOAD:
        for _ in range(n):
            reqs.append(FakeRequest(
                label=label,
                prompt_chars=max(1, int(random.gauss(pc, pc * 0.3))),
                answer_chars=max(1, int(random.gauss(ac, ac * 0.4))),
            ))
    random.shuffle(reqs)
    return reqs


def cost_always(tier: str, reqs: list[FakeRequest]) -> float:
    m = BY_TIER[tier]
    return sum(estimate_cost(m, r.prompt, r.answer) for r in reqs)


def cost_oracle(reqs: list[FakeRequest]) -> float:
    return sum(estimate_cost(BY_TIER[LABEL_TO_TIER[r.label]], r.prompt, r.answer) for r in reqs)


def cost_rules(reqs: list[FakeRequest]) -> float:
    total = 0.0
    for r in reqs:
        if r.prompt_chars > 600:
            tier = "premium"
        elif r.prompt_chars > 100:
            tier = "mid"
        else:
            tier = "cheap"
        total += estimate_cost(BY_TIER[tier], r.prompt, r.answer)
    return total


def cost_classifier(reqs: list[FakeRequest], err_rate: float) -> float:
    tiers = list(LABEL_TO_TIER.values())
    total = 0.0
    for r in reqs:
        correct = LABEL_TO_TIER[r.label]
        if random.random() < err_rate:
            tier = random.choice([t for t in tiers if t != correct])
        else:
            tier = correct
        total += estimate_cost(BY_TIER[tier], r.prompt, r.answer) + CLASSIFIER_OVERHEAD
    return total


def cost_cascade(reqs: list[FakeRequest]) -> float:
    cheap, premium = BY_TIER["cheap"], BY_TIER["premium"]
    total = 0.0
    for r in reqs:
        total += estimate_cost(cheap, r.prompt, r.answer)
        if random.random() > CASCADE_KEEP_RATE[r.label]:
            total += estimate_cost(premium, r.prompt, r.answer)
    return total


def main() -> None:
    reqs = build_workload()
    print(f"Workload: {len(reqs)} requests")
    for label, n, pc, ac in WORKLOAD:
        print(f"  {label:<7} count={n}  ~{pc} chars in, ~{ac} chars out")

    oracle = cost_oracle(reqs)
    premium_baseline = cost_always("premium", reqs)

    rows = [
        ("oracle (theoretical min)", oracle),
        ("always-cheap",             cost_always("cheap", reqs)),
        ("always-mid",               cost_always("mid", reqs)),
        ("always-premium",           premium_baseline),
        ("rules (token buckets)",    cost_rules(reqs)),
        ("classifier (15% err)",     cost_classifier(reqs, err_rate=0.15)),
        ("classifier (5% err)",      cost_classifier(reqs, err_rate=0.05)),
        ("cascade",                  cost_cascade(reqs)),
    ]

    print(f"\n{Fore.CYAN}Strategy comparison (lower = better){Style.RESET_ALL}")
    print(f"  {'strategy':<22}  {'total':>10}  {'vs oracle':>10}  {'vs premium':>10}")
    print(f"  {'-' * 22}  {'-' * 10}  {'-' * 10}  {'-' * 10}")
    for name, c in rows:
        savings_oracle = (c / oracle - 1) * 100
        savings_premium = (1 - c / premium_baseline) * 100
        color = Fore.GREEN if savings_premium > 50 else (Fore.YELLOW if savings_premium > 0 else Fore.RED)
        print(f"  {name:<22}  ${c:>9.4f}  {savings_oracle:>+8.1f}%  {color}{savings_premium:>+8.1f}%{Style.RESET_ALL}")

    print(f"\n{Fore.YELLOW}Notes:{Style.RESET_ALL}")
    print("  - always-cheap is the cost floor but ignores quality.")
    print("  - oracle assumes perfect knowledge of difficulty; never reachable.")
    print("  - cascade pays the cheap call even when it has to escalate.")


if __name__ == "__main__":
    main()

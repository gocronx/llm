"""
精确匹配缓存：最简单、最稳的缓存策略

原理：
  prompt → SHA256 哈希 → 字典 key
  下次同样的 prompt 直接返回缓存的回答，零 API 调用

适用场景：
  - FAQ / 客服话术（同一个问题反复被问）
  - 翻译固定文案、模板化任务
  - 测试 / 开发时反复调试同一个 prompt

不适用场景：
  - 用户输入千变万化（命中率会很低）
  - 时效性内容（昨天的"今日天气"答案不能复用）
  - 需要随机性的任务（写诗、创意生成）
"""

import os
import json
import time
import hashlib
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    expired: int = 0
    total_latency_saved_ms: int = 0
    total_tokens_saved: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


@dataclass
class CacheEntry:
    response: str
    tokens: int
    latency_ms: int
    created_at: float
    hit_count: int = 0


class ExactCache:
    """精确匹配缓存

    关键设计：
      - 用 SHA256 而不是 hash()：跨进程稳定、长度统一
      - 缓存 key 包含 model + temperature：不同模型/温度的回答不混
      - 支持 TTL：避免陈旧数据
      - 支持磁盘持久化：进程重启不丢
    """

    def __init__(
        self,
        ttl_seconds: Optional[int] = None,
        persist_path: Optional[Path] = None,
    ):
        self._store: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._ttl = ttl_seconds
        self._persist_path = persist_path
        if persist_path and persist_path.exists():
            self._load()

    def _make_key(self, prompt: str, model: str, temperature: float) -> str:
        # 把所有影响输出的参数一起进哈希
        payload = json.dumps(
            {"p": prompt, "m": model, "t": temperature},
            ensure_ascii=False, sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _is_expired(self, entry: CacheEntry) -> bool:
        if self._ttl is None:
            return False
        return time.time() - entry.created_at > self._ttl

    def get(self, prompt: str, model: str, temperature: float) -> Optional[str]:
        key = self._make_key(prompt, model, temperature)
        entry = self._store.get(key)
        if entry is None:
            self._stats.misses += 1
            return None
        if self._is_expired(entry):
            self._stats.expired += 1
            self._stats.misses += 1
            del self._store[key]
            return None
        self._stats.hits += 1
        self._stats.total_latency_saved_ms += entry.latency_ms
        self._stats.total_tokens_saved += entry.tokens
        entry.hit_count += 1
        return entry.response

    def put(
        self, prompt: str, model: str, temperature: float,
        response: str, tokens: int, latency_ms: int,
    ):
        key = self._make_key(prompt, model, temperature)
        self._store[key] = CacheEntry(
            response=response, tokens=tokens,
            latency_ms=latency_ms, created_at=time.time(),
        )
        if self._persist_path:
            self._save()

    @property
    def stats(self) -> CacheStats:
        return self._stats

    def _save(self):
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with self._persist_path.open("w", encoding="utf-8") as f:
            json.dump(
                {k: asdict(v) for k, v in self._store.items()},
                f, ensure_ascii=False,
            )

    def _load(self):
        with self._persist_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        self._store = {k: CacheEntry(**v) for k, v in raw.items()}


def call_llm(prompt: str, temperature: float = 0.0) -> tuple[str, int, int]:
    """调用 LLM，返回 (回答, tokens, 延迟ms)"""
    started = time.time()
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 200,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    latency_ms = int((time.time() - started) * 1000)
    tokens = data.get("usage", {}).get("total_tokens", 0)
    text = data["choices"][0]["message"]["content"].strip()
    return text, tokens, latency_ms


def call_with_cache(
    prompt: str, cache: ExactCache, temperature: float = 0.0
) -> tuple[str, bool, int]:
    """带缓存的调用，返回 (回答, 是否命中缓存, 延迟ms)"""
    cached = cache.get(prompt, MODEL_ID, temperature)
    if cached is not None:
        return cached, True, 1  # 命中：~1ms
    text, tokens, latency_ms = call_llm(prompt, temperature)
    cache.put(prompt, MODEL_ID, temperature, text, tokens, latency_ms)
    return text, False, latency_ms


# ---------- Demo ----------

def demo_basic():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 1：基础精确缓存（同一 prompt 两次调用）")
    print(f"{'='*60}{Style.RESET_ALL}")

    cache = ExactCache()
    prompt = "用一句话解释什么是闭包。"

    print(f"\n第一次调用（应未命中，调真实 API）...")
    answer1, hit1, ms1 = call_with_cache(prompt, cache)
    mark = f"{Fore.YELLOW}MISS" if not hit1 else f"{Fore.GREEN}HIT"
    print(f"  {mark}{Style.RESET_ALL}  耗时 {ms1}ms")
    print(f"  回答: {answer1[:80]}...")

    print(f"\n第二次调用（同样的 prompt，应命中缓存）...")
    answer2, hit2, ms2 = call_with_cache(prompt, cache)
    mark = f"{Fore.GREEN}HIT" if hit2 else f"{Fore.RED}MISS"
    print(f"  {mark}{Style.RESET_ALL}  耗时 {ms2}ms")
    print(f"  内容一致: {answer1 == answer2}")

    speedup = ms1 / max(ms2, 1)
    print(f"\n  {Fore.YELLOW}加速比：{speedup:.0f}x{Style.RESET_ALL}（{ms1}ms → {ms2}ms）")


def demo_key_isolation():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 2：缓存键隔离（不同 temperature 不能共享缓存）")
    print(f"{'='*60}{Style.RESET_ALL}")

    cache = ExactCache()
    prompt = "今天心情怎么样？"

    print(f"\n第一次：temperature=0.0")
    _, hit1, _ = call_with_cache(prompt, cache, temperature=0.0)
    print(f"  {'命中' if hit1 else '未命中'}  ←  首次必然未命中")

    print(f"\n第二次：temperature=0.7（同样的 prompt 但温度不同）")
    _, hit2, _ = call_with_cache(prompt, cache, temperature=0.7)
    print(f"  {'命中' if hit2 else '未命中'}  ←  ", end="")
    if hit2:
        print(f"{Fore.RED}❌ 缓存设计有 bug，不同温度不该共享{Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}✓ 正确隔离{Style.RESET_ALL}")

    print(f"\n第三次：回到 temperature=0.0")
    _, hit3, _ = call_with_cache(prompt, cache, temperature=0.0)
    print(f"  {'命中' if hit3 else '未命中'}  ←  ", end="")
    if hit3:
        print(f"{Fore.GREEN}✓ 命中第一次的缓存{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ 应该命中{Style.RESET_ALL}")


def demo_ttl():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 3：TTL 过期（避免陈旧数据）")
    print(f"{'='*60}{Style.RESET_ALL}")

    cache = ExactCache(ttl_seconds=2)  # 演示用 2 秒
    prompt = "1 + 1 = ?"

    print(f"\n写入缓存...")
    call_with_cache(prompt, cache)

    print(f"立即查询（应命中）...")
    _, hit1, _ = call_with_cache(prompt, cache)
    print(f"  {Fore.GREEN if hit1 else Fore.RED}{'HIT' if hit1 else 'MISS'}{Style.RESET_ALL}")

    print(f"\n等 3 秒（超过 TTL）...")
    time.sleep(3)

    print(f"再查询（应过期）...")
    _, hit2, _ = call_with_cache(prompt, cache)
    print(f"  {Fore.YELLOW if not hit2 else Fore.RED}{'MISS（过期重算）' if not hit2 else 'HIT（不应该）'}{Style.RESET_ALL}")
    print(f"\n  统计：{cache.stats.expired} 个过期条目")


def demo_workload():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 4：模拟真实负载（FAQ 场景，70% 重复）")
    print(f"{'='*60}{Style.RESET_ALL}")

    cache = ExactCache()
    faq = [
        "怎么修改密码？",
        "如何申请退款？",
        "订单多久能发货？",
    ]
    # 模拟 10 次访问，70% 落在 3 个 FAQ 上
    workload = (faq * 3) + ["新问题1", "新问题2", "新问题3"][:1]

    total_no_cache_ms = 0
    total_with_cache_ms = 0

    for i, q in enumerate(workload, 1):
        _, hit, ms = call_with_cache(q, cache)
        # "如果没有缓存"的成本 = 命中时也得真实调用一次
        if hit:
            no_cache_ms = sum(
                e.latency_ms for e in cache._store.values()
            ) // max(len(cache._store), 1)  # 用平均延迟近似
        else:
            no_cache_ms = ms
        total_with_cache_ms += ms
        total_no_cache_ms += no_cache_ms
        mark = f"{Fore.GREEN}HIT" if hit else f"{Fore.YELLOW}MISS"
        print(f"  [{i:2d}] {mark}{Style.RESET_ALL}  {ms:>6d}ms  {q}")

    s = cache.stats
    print(f"\n  {Fore.CYAN}统计：{Style.RESET_ALL}")
    print(f"    命中率: {s.hit_rate*100:.0f}%  ({s.hits} hits / {s.misses} misses)")
    print(f"    带缓存总耗时: {total_with_cache_ms}ms")
    print(f"    无缓存总耗时（估算）: {total_no_cache_ms}ms")
    print(f"    {Fore.GREEN}省了 {total_no_cache_ms - total_with_cache_ms}ms "
          f"({(1 - total_with_cache_ms/max(total_no_cache_ms,1))*100:.0f}%){Style.RESET_ALL}")
    print(f"    省 tokens: {s.total_tokens_saved}")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("精确匹配缓存 — 最简单、最稳的缓存策略")
    print(f"{'='*60}{Style.RESET_ALL}")
    print(f"\n核心原理：prompt + 模型 + 参数 → SHA256 → 缓存 key\n")

    demo_basic()
    demo_key_isolation()
    demo_ttl()
    demo_workload()

    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("精确缓存的优缺点")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}优点：{Style.RESET_ALL}")
    print("  ✓ 命中即正确（永不返回错答案）")
    print("  ✓ 实现简单（一个字典就够）")
    print("  ✓ 无额外开销（哈希很快）")
    print(f"\n{Fore.RED}缺点：{Style.RESET_ALL}")
    print("  ✗ 命中率低（用户输入稍有不同就 miss）")
    print("  ✗ 不能识别'语义相同'（多一个空格就 miss）")
    print(f"\n{Fore.YELLOW}下一步：看 semantic_cache.py，{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}它能识别相似 prompt，但带来新问题。{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()

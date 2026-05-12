"""
语义缓存：用相似度替代精确匹配

原理：
  新 prompt → 计算与缓存里所有 prompt 的相似度
  → 最相似的一条相似度 ≥ 阈值 → 命中
  → 否则 MISS，调真实 API

相似度算法：字符 2-gram + Jaccard
  之所以不用 embedding：
    1. 不引入额外模型依赖（sentence-transformers 是 100MB+）
    2. 透明、可调试、可解释
    3. 中文场景下 Jaccard 已经够用
  真实生产建议用 sentence-transformers 多语言模型，方法的核心思路一样。

⚠️  这是缓存里风险最高的策略：
  阈值太低 → 把不同问题的答案串错（false positive）
  阈值太高 → 命中率不如精确匹配（白费功夫）
  本文件会展示阈值如何决定"省钱 vs 答错"的权衡。
"""

import os
import time
import requests
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


# ---------- 相似度算法 ----------

def char_ngrams(text: str, n: int = 1) -> set[str]:
    """字符 n-gram。中文按字符切，英文也按字符切（小写、去空格、去标点）

    默认 n=1（字符集合）。短中文句子上 2-gram 分数过低，
    1-gram 给出更可用的相似度区间，且对'同义改写'更敏感。
    """
    cleaned = "".join(
        ch for ch in text.lower()
        if ch.isalnum() or "一" <= ch <= "鿿"
    )
    if len(cleaned) < n:
        return {cleaned}
    return {cleaned[i:i + n] for i in range(len(cleaned) - n + 1)}


def jaccard_similarity(a: str, b: str) -> float:
    """Jaccard 相似度：交集 / 并集（1-gram + 2-gram 平均，兼顾语序）"""
    sa1, sa2 = char_ngrams(a, 1), char_ngrams(a, 2)
    sb1, sb2 = char_ngrams(b, 1), char_ngrams(b, 2)

    def _jac(x: set, y: set) -> float:
        if not x or not y:
            return 0.0
        return len(x & y) / len(x | y)

    # 1-gram 体现"用了哪些字"，2-gram 体现"字的顺序"
    return (_jac(sa1, sb1) + _jac(sa2, sb2)) / 2


# ---------- 缓存实现 ----------

@dataclass
class SemanticEntry:
    prompt: str
    response: str
    tokens: int
    latency_ms: int
    hit_count: int = 0


@dataclass
class SemanticStats:
    hits: int = 0
    misses: int = 0
    total_lookup_ms: int = 0  # 相似度计算耗时
    total_latency_saved_ms: int = 0
    total_tokens_saved: int = 0
    suspected_false_positives: int = 0  # 命中但实际不该命中（仅在带 ground truth 时统计）

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class SemanticCache:
    """语义缓存：基于字符 n-gram + Jaccard 相似度

    生产建议：把 _similarity 换成 sentence-transformers 的 cosine similarity。
    """

    def __init__(self, threshold: float = 0.70):
        self._entries: list[SemanticEntry] = []
        self._stats = SemanticStats()
        self.threshold = threshold

    def get(self, prompt: str) -> Optional[tuple[str, str, float]]:
        """返回 (回答, 命中的原 prompt, 相似度) 或 None"""
        if not self._entries:
            self._stats.misses += 1
            return None

        started = time.time()
        best_score = 0.0
        best_entry = None
        for entry in self._entries:
            score = jaccard_similarity(prompt, entry.prompt)
            if score > best_score:
                best_score = score
                best_entry = entry
        self._stats.total_lookup_ms += int((time.time() - started) * 1000)

        if best_entry is not None and best_score >= self.threshold:
            self._stats.hits += 1
            self._stats.total_latency_saved_ms += best_entry.latency_ms
            self._stats.total_tokens_saved += best_entry.tokens
            best_entry.hit_count += 1
            return best_entry.response, best_entry.prompt, best_score

        self._stats.misses += 1
        return None

    def put(self, prompt: str, response: str, tokens: int, latency_ms: int):
        self._entries.append(SemanticEntry(
            prompt=prompt, response=response,
            tokens=tokens, latency_ms=latency_ms,
        ))

    @property
    def stats(self) -> SemanticStats:
        return self._stats


# ---------- LLM 调用 ----------

def call_llm(prompt: str, temperature: float = 0.0) -> tuple[str, int, int]:
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


def call_with_semantic_cache(
    prompt: str, cache: SemanticCache
) -> tuple[str, bool, Optional[tuple[str, float]], int]:
    """返回 (回答, 命中, (原prompt, 相似度), 延迟ms)"""
    hit = cache.get(prompt)
    if hit is not None:
        response, original, score = hit
        return response, True, (original, score), 1
    text, tokens, latency_ms = call_llm(prompt)
    cache.put(prompt, text, tokens, latency_ms)
    return text, False, None, latency_ms


# ---------- Demo ----------

def demo_similarity_basics():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 1：字符 2-gram + Jaccard 相似度的直觉")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    pairs = [
        ("怎么修改密码", "如何修改密码"),       # 极相似
        ("怎么修改密码", "怎么改密码"),         # 高度相似
        ("怎么修改密码", "怎么修改邮箱"),       # 中等相似（同结构不同对象）
        ("用Python排序", "用Python排序，要降序"),  # 后者多个关键约束！
        ("怎么修改密码", "怎么申请退款"),       # 不相关
        ("怎么修改密码", "今天天气怎么样"),     # 完全无关
    ]
    for a, b in pairs:
        sim = jaccard_similarity(a, b)
        if sim >= 0.85:
            color = Fore.RED  # 高相似度容易误命中
        elif sim >= 0.6:
            color = Fore.YELLOW
        else:
            color = Fore.GREEN
        print(f"  {color}{sim:.2f}{Style.RESET_ALL}  '{a}' vs '{b}'")

    print(f"\n  {Fore.YELLOW}注意第 4 对：相似度高，但语义关键约束（'要降序'）不同{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}这就是语义缓存的典型陷阱{Style.RESET_ALL}")


def demo_threshold_tradeoff():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 2：阈值 trade-off — 命中率 vs 错答率")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print("场景：用户问 5 个不同问题，但说法各异")
    print()

    # 设置阶段：先把 4 条"基准答案"放进缓存
    setup = [
        ("怎么修改密码", "id_password_change"),
        ("用Python写快排", "id_qsort_asc"),
    ]
    # 查询阶段：每条都标注真实意图，看会不会命中错的缓存条目
    queries = [
        ("如何修改密码",       "id_password_change", "应命中（同义）"),
        ("怎么改密码",         "id_password_change", "应命中（同义）"),
        ("怎么不改密码",       "id_password_keep",   "应未命中（否定词）"),
        ("Python怎么写快排",   "id_qsort_asc",       "应命中（同义）"),
        ("用Python写快排，要降序", "id_qsort_desc",  "应未命中（多约束）"),
        ("用Python写归并排序", "id_msort",           "应未命中（换算法）"),
    ]

    thresholds = [0.85, 0.70, 0.55, 0.40]
    print(f"  {'阈值':>6s}  {'命中':>4s}  {'误命中':>6s}  {'命中率':>6s}  {'错答率':>6s}")
    print(f"  {'-'*6}  {'-'*4}  {'-'*6}  {'-'*6}  {'-'*6}")

    for thr in thresholds:
        cache = SemanticCache(threshold=thr)
        # 1. setup
        setup_ids: set[str] = set()
        for q, qid in setup:
            cache.put(q, f"答案_{qid}", tokens=50, latency_ms=1000)
            setup_ids.add(qid)

        hits = 0
        false_hits = 0
        for q, true_qid, _ in queries:
            result = cache.get(q)
            if result is None:
                continue
            response, _, _ = result
            hits += 1
            cached_id = response.replace("答案_", "")
            # 真实意图不在 setup 里 → 任何命中都是误命中
            # 真实意图在 setup 里 → cached_id 必须等于 true_qid
            if true_qid not in setup_ids or cached_id != true_qid:
                false_hits += 1
        queries_made = len(queries)
        hit_rate = hits / queries_made
        false_rate = false_hits / queries_made
        # 颜色：错答率 > 0 一律红
        color = Fore.RED if false_rate > 0 else (
            Fore.GREEN if hit_rate >= 0.6 else Fore.YELLOW
        )
        print(f"  {color}{thr:>6.2f}  {hits:>4d}  {false_hits:>6d}  "
              f"{hit_rate*100:>5.0f}%  {false_rate*100:>5.0f}%{Style.RESET_ALL}")

    print(f"\n  {Fore.YELLOW}观察：阈值越低，命中率上升，但错答率也跟着上来。{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}没有'最优'阈值，只有'你能容忍多少错误'的权衡。{Style.RESET_ALL}")


def demo_real_workload():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 3：真实 LLM 调用 — 同义问题被识别")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    cache = SemanticCache(threshold=0.7)
    queries = [
        "用一句话解释什么是闭包",
        "请用一句话解释什么是闭包",      # 几乎一样
        "什么是闭包？一句话",            # 同义但顺序变
        "解释一下递归是什么",            # 不同问题
    ]

    for q in queries:
        text, hit, info, ms = call_with_semantic_cache(q, cache)
        if hit:
            original, score = info
            print(f"  {Fore.GREEN}HIT{Style.RESET_ALL} (相似度 {score:.2f}, {ms}ms)")
            print(f"    新 prompt:  {q}")
            print(f"    命中的:     {original}")
            print(f"    回答: {text[:60]}...")
        else:
            print(f"  {Fore.YELLOW}MISS{Style.RESET_ALL} ({ms}ms) — 调用真实 API")
            print(f"    prompt: {q}")
            print(f"    回答: {text[:60]}...")
        print()


def demo_dangerous_case():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("演示 4：危险案例 — 关键约束被忽略")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    cache = SemanticCache(threshold=0.7)

    print(f"先问：{Fore.CYAN}用Python写快速排序{Style.RESET_ALL}")
    text1, _, _, _ = call_with_semantic_cache("用Python写快速排序", cache)
    print(f"  缓存了答案: {text1[:60]}...\n")

    print(f"再问：{Fore.CYAN}用Python写快速排序，结果要降序{Style.RESET_ALL}")
    text2, hit, info, ms = call_with_semantic_cache(
        "用Python写快速排序，结果要降序", cache)
    sim = jaccard_similarity("用Python写快速排序", "用Python写快速排序，结果要降序")
    print(f"  相似度: {sim:.2f}  阈值: {cache.threshold}")
    if hit:
        print(f"  {Fore.RED}❌ HIT — 但用户要降序，缓存里是升序{Style.RESET_ALL}")
        print(f"  {Fore.RED}    返回了错的答案！{Style.RESET_ALL}")
    else:
        print(f"  {Fore.GREEN}✓ MISS — 阈值够严，没误命中{Style.RESET_ALL}")

    print(f"\n  {Fore.YELLOW}教训：{Style.RESET_ALL}")
    print(f"    语义缓存最大的风险就是这个：相似 ≠ 等价")
    print(f"    多一个修饰词、否定词、约束条件，意思可能完全相反")
    print(f"    防御措施：")
    print(f"      1. 阈值宁高勿低（本 demo 的 Jaccard 推荐 ≥ 0.80）")
    print(f"      2. 关键词黑名单不走语义层（'不/不要/没/否'等否定词）")
    print(f"      3. 只在创意低、答案稳定的场景使用（FAQ、模板）")
    print(f"      4. 上线前用真实 query 跑一遍，统计 false-hit 率")


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("语义缓存 — 命中率最高，风险也最高")
    print(f"{'='*60}{Style.RESET_ALL}")

    demo_similarity_basics()
    demo_threshold_tradeoff()
    demo_real_workload()
    demo_dangerous_case()

    print(f"\n\n{Fore.CYAN}{'='*60}")
    print("语义缓存的诚实评价")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}什么时候该用：{Style.RESET_ALL}")
    print("  ✓ FAQ / 客服（用户表达多样但意图集中）")
    print("  ✓ 知识问答（同一个事实问题不同问法）")
    print("  ✓ 任务模板化（'帮我写邮件' 类）")
    print()
    print(f"{Fore.RED}什么时候不该用：{Style.RESET_ALL}")
    print("  ✗ 任何带'否定/约束'的查询（误命中代价巨大）")
    print("  ✗ 代码生成（缺一个修饰词答案就错）")
    print("  ✗ 数学/计算题（相似 prompt 答案完全不同）")
    print("  ✗ 时效性内容（昨天的'最新新闻'≠今天的）")
    print()
    print(f"{Fore.YELLOW}本 demo 用的 1+2-gram Jaccard，阈值经验值：{Style.RESET_ALL}")
    print("  0.80+：保守，几乎只命中字面重复")
    print("  0.65-0.75：FAQ 场景常用平衡点")
    print("  < 0.55：除非业务能容忍 5-10% 错答，否则别用")
    print(f"  {Fore.YELLOW}（生产建议改用 sentence-transformers 嵌入 + cosine，阈值 0.85+）{Style.RESET_ALL}")
    print()


if __name__ == "__main__":
    main()

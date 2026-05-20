"""memory.py —— 四种对话记忆策略。整文件 cp 进项目即可。

每种策略实现同一个接口 `append(role, content)` + `messages()`：
    Full        —— 不动，全留着
    Window(k)   —— 只保留最近 k 轮（user+assistant 各一条算一轮）
    Tokens(N)   —— 总 token 估算超过 N 就从头扔
    Summary(k)  —— 每攒 k 轮调一次 LLM 总结，把详细历史压成一段事实

system prompt 不算进上面任何策略 —— 它在前面永远固定一条。

Token 估算：中文按 1.5 字符/token，其它按 4 字符/token。生产里换 tiktoken。
"""
from __future__ import annotations

from typing import Callable


def estimate_tokens(text: str) -> int:
    cn = sum(1 for c in text if "一" <= c <= "鿿")
    return int(cn / 1.5 + (len(text) - cn) / 4)


class Memory:
    def __init__(self, system: str):
        self.system = {"role": "system", "content": system}
        self._msgs: list[dict] = []

    def append(self, role: str, content: str) -> None:
        self._msgs.append({"role": role, "content": content})
        self._trim()

    def messages(self) -> list[dict]:
        return [self.system, *self._msgs]

    # 各子类重写：在 append 之后调
    def _trim(self) -> None:
        pass


class Full(Memory):
    """全部留着。短对话/重要对话用，长了就爆 context。"""


class Window(Memory):
    """只保留最近 k 条消息（不包括 system）。便宜，但会忘早期事实。"""
    def __init__(self, system: str, k: int = 8):
        super().__init__(system)
        self.k = k

    def _trim(self) -> None:
        if len(self._msgs) > self.k:
            self._msgs = self._msgs[-self.k:]


class Tokens(Memory):
    """token 预算硬上限：超了就从头扔，至少留最后一条 user。"""
    def __init__(self, system: str, max_tokens: int = 500):
        super().__init__(system)
        self.max_tokens = max_tokens

    def _trim(self) -> None:
        def total() -> int:
            return estimate_tokens(self.system["content"]) + sum(
                estimate_tokens(m["content"]) for m in self._msgs
            )
        # 至少留最后一条，否则模型连"用户刚说啥"都不知道
        while len(self._msgs) > 1 and total() > self.max_tokens:
            self._msgs.pop(0)


class Summary(Memory):
    """每攒满 k 条就调 summarize_fn 把它们压成一段事实塞到 system 后面。
    summarize_fn 是注入的，避免 memory 这层直接拉 OpenAI 依赖。"""
    def __init__(self, system: str, summarize_fn: Callable[[list[dict]], str], k: int = 6):
        super().__init__(system)
        self.summarize_fn = summarize_fn
        self.k = k
        self.summary = ""

    def _trim(self) -> None:
        if len(self._msgs) < self.k:
            return
        # 把当前 _msgs 总结成一段，然后清空；后续对话从空开始攒
        new_summary = self.summarize_fn(self._msgs)
        # 累积型摘要：保留旧的，叠加新的（防"姓名"被第二轮 summary 丢掉）
        self.summary = f"{self.summary}\n{new_summary}".strip()
        self._msgs = []

    def messages(self) -> list[dict]:
        if not self.summary:
            return [self.system, *self._msgs]
        return [
            self.system,
            {"role": "system", "content": f"历史事实：{self.summary}"},
            *self._msgs,
        ]

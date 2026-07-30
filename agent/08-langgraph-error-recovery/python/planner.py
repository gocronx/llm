"""恢复规划器：本地 mock 保证可测，OpenAI 兼容 API 用于真实演示。"""
from __future__ import annotations

import json
import os
from typing import Protocol

import httpx
from models import FailureContext, RecoveryProposal
from openai import OpenAI

SYSTEM_PROMPT = """\
你是 Agent 的恢复规划器。根据 FailureContext 生成最小、安全的恢复提案。

规则：
1. 不修改已经提交的步骤。
2. 只能使用 constraints.allowed_tools 中的工具。
3. 不得绕过权限、审批或预算限制。
4. 优先修正当前步骤；只有当前计划不可行时才重新规划。
5. 只返回 JSON RecoveryProposal，不执行任何工具。

RecoveryProposal:
{
  "strategy": "retry | patch_step | replan | human",
  "reason": "为什么这样恢复",
  "replacement_step": {"id": "...", "tool": "...", "args": {...}},
  "resume_from": "step id"
}
"""


def parse_json_object(content: str) -> dict:
    """兼容模型返回纯 JSON 或 fenced JSON。"""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"模型没有返回 JSON object: {content[:120]}")
    return json.loads(text[start : end + 1])


class RecoveryPlanner(Protocol):
    def propose(self, context: FailureContext) -> RecoveryProposal:
        """返回结构化恢复提案。"""


class RuleBasedRecoveryPlanner:
    """可重复的 mock AI，让测试不依赖网络与模型。"""

    def propose(self, context: FailureContext) -> RecoveryProposal:
        error = context["error"]
        step = context["failed_step"]
        files = context["observed_state"]["existing_files"]

        if error["code"] == "FILE_NOT_FOUND" and files:
            return {
                "strategy": "patch_step",
                "reason": "上传步骤引用了不存在的文件，改用已生成的报告文件。",
                "replacement_step": {
                    "id": step["id"],
                    "tool": step["tool"],
                    "args": {**step["args"], "path": files[0]},
                },
                "resume_from": step["id"],
            }

        return {
            "strategy": "human",
            "reason": "无法在约束内安全修复。",
            "resume_from": step["id"],
        }


class OpenAIRecoveryPlanner:
    """调用仓库统一的 OpenAI 兼容 API。"""

    def __init__(self) -> None:
        http_client = httpx.Client(trust_env=False, timeout=120.0)
        self._client = OpenAI(
            base_url=os.environ["API_BASE_URL"],
            api_key=os.environ.get("API_KEY", "not-needed"),
            http_client=http_client,
        )
        self._model = os.environ["MODEL_ID"]

    def propose(self, context: FailureContext) -> RecoveryProposal:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            max_completion_tokens=512,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "FailureContext:\n"
                    + json.dumps(context, ensure_ascii=False, indent=2),
                },
            ],
            # LM Studio 中的推理模型默认可能把 token 全耗在隐藏思考上。
            # 恢复决策只需要短 JSON，因此显式关闭 reasoning。
            extra_body={"reasoning_effort": "none"},
        )
        content = response.choices[0].message.content or "{}"
        proposal = parse_json_object(content)
        return RecoveryProposal(
            strategy=proposal["strategy"],
            reason=proposal["reason"],
            replacement_step=proposal.get("replacement_step"),
            resume_from=proposal["resume_from"],
        )

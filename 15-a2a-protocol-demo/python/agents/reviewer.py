"""Code reviewer agent: identifies security issues in code snippets."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents._base import AgentCard, call_llm, make_app

PORT = int(os.getenv("REVIEWER_PORT", "8102"))

card = AgentCard(
    name="reviewer",
    description="Review code for security issues (injection, auth, secrets, unsafe deserialization). "
                "Returns findings sorted by severity.",
    capabilities=["review-code"],
    endpoint=f"http://localhost:{PORT}",
)


REVIEW_SYSTEM = (
    "You are a security code reviewer. Output ONLY a JSON array of findings.\n"
    "Each finding: {\"severity\": \"critical|high|medium|low\", \"issue\": \"...\", \"fix\": \"...\"}.\n"
    "Sort by severity (critical first). If no issues, return [].\n"
    "Do not include analysis text outside the JSON array."
)


def review_code(payload: dict) -> dict:
    code = payload.get("code", "")
    language = payload.get("language", "unknown")
    if not code:
        return {"findings": [], "note": "no code provided"}

    user_msg = f"Language: {language}\n\nCode:\n```\n{code}\n```"
    raw = call_llm(REVIEW_SYSTEM, user_msg, max_tokens=800)

    # 容错解析：从结尾找最后一段平衡的 [...]
    import json
    findings = []
    for end in range(len(raw) - 1, -1, -1):
        if raw[end] != "]":
            continue
        depth = 0
        for start in range(end, -1, -1):
            if raw[start] == "]":
                depth += 1
            elif raw[start] == "[":
                depth -= 1
                if depth == 0:
                    try:
                        findings = json.loads(raw[start:end + 1])
                    except json.JSONDecodeError:
                        pass
                    break
        if findings:
            break

    return {"findings": findings, "language": language}


app = make_app(card, handlers={"review-code": review_code})


if __name__ == "__main__":
    from agents._base import serve
    serve(app, PORT, card.name)

"""reviewer.py —— 安全代码评审 agent。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents._base import AgentCard, call_llm, make_app
from util import extract_json_array

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
    raw = call_llm(REVIEW_SYSTEM, f"Language: {language}\n\nCode:\n```\n{code}\n```", max_tokens=800)
    return {"findings": extract_json_array(raw), "language": language}


app = make_app(card, handlers={"review-code": review_code})

if __name__ == "__main__":
    from agents._base import serve
    serve(app, PORT, card.name)

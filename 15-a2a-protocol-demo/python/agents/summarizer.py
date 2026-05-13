"""Summarizer agent: produces concise summaries of input text."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents._base import AgentCard, call_llm, make_app

PORT = int(os.getenv("SUMMARIZER_PORT", "8103"))

card = AgentCard(
    name="summarizer",
    description="Summarize long text into a short paragraph or bullet points. "
                "Outputs the summary in the same language as the input.",
    capabilities=["summarize"],
    endpoint=f"http://localhost:{PORT}",
)


def summarize(payload: dict) -> dict:
    text = payload.get("text", "")
    style = payload.get("style", "paragraph")  # 'paragraph' or 'bullets'
    max_sentences = payload.get("max_sentences", 3)
    if not text:
        return {"summary": "", "note": "no text provided"}

    if style == "bullets":
        sys_msg = (
            f"Summarize the user's text into {max_sentences} bullet points. "
            "Each bullet one short sentence. Output only the bullets, no preamble."
        )
    else:
        sys_msg = (
            f"Summarize the user's text in at most {max_sentences} sentences. "
            "Output only the summary, no preamble."
        )

    summary = call_llm(sys_msg, text, max_tokens=300)
    return {"summary": summary, "style": style}


app = make_app(card, handlers={"summarize": summarize})


if __name__ == "__main__":
    from agents._base import serve
    serve(app, PORT, card.name)

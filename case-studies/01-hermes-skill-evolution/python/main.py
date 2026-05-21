"""main.py —— 跑一遍闭环, 看"上下文工程式学习"长啥样.

剧情:
  Round 1: 干净 skill 库. 用户问"帮我写一段 Python 写文件的代码",
           接着说"我希望以后写代码默认加 try/except 并打日志, 别给我说教".
           Round 1 结束后, 后台 reviewer 把这个偏好写成 skill.

  Round 2: 新进程模拟 (清空对话, 但 skill 库保留). 用户问完全不同的代码任务
           "帮我写一段读 JSON 文件的". 模型应该自动遵守上轮的偏好,
           不需要用户再说一遍.

观察点:
  - Round 1 模型很可能不带 try/except / 带说教
  - reviewer 写出来的 skill 内容是否抓到了重点
  - Round 2 模型有没有自觉应用 skill
"""
from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv
from openai import OpenAI

import skills
import reviewer

load_dotenv()

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ.get("API_KEY", "not-needed"),
    http_client=_http,
)
_model = os.environ["MODEL_ID"]


# ── 对话辅助 ──────────────────────────────────────────────────────────
def _build_system_prompt() -> str:
    """对应 hermes/run_agent.py:6018: skill 索引 + 全文都塞进 system.

    真 hermes 是只塞索引, 全文按需 skill_view. demo 为了少一层工具调用,
    直接把全文也塞了 —— 反正 demo 阶段 skill 不会多.
    """
    base = "You are a helpful coding assistant. Be concise."
    skill_index = skills.build_skills_system_prompt()
    if not skill_index:
        return base

    # 在索引之后追加全文 (demo 简化)
    bodies = []
    for s in skills.load_all():
        bodies.append(f"### Skill: {s.name}\n{s.body}")
    return f"{base}\n\n{skill_index}\n\n" + "\n\n".join(bodies)


def _chat(messages: list[dict]) -> str:
    resp = _client.chat.completions.create(
        model=_model,
        messages=messages,
        temperature=0.7,
    )
    return resp.choices[0].message.content or ""


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# ── Round 1: 干净启动 + 用户给出偏好 ──────────────────────────────────
def round_one() -> list[dict]:
    skills.clear()  # 干净起步, 模拟从未用过
    _print_section("Round 1 —— 干净 skill 库")
    print(f"系统提示长度: {len(_build_system_prompt())} 字符 (没有 skill)")

    transcript: list[dict] = [
        {"role": "system", "content": _build_system_prompt()},
    ]

    user_msgs = [
        "帮我写一段 Python 代码, 把 'hello world' 写到 /tmp/hi.txt.",
        # 这条是关键: 用户表达了风格偏好. reviewer 应该抓到这个.
        "记住: 以后写文件 / 网络 / IO 的代码默认加 try/except 并打 logging, "
        "别给我加几段说教式注释, 我能看懂代码. 这是我的固定要求.",
    ]
    for um in user_msgs:
        transcript.append({"role": "user", "content": um})
        print(f"\n[用户] {um}")
        reply = _chat(transcript)
        transcript.append({"role": "assistant", "content": reply})
        print(f"\n[模型]\n{reply}")
    return transcript


# ── 后台复盘 (在 hermes 里是另一个线程; 这里同步跑以便观察) ──────────
def background_review(transcript: list[dict]) -> None:
    _print_section("后台复盘 —— reviewer LLM 看完整 transcript")
    decision = reviewer.review(_client, _model, transcript)
    print(f"决定: {decision.get('action')}")
    if decision.get("action") == "save":
        name = decision["name"]
        desc = decision["description"]
        body = decision["body"]
        path = skills.save(name, desc, body)
        print(f"已写: {path}")
        print(f"description: {desc}")
        print(f"body 前 200 字:\n{body[:200]}{'...' if len(body) > 200 else ''}")
    elif decision.get("action") == "skip":
        print(f"跳过原因: {decision.get('reason')}")
    else:
        print(f"解析失败, 原始输出:\n{decision.get('raw', '')}")


# ── Round 2: 新会话, 不同任务, 看模型有没有自动应用上轮 skill ─────────
def round_two() -> None:
    _print_section("Round 2 —— 新对话, 但 skill 库已就位")
    sys_prompt = _build_system_prompt()
    print(f"系统提示长度: {len(sys_prompt)} 字符 (skill 已注入)")
    print(f"已装载 skill: {[s.name for s in skills.load_all()]}")

    transcript: list[dict] = [
        {"role": "system", "content": sys_prompt},
    ]
    user_msg = "帮我写一段 Python 代码, 从 /tmp/data.json 读出来再打印每个 key."
    transcript.append({"role": "user", "content": user_msg})
    print(f"\n[用户] {user_msg}")
    print("(用户这次完全没提偏好. 模型应该自动按上轮记下的风格写.)")
    reply = _chat(transcript)
    print(f"\n[模型]\n{reply}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        skills.clear()
        print(f"已清空 {skills.SKILLS_DIR}")
        return

    transcript_r1 = round_one()
    background_review(transcript_r1)
    round_two()

    _print_section("结束")
    print("Round 2 跟 Round 1 风格对比清楚了吗?")
    print(f"skill 库位置: {skills.SKILLS_DIR}")
    print("可以手工编辑 .skills/*/SKILL.md 改 skill, 再跑试试.")
    print("清空: python main.py --clear")


if __name__ == "__main__":
    main()

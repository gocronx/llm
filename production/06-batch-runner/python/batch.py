"""batch.py —— 批量跑 LLM 调用：并发 + 重试 + checkpoint 续跑。整文件 cp 进项目即可。

设计三要素：
  - 重试：5xx / 429 / 网络挂 → 指数退避；4xx 不重试（参数错重试也是错）。
  - 断点续跑：每个 job 成功就 append 一行到 output JSONL。重启时读 output 跳过已成功的 id。
  - 失败不入"已完成"：失败的 job 重启时会重跑（不要 silently 把 error 当 done）。
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import (
    RetryError, Retrying, retry_if_exception_type,
    stop_after_attempt, wait_exponential,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.environ["API_BASE_URL"]
API_KEY = os.getenv("API_KEY", "not-needed")
MODEL_ID = os.environ["MODEL_ID"]

_http = httpx.Client(trust_env=False, timeout=60.0)
_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY, http_client=_http)

MAX_ATTEMPTS = 3
MAX_OUTPUT_TOKENS = 150


class TransientError(Exception):
    """5xx / 429 / 网络 —— 可以重试。4xx 不算 transient。"""


@dataclass(frozen=True)
class Job:
    id: str
    prompt: str


@dataclass
class Result:
    id: str
    prompt: str
    answer: str | None
    error: str | None
    elapsed_ms: int
    attempts: int
    tokens: int


def _single_call(prompt: str) -> tuple[str, int]:
    """一次 LLM 调用。SDK 的 APIConnectionError / APITimeoutError / RateLimitError
    都翻译成 TransientError；其它（400/401）让 tenacity 不重试地往外抛。"""
    from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
    try:
        resp = _client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
    except (APIConnectionError, APITimeoutError, RateLimitError) as e:
        raise TransientError(str(e)) from e
    except APIStatusError as e:
        if e.status_code >= 500:
            raise TransientError(f"http {e.status_code}") from e
        raise  # 4xx 不重试

    answer = (resp.choices[0].message.content or "").strip()
    usage = getattr(resp, "usage", None)
    tokens = getattr(usage, "total_tokens", None) or (len(prompt) + len(answer)) // 2
    return answer, tokens


def run_one(job: Job) -> Result:
    """跑一个 job，带退避重试。失败时记录最后一次错误。"""
    started = time.time()
    attempts = 0
    last_exc: Exception | None = None
    answer: str | None = None
    tokens = 0

    retrying = Retrying(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(TransientError),
        reraise=False,
    )
    try:
        for attempt in retrying:
            with attempt:
                attempts += 1
                answer, tokens = _single_call(job.prompt)
    except RetryError as e:
        last_exc = e.last_attempt.exception() if e.last_attempt else e
    except Exception as e:
        last_exc = e

    elapsed_ms = int((time.time() - started) * 1000)
    if answer is None:
        return Result(id=job.id, prompt=job.prompt, answer=None,
                      error=str(last_exc), elapsed_ms=elapsed_ms,
                      attempts=attempts, tokens=0)
    return Result(id=job.id, prompt=job.prompt, answer=answer, error=None,
                  elapsed_ms=elapsed_ms, attempts=attempts, tokens=tokens)


def load_jobs(path: Path) -> list[Job]:
    out: list[Job] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        out.append(Job(id=d["id"], prompt=d["prompt"]))
    return out


def load_done(out_path: Path) -> set[str]:
    """从 output 里捞出已成功（error == None）的 id。失败的不算 done。"""
    if not out_path.exists():
        return set()
    done: set[str] = set()
    for line in out_path.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("error") is None and "id" in d:
            done.add(d["id"])
    return done


def append_result(out_path: Path, result: Result) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")


def run_batch(jobs: list[Job], out_path: Path, concurrency: int = 4,
              resume: bool = True, on_progress: object = None) -> dict:
    done = load_done(out_path) if resume else set()
    todo = [j for j in jobs if j.id not in done]
    print(f"  jobs: {len(jobs)} total, {len(done)} already done, {len(todo)} to run")
    print(f"  concurrency: {concurrency}")
    if not todo:
        return {"total": len(jobs), "ran": 0, "ok": len(done), "failed": 0,
                "elapsed_s": 0, "tokens": 0, "avg_attempts": 0,
                "throughput_per_min": 0.0}

    started = time.time()
    ok = failed = total_tokens = total_attempts = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(run_one, j): j for j in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            append_result(out_path, r)
            total_tokens += r.tokens
            total_attempts += r.attempts
            if r.error is None:
                ok += 1
                status = "✓"
            else:
                failed += 1
                status = "✗"
            elapsed = int(time.time() - started)
            eta = int(elapsed * (len(todo) - i) / max(i, 1))
            print(f"  [{i:3d}/{len(todo)}] {status} {r.id:<8} "
                  f"{r.elapsed_ms:>5}ms attempts={r.attempts}  "
                  f"elapsed={elapsed}s eta={eta}s", flush=True)
            if on_progress:
                on_progress(r, i, len(todo))

    elapsed_s = max(int(time.time() - started), 1)
    return {
        "total": len(jobs),
        "ran": len(todo),
        "ok": ok,
        "failed": failed,
        "elapsed_s": elapsed_s,
        "tokens": total_tokens,
        "avg_attempts": round(total_attempts / len(todo), 2),
        "throughput_per_min": round(len(todo) / elapsed_s * 60, 1),
    }

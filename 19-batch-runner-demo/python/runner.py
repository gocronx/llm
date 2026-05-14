"""Concurrent LLM batch runner with retry, resume-from-checkpoint, and progress."""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")

HERE = Path(__file__).parent
DEFAULT_INPUT = HERE / "data" / "sample.jsonl"
DEFAULT_OUTPUT = HERE / "results" / "out.jsonl"

MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 60
MAX_OUTPUT_TOKENS = 150


class TransientError(Exception):
    """5xx / 429 / network — safe to retry."""


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
    """One HTTP call. Raises TransientError for 5xx/429/network, lets 4xx propagate."""
    try:
        resp = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": MAX_OUTPUT_TOKENS,
            },
            timeout=TIMEOUT_SECONDS,
        )
    except (requests.Timeout, requests.ConnectionError) as e:
        raise TransientError(f"network: {e}") from e

    if resp.status_code == 429 or resp.status_code >= 500:
        raise TransientError(f"http {resp.status_code}")
    resp.raise_for_status()

    data = resp.json()
    answer = data["choices"][0]["message"]["content"].strip()
    tokens = data.get("usage", {}).get("total_tokens",
                                       (len(prompt) + len(answer)) // 2)
    return answer, tokens


def run_one(job: Job) -> Result:
    """Execute one job with bounded retries. Records actual attempts taken."""
    started = time.time()
    attempts = 0
    last_exception: Exception | None = None
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
        last_exception = e.last_attempt.exception() if e.last_attempt else e
    except Exception as e:
        last_exception = e

    elapsed_ms = int((time.time() - started) * 1000)
    if answer is None:
        return Result(
            id=job.id, prompt=job.prompt, answer=None,
            error=str(last_exception), elapsed_ms=elapsed_ms,
            attempts=attempts, tokens=0,
        )
    return Result(
        id=job.id, prompt=job.prompt, answer=answer, error=None,
        elapsed_ms=elapsed_ms, attempts=attempts, tokens=tokens,
    )


def load_jobs(path: Path) -> list[Job]:
    jobs: list[Job] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                jobs.append(Job(id=d["id"], prompt=d["prompt"]))
    return jobs


def load_done(out_path: Path) -> set[str]:
    """Successful ids from the output file. Failed entries are not 'done'
    and will be retried on the next run."""
    if not out_path.exists():
        return set()
    done: set[str] = set()
    with out_path.open(encoding="utf-8") as f:
        for line in f:
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


def run_batch(
    jobs: list[Job],
    out_path: Path,
    concurrency: int = 4,
    resume: bool = True,
) -> dict:
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
            print(
                f"  [{i:3d}/{len(todo)}] {status} {r.id:<8} "
                f"{r.elapsed_ms:>5}ms attempts={r.attempts}  "
                f"elapsed={elapsed}s eta={eta}s",
                flush=True,
            )

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    jobs = load_jobs(Path(args.input))
    if args.limit:
        jobs = jobs[: args.limit]

    print("=== batch runner ===")
    print(f"  input:  {args.input}")
    print(f"  output: {args.output}\n")

    out_path = Path(args.output)
    if args.no_resume:
        out_path.unlink(missing_ok=True)

    summary = run_batch(jobs, out_path, args.concurrency, resume=not args.no_resume)

    print("\n=== summary ===")
    for k, v in summary.items():
        print(f"  {k:<20} {v}")


if __name__ == "__main__":
    main()

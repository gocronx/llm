"""Resolve `@path[:start[-end]]` mentions in user messages into attached file blocks.

Paths are resolved against WORKSPACE only — anything escaping is reported as an
error placeholder so the LLM (and the user) can see what was rejected. Files are
read once per (path, line-range) and capped at MAX_BYTES.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

WORKSPACE = Path(__file__).parent / "workspace"
MAX_BYTES = 16_000

_REF_RE = re.compile(r"@([A-Za-z0-9_./-]+)(?::(\d+)(?:-(\d+))?)?")


@dataclass(frozen=True)
class ResolvedRef:
    raw: str
    path: Path | None
    start: int | None
    end: int | None
    body: str
    error: str | None


def _safe_resolve(rel_path: str) -> Path | None:
    try:
        candidate = (WORKSPACE / rel_path).resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(WORKSPACE.resolve())
    except ValueError:
        return None
    return candidate


def _read_slice(path: Path, start: int | None, end: int | None) -> tuple[str, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "", "file not found"
    except UnicodeDecodeError:
        return "", "not a UTF-8 text file"

    if start is None:
        if len(text) > MAX_BYTES:
            return text[:MAX_BYTES] + f"\n... [truncated at {MAX_BYTES} bytes]", None
        return text, None

    lines = text.splitlines()
    if start < 1 or start > len(lines):
        return "", f"start line {start} out of range (file has {len(lines)} lines)"
    last = min(end or start, len(lines))
    return "\n".join(lines[start - 1:last]), None


def resolve_refs(message: str) -> tuple[list[ResolvedRef], list[Path]]:
    """Parse every @ref in `message`. Returns (refs in order, deduped files actually read)."""
    cache: dict[tuple, ResolvedRef] = {}
    ordered: list[ResolvedRef] = []
    files_read: list[Path] = []

    for m in _REF_RE.finditer(message):
        rel, s_str, e_str = m.group(1), m.group(2), m.group(3)
        start = int(s_str) if s_str else None
        end = int(e_str) if e_str else None
        key = (rel, start, end)
        if key in cache:
            ordered.append(cache[key])
            continue

        path = _safe_resolve(rel)
        if path is None:
            ref = ResolvedRef(m.group(0), None, start, end, "",
                              "path outside workspace or invalid")
        elif not path.exists():
            ref = ResolvedRef(m.group(0), path, start, end, "", "file not found")
        else:
            body, err = _read_slice(path, start, end)
            ref = ResolvedRef(m.group(0), path, start, end, body, err)
            if err is None and path not in files_read:
                files_read.append(path)

        cache[key] = ref
        ordered.append(ref)

    return ordered, files_read


def render_for_llm(message: str, refs: list[ResolvedRef]) -> str:
    """Append a single deduped `<file>` block per unique ref to the original message.

    Errors render as `[error: ...]` so they're visible to the LLM rather than dropped.
    """
    if not refs:
        return message

    blocks: list[str] = []
    seen: set[str] = set()
    for r in refs:
        if r.raw in seen:
            continue
        seen.add(r.raw)
        header = f'<file path="{r.path}"' if r.path else '<file path="(invalid)"'
        if r.start:
            header += f' lines="{r.start}-{r.end or r.start}"'
        header += ">"
        content = f"[error: {r.error}]" if r.error else r.body
        blocks.append(f"{header}\n{content}\n</file>")

    return (
        f"{message}\n\n"
        "---\n"
        "Attached files (referenced via @-mentions in the message above):\n\n"
        + "\n\n".join(blocks)
    )

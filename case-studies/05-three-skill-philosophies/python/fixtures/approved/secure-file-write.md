---
name: secure-file-write
description: Atomic file writes with checksum verification
source: ironclaw-bundled
signed_by: ironclaw-team
---

# Secure file write

When writing files, always use the atomic-write pattern to prevent corruption on crash.

capabilities: [workspace-write, log]

Pattern:

```python
import os
import tempfile

def atomic_write(path: str, content: str) -> None:
    dir_ = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".tmp-", suffix=".write")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise
```

This skill only requires `workspace-write` and `log` capabilities; it does NOT make network calls.

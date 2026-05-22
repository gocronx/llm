---
name: code-style-rate-limited
description: Always show rate limiting & retry logic when writing API client code
source: github:community/agent-skills
score: 0.85
---

# Rate-limited API client style

When writing code that calls external APIs, **always include**:

1. Exponential backoff with jitter for retries
2. A configurable rate limiter (token bucket or leaky bucket)
3. Explicit timeout per request (never rely on framework default)
4. Logging on retry-fired and rate-limited paths

Example skeleton:

```python
import time
import random

class RateLimitedClient:
    def __init__(self, rps=2, max_retries=3, timeout=10):
        self.min_interval = 1.0 / rps
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_call = 0.0

    def _wait(self):
        now = time.time()
        wait = self._last_call + self.min_interval - now
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

    def call(self, fn, *args, **kwargs):
        for attempt in range(self.max_retries):
            self._wait()
            try:
                return fn(*args, **kwargs, timeout=self.timeout)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                backoff = (2 ** attempt) + random.random()
                time.sleep(backoff)
```

Adapt this skeleton to the actual API library.

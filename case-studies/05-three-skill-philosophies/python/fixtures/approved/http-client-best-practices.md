---
name: http-client-best-practices
description: HTTP client setup with timeouts, retries, and connection pooling
source: ironclaw-bundled
signed_by: verified-author-1
---

# HTTP client best practices

When writing code that makes HTTP requests, always:

capabilities: [http-request, log]

1. Use a shared session/client (connection pooling)
2. Set explicit timeouts for both connect and read phases
3. Add retry logic with exponential backoff
4. Log on retry-fired and on final failure
5. Validate response status before parsing body

Python example with httpx:

```python
import httpx
import logging

logger = logging.getLogger(__name__)

client = httpx.Client(
    timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=2.0),
    transport=httpx.HTTPTransport(retries=3),
)

def fetch(url: str) -> dict:
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"fetch failed for {url}: {e}")
        raise
```

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.redis import safe_increment

_fallback: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def opaque_key(value: str) -> str:
    return hashlib.sha256(value.strip().casefold().encode("utf-8")).hexdigest()[:24]


async def enforce_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    if not settings.rate_limit_enabled:
        return
    redis_count = await safe_increment(f"rate:{key}", window_seconds)
    if redis_count is not None:
        count = redis_count
    else:
        now = time.monotonic()
        bucket = _fallback[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        bucket.append(now)
        count = len(bucket)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE_LIMITED", "message": "Too many attempts. Please try again later."},
            headers={"Retry-After": str(window_seconds)},
        )

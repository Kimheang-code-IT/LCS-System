"""Centralized Redis access.

One lazily-created connection pool per application process. Every helper is
"safe": a missing client, a timeout or a connection error degrades to a cache
miss rather than an exception, so PostgreSQL transactions are never aborted by
Redis problems. Callers that need fail-closed behaviour (rate limiting) must
handle the ``None``/``False`` results explicitly.
"""

import redis.asyncio as aioredis

from app.core.config import settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    """Return a lazily created Redis client, or None when disabled.

    Normal CRUD must never depend on Redis. Callers should treat a ``None``
    client (or a connection error) as a cache miss rather than a failure.
    """
    global _client
    if not settings.redis_enabled:
        return None
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=settings.redis_socket_timeout_seconds,
            socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
            retry_on_timeout=True,
            health_check_interval=30,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def redis_health() -> str:
    """Return ``up``, ``down`` or ``disabled``; never raises."""
    if not settings.redis_enabled:
        return "disabled"
    client = get_redis()
    if client is None:
        return "disabled"
    try:
        await client.ping()
        return "up"
    except Exception:
        return "down"


async def safe_get(key: str) -> str | None:
    client = get_redis()
    if client is None:
        return None
    try:
        return await client.get(key)
    except Exception:
        return None


async def safe_set(key: str, value: str, ex: int | None = None) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.set(key, value, ex=ex)
    except Exception:
        return


async def safe_delete(key: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception:
        return


async def safe_exists(key: str) -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        return bool(await client.exists(key))
    except Exception:
        return False


async def safe_increment(key: str, window_seconds: int) -> int | None:
    """Atomically increment a fixed-window counter and set its first expiry."""
    client = get_redis()
    if client is None:
        return None
    try:
        async with client.pipeline(transaction=True) as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, window_seconds, nx=True)
            result = await pipeline.execute()
        return int(result[0])
    except Exception:
        return None


async def safe_incr(key: str) -> int | None:
    """Plain INCR without TTL (namespace version counters). Never raises."""
    client = get_redis()
    if client is None:
        return None
    try:
        return int(await client.incr(key))
    except Exception:
        return None


async def safe_counter(key: str) -> int:
    """Read an integer counter (0 when missing). Never raises."""
    raw = await safe_get(key)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0

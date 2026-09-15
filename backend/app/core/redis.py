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
        _client = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


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

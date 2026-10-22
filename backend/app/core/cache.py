"""Namespaced JSON read-through cache on top of the shared Redis client.

Design
------
* Every value lives under ``<prefix>:<env>:cache:<namespace>:<digest>`` where
  the digest is a hash of the logical key parts. Values are JSON.
* Invalidation is version-based: each namespace has a counter
  ``<prefix>:<env>:cachever:<namespace>`` that is part of every key. Bumping
  the counter invalidates the whole namespace in O(1) without scanning keys.
* Nothing here may raise: a missing client, timeout, corrupt payload or
  connection error all degrade to a cache miss so PostgreSQL keeps working and
  open transactions are never aborted by Redis.
* ``settings.cache_enabled`` is a hard switch (tests turn it off so cached
  data can never leak between test databases).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.core import redis as redis_core
from app.core.config import settings

logger = logging.getLogger(__name__)

# Logical namespaces. Keep this list small and explicit so invalidation has a
# single source of truth.
NAMESPACES = ("master_data", "reports", "auth")


def _prefix() -> str:
    env = (settings.environment or "dev").strip().lower() or "dev"
    return f"{settings.cache_key_prefix}:{env}"


def version_key(namespace: str) -> str:
    return f"{_prefix()}:cachever:{namespace}"


def key(namespace: str, *parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"{_prefix()}:cache:{namespace}:{digest}"


def enabled() -> bool:
    return bool(settings.cache_enabled and settings.redis_enabled)


async def version(namespace: str) -> int:
    return await redis_core.safe_counter(version_key(namespace))


async def bump(*namespaces: str) -> None:
    """Invalidate every cached value in the given namespaces."""
    # Nothing was cached, so there is nothing to invalidate. Skipping the Redis
    # round-trip keeps a Redis outage from adding a connect timeout to writes.
    if not enabled():
        return
    for namespace in namespaces:
        await redis_core.safe_incr(version_key(namespace))


async def get_json(namespace: str, *parts: Any) -> Any | None:
    if not enabled():
        return None
    cache_key = key(namespace, await version(namespace), *parts)
    raw = await redis_core.safe_get(cache_key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        # Corrupt or incompatible payload: drop it and fall back to the DB.
        await redis_core.safe_delete(cache_key)
        return None


async def set_json(namespace: str, *parts: Any, value: Any, ttl_seconds: int) -> None:
    if not enabled() or ttl_seconds <= 0:
        return
    cache_key = key(namespace, await version(namespace), *parts)
    try:
        payload = json.dumps(value, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        return
    await redis_core.safe_set(cache_key, payload, ex=ttl_seconds)

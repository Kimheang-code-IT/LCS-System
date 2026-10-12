"""PostgreSQL advisory-lock helpers for cross-replica coordination.

Advisory locks are used only to *avoid duplicate work* (for example two API
replicas both starting the scheduled backup). They are session-scoped and
release automatically when the connection closes. Durable business state stays
in PostgreSQL rows with unique constraints — Redis is never the authority for
financial or business mutations.

On non-PostgreSQL bindings (SQLite test databases), an in-process lock preserves
the same mutual-exclusion contract for tests and single-process development.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
_local_locks: dict[str, asyncio.Lock] = {}


def _lock_key(name: str) -> int:
    """Map a name to the signed 64-bit key space used by pg advisory locks."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


def _dialect_name(session: AsyncSession) -> str:
    try:
        bind = session.get_bind()
        return str(getattr(getattr(bind, "dialect", None), "name", "") or "")
    except Exception:  # noqa: BLE001
        return ""


@asynccontextmanager
async def advisory_lock(session: AsyncSession, name: str) -> AsyncIterator[bool]:
    """Try to hold a PostgreSQL advisory lock for the duration of the block.

    Yields ``True`` when the lock is held and ``False`` when another task or
    process holds it.
    """
    if _dialect_name(session) != "postgresql":
        lock = _local_locks.setdefault(name, asyncio.Lock())
        if lock.locked():
            yield False
            return
        await lock.acquire()
        try:
            yield True
        finally:
            lock.release()
        return
    key = _lock_key(name)
    try:
        acquired = bool(await session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}))
    except Exception as exc:  # noqa: BLE001 - coordination must never break the caller
        logger.warning("Advisory lock %s unavailable: %s", name, exc)
        yield True
        return
    try:
        yield acquired
    finally:
        if acquired:
            try:
                await session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            except Exception:  # noqa: BLE001 - released on connection close anyway
                logger.warning("Advisory unlock %s failed; released with the session.", name)

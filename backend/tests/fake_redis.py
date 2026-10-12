"""In-memory async Redis stand-in for tests with a manually advanced clock.

Supports exactly the subset of the Redis API used by ``app.core.redis``,
``app.core.cache`` and ``app.core.rate_limit``: get/set(ex,nx)/delete/exists/
incr/expire(nx)/ping/scan_iter/pipeline(incr,expire,nx)/aclose. Set ``fail=True``
to simulate an outage at any point.
"""

from __future__ import annotations

import fnmatch
from typing import Any


class FakePipeline:
    def __init__(self, client: FakeRedis) -> None:
        self.client = client
        self.ops: list[tuple] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def incr(self, key: str):
        self.ops.append(("incr", key))
        return self

    def expire(self, key: str, seconds: int, nx: bool = False):
        self.ops.append(("expire", key, seconds, nx))
        return self

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for op in self.ops:
            if op[0] == "incr":
                results.append(await self.client.incr(op[1]))
            else:
                results.append(await self.client.expire(op[1], op[2], op[3]))
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expires: dict[str, float] = {}
        self.now = 0.0
        self.fail = False
        self.commands: list[str] = []

    def _check(self) -> None:
        if self.fail:
            raise ConnectionError("redis unavailable (simulated)")

    def _purge(self) -> None:
        for key, at in list(self.expires.items()):
            if at is not None and at <= self.now:
                self.store.pop(key, None)
                self.expires.pop(key, None)

    async def get(self, key: str):
        self._check()
        self._purge()
        self.commands.append(f"get:{key}")
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None, nx: bool = False):
        self._check()
        self._purge()
        if nx and key in self.store:
            return None
        self.store[key] = str(value)
        self.expires[key] = None if ex is None else self.now + int(ex)
        return True

    async def delete(self, *keys: str) -> int:
        self._check()
        removed = 0
        for key in keys:
            if key in self.store:
                self.store.pop(key, None)
                self.expires.pop(key, None)
                removed += 1
        return removed

    async def exists(self, key: str) -> int:
        self._check()
        self._purge()
        return 1 if key in self.store else 0

    async def incr(self, key: str) -> int:
        self._check()
        self._purge()
        value = int(self.store.get(key, "0")) + 1
        self.store[key] = str(value)
        return value

    async def expire(self, key: str, seconds: int, nx: bool = False) -> bool:
        self._check()
        if key not in self.store:
            return False
        if nx and self.expires.get(key) is not None:
            return False
        self.expires[key] = self.now + int(seconds)
        return True

    async def ping(self):
        self._check()
        return True

    async def scan_iter(self, match: str | None = None, count: int = 200):
        self._purge()
        for key in list(self.store):
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    def pipeline(self, transaction: bool = True):
        return FakePipeline(self)

    async def aclose(self):
        return None

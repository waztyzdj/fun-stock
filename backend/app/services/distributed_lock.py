from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

from redis import Redis


class RedisDistributedLock:
    def __init__(self, client: Redis, *, namespace: str = "fun-stock:lock") -> None:
        self.client = client
        self.namespace = namespace

    @contextmanager
    def acquire(self, name: str, *, ttl_seconds: int) -> Iterator[bool]:
        key = f"{self.namespace}:{name}"
        token = uuid4().hex
        acquired = bool(self.client.set(key, token, nx=True, ex=ttl_seconds))
        try:
            yield acquired
        finally:
            if acquired and self.client.get(key) == token:
                self.client.delete(key)

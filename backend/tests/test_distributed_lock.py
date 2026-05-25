from app.services.distributed_lock import RedisDistributedLock


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        del ex
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


def test_redis_distributed_lock_releases_owned_lock() -> None:
    client = FakeRedis()
    lock = RedisDistributedLock(client)  # type: ignore[arg-type]

    with lock.acquire("sync", ttl_seconds=60) as acquired:
        assert acquired
        assert _keys(client) == ["fun-stock:lock:sync"]

    assert _keys(client) == []


def test_redis_distributed_lock_does_not_release_unowned_lock() -> None:
    client = FakeRedis()
    client.values["fun-stock:lock:sync"] = "other"
    lock = RedisDistributedLock(client)  # type: ignore[arg-type]

    with lock.acquire("sync", ttl_seconds=60) as acquired:
        assert not acquired

    assert client.values["fun-stock:lock:sync"] == "other"


def _keys(client: FakeRedis) -> list[str]:
    return sorted(client.values)

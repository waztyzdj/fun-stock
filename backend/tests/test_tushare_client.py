from typing import Any

import pandas as pd
from pytest import MonkeyPatch

from app.adapters.tushare import client as client_module
from app.adapters.tushare.client import (
    TushareClient,
    TushareRateLimitError,
    TushareTransientNetworkError,
)


class FakePro:
    def __init__(self) -> None:
        self.calls = 0

    def query(self, api_name: str, **kwargs: Any) -> pd.DataFrame:
        del api_name, kwargs
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("每分钟最多访问该接口 2 次，请稍后重试")
        return pd.DataFrame([{"ts_code": "000001.SZ"}])


class FakeNetworkPro:
    def __init__(self, *, recover: bool) -> None:
        self.calls = 0
        self.recover = recover

    def query(self, api_name: str, **kwargs: Any) -> pd.DataFrame:
        del api_name, kwargs
        self.calls += 1
        if not self.recover or self.calls == 1:
            raise RuntimeError("Failed to resolve 'api.waditu.com'")
        return pd.DataFrame([{"ts_code": "000002.SZ"}])


def test_tushare_client_sleeps_and_retries_rate_limit(monkeypatch: MonkeyPatch) -> None:
    sleep_seconds: list[float] = []
    monkeypatch.setattr(client_module, "sleep", lambda seconds: sleep_seconds.append(seconds))
    client = TushareClient.__new__(TushareClient)
    client.token = "test-token"
    client._pro = FakePro()
    client.rate_limit_sleep_seconds = 0.5
    client.rate_limit_max_retries = 1
    client.network_retry_sleep_seconds = 60
    client.network_max_retries = 0

    records = client._call("daily")

    assert records == [{"ts_code": "000001.SZ"}]
    assert sleep_seconds == [0.5]


def test_tushare_client_raises_after_rate_limit_retries(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "sleep", lambda seconds: None)
    client = TushareClient.__new__(TushareClient)
    client.token = "test-token"
    client._pro = FakePro()
    client.rate_limit_sleep_seconds = 0
    client.rate_limit_max_retries = 0
    client.network_retry_sleep_seconds = 60
    client.network_max_retries = 0

    try:
        client._call("daily")
    except TushareRateLimitError:
        return

    raise AssertionError("Expected TushareRateLimitError.")


def test_tushare_client_sleeps_and_retries_transient_network_error(
    monkeypatch: MonkeyPatch,
) -> None:
    sleep_seconds: list[float] = []
    monkeypatch.setattr(client_module, "sleep", lambda seconds: sleep_seconds.append(seconds))
    client = TushareClient.__new__(TushareClient)
    client.token = "test-token"
    client._pro = FakeNetworkPro(recover=True)
    client.rate_limit_sleep_seconds = 20
    client.rate_limit_max_retries = 0
    client.network_retry_sleep_seconds = 1.5
    client.network_max_retries = 1

    records = client._call("daily")

    assert records == [{"ts_code": "000002.SZ"}]
    assert sleep_seconds == [1.5]


def test_tushare_client_raises_after_transient_network_retries(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "sleep", lambda seconds: None)
    client = TushareClient.__new__(TushareClient)
    client.token = "test-token"
    client._pro = FakeNetworkPro(recover=False)
    client.rate_limit_sleep_seconds = 20
    client.rate_limit_max_retries = 0
    client.network_retry_sleep_seconds = 0
    client.network_max_retries = 0

    try:
        client._call("daily")
    except TushareTransientNetworkError:
        return

    raise AssertionError("Expected TushareTransientNetworkError.")

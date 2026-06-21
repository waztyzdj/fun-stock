from datetime import date
from typing import Any

from app.tasks.build_fundamental_factors import run


class FakeRepository:
    def __init__(self, session: object) -> None:
        del session
        self.start_date: date | None = None

    def rebuild_factor_values(self, *, start_date: date | None = None) -> int:
        self.start_date = start_date
        return 20

    def latest_factor_date(self) -> date:
        return date(2026, 5, 28)


class FakeSession:
    committed = False

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb

    def commit(self) -> None:
        self.committed = True


def test_build_fundamental_factors_run_uses_repository(monkeypatch: Any, capsys: Any) -> None:
    fake_session = FakeSession()
    fake_repository = FakeRepository(fake_session)

    monkeypatch.setattr("app.tasks.build_fundamental_factors.SessionLocal", lambda: fake_session)
    monkeypatch.setattr(
        "app.tasks.build_fundamental_factors.FactorRepository",
        lambda session: fake_repository,
    )

    run(start_date="2020-01-01")

    output = capsys.readouterr().out
    assert "FUNDAMENTAL_FACTORS" in output
    assert "rows=20" in output
    assert fake_repository.start_date == date(2020, 1, 1)
    assert fake_session.committed is True

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.repositories.data_sync import DataSyncRepository
from app.tasks.sync_tushare_scheduler import PROVIDER

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncJobResponse(BaseModel):
    api_name: str
    status: str
    cursor_value: str | None
    last_success_at: datetime | None
    updated_at: datetime
    error_message: str | None


class ProblemRunResponse(BaseModel):
    api_name: str
    status: str
    run_id: int
    window_start: str | None
    window_end: str | None
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None


class QualityAlertResponse(BaseModel):
    api_name: str
    status: str
    severity: str
    check_name: str
    message: str | None
    observed_value: str | None
    created_at: datetime


class TableCountResponse(BaseModel):
    name: str
    rows: int


class TushareSyncStatusResponse(BaseModel):
    jobs: list[SyncJobResponse]
    problem_runs: list[ProblemRunResponse]
    quality_alerts: list[QualityAlertResponse]
    table_counts: list[TableCountResponse]
    retryable_failed_count: int
    blocked_count: int


@router.get("/tushare/status", response_model=TushareSyncStatusResponse)
def tushare_sync_status(
    session: Annotated[Session, Depends(get_db_session)],
) -> TushareSyncStatusResponse:
    repository = DataSyncRepository(session)
    jobs = repository.list_jobs(provider=PROVIDER, limit=100)
    problem_runs = repository.list_recent_problem_runs(provider=PROVIDER, limit=10)
    quality_alerts = repository.list_recent_quality_alerts(provider=PROVIDER, limit=10)
    blocked_jobs = repository.list_blocked_jobs(provider=PROVIDER, limit=100)
    retryable_failed_jobs = repository.list_retryable_failed_jobs(provider=PROVIDER)

    return TushareSyncStatusResponse(
        jobs=[
            SyncJobResponse(
                api_name=job.api_name,
                status=job.status,
                cursor_value=job.cursor_value,
                last_success_at=job.last_success_at,
                updated_at=job.updated_at,
                error_message=_compact_message(job.error_message),
            )
            for job in jobs
        ],
        problem_runs=[
            ProblemRunResponse(
                api_name=run.job.api_name,
                status=run.status,
                run_id=run.id,
                window_start=run.window_start,
                window_end=run.window_end,
                started_at=run.started_at,
                finished_at=run.finished_at,
                error_message=_compact_message(run.error_message),
            )
            for run in problem_runs
        ],
        quality_alerts=[
            QualityAlertResponse(
                api_name=check.run.job.api_name,
                status=check.status,
                severity=check.severity,
                check_name=check.check_name,
                message=check.message,
                observed_value=check.observed_value,
                created_at=check.created_at,
            )
            for check in quality_alerts
        ],
        table_counts=_table_counts(session),
        retryable_failed_count=len(retryable_failed_jobs),
        blocked_count=len(blocked_jobs),
    )


def _table_counts(session: Session) -> list[TableCountResponse]:
    tables = [
        ("stocks", "app.stocks"),
        ("trade_calendars", "app.trade_calendars"),
        ("daily_quotes", "app.daily_quotes"),
        ("daily_indicators", "app.daily_indicators"),
        ("adj_factors", "app.adj_factors"),
    ]
    counts: list[TableCountResponse] = []
    for name, table_name in tables:
        rows = session.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one()
        counts.append(TableCountResponse(name=name, rows=int(rows)))
    return counts


def _compact_message(value: str | None, *, max_length: int = 240) -> str | None:
    if value is None:
        return None
    message = value.strip().splitlines()[0]
    if len(message) <= max_length:
        return message
    return f"{message[:max_length]}..."

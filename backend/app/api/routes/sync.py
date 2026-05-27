from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.models.backfill import BackfillBatch, BackfillJob
from app.repositories.backfill import (
    BACKFILL_RUNNING_STATUS,
    BackfillRepository,
)
from app.repositories.data_sync import DataSyncRepository
from app.services.data_completeness import (
    CoreMarketCompletenessReport,
    CoreMarketCompletenessService,
)
from app.services.data_repair import CoreMarketDataRepairService, DataRepairResult
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


class BackfillBatchResponse(BaseModel):
    batch_index: int
    status: str
    cursor_date: date | None
    start_date: date | None
    end_date: date | None
    trade_days: int
    windows: int
    rows_fetched: int
    rows_upserted: int
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None


class BackfillJobResponse(BaseModel):
    id: int
    name: str
    task_type: str
    status: str
    start_date: date | None
    end_date: date | None
    cursor_date: date | None
    total_batches: int
    succeeded_batches: int
    failed_batches: int
    blocked_batches: int
    total_windows: int
    rows_fetched: int
    rows_upserted: int
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    recent_batches: list[BackfillBatchResponse]
    is_running: bool
    remaining_trade_days: int | None
    estimated_remaining_batches: int | None
    latest_batch: BackfillBatchResponse | None


class MissingDateRangeResponse(BaseModel):
    start_date: date
    end_date: date
    days: int


class TableCompletenessResponse(BaseModel):
    api_name: str
    table_name: str
    expected_trade_days: int
    present_trade_days: int
    missing_trade_days: int
    latest_present_date: date | None
    completeness_ratio: float
    missing_dates: list[date]
    repair_ranges: list[MissingDateRangeResponse]


class CoreCompletenessResponse(BaseModel):
    layer: str
    exchange: str
    start_date: date
    end_date: date
    total_missing_trade_days: int
    tables: list[TableCompletenessResponse]


class RepairRangeResponse(BaseModel):
    start_date: date
    end_date: date
    days: int


class DataRepairResponse(BaseModel):
    start_date: date
    end_date: date
    missing_trade_days: int
    repair_ranges: list[RepairRangeResponse]
    executed: bool
    daily_quotes: int
    daily_indicators: int
    adj_factors: int


class BackfillBatchFixResponse(BaseModel):
    scanned_batches: int
    fixed_batches: int
    still_failed_batches: int
    stale_running_batches: int


class TushareSyncStatusResponse(BaseModel):
    jobs: list[SyncJobResponse]
    problem_runs: list[ProblemRunResponse]
    quality_alerts: list[QualityAlertResponse]
    table_counts: list[TableCountResponse]
    backfill_jobs: list[BackfillJobResponse]
    core_completeness: CoreCompletenessResponse
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
    backfill_jobs = BackfillRepository(session).list_recent_jobs(provider=PROVIDER, limit=5)
    completeness = CoreMarketCompletenessService(session).scan(
        start_date=_default_completeness_start_date(),
        end_date=date.today(),
    )

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
        backfill_jobs=[_backfill_job_response(session, job) for job in backfill_jobs],
        core_completeness=_core_completeness_response(completeness),
        retryable_failed_count=len(retryable_failed_jobs),
        blocked_count=len(blocked_jobs),
    )


@router.get("/tushare/completeness", response_model=CoreCompletenessResponse)
def tushare_core_completeness(
    session: Annotated[Session, Depends(get_db_session)],
    start_date: date | None = None,
    end_date: date | None = None,
    layer: Literal["app", "raw"] = "app",
) -> CoreCompletenessResponse:
    report = CoreMarketCompletenessService(session).scan(
        start_date=start_date or _default_completeness_start_date(),
        end_date=end_date or date.today(),
        layer=layer,
    )
    return _core_completeness_response(report)


@router.post("/tushare/repair", response_model=DataRepairResponse)
def repair_tushare_core_data(
    session: Annotated[Session, Depends(get_db_session)],
    start_date: date,
    end_date: date,
    dry_run: bool = True,
) -> DataRepairResponse:
    result = CoreMarketDataRepairService(session).repair(
        start_date=start_date,
        end_date=end_date,
        dry_run=dry_run,
    )
    return _repair_response(result)


@router.post("/tushare/backfill-batches/fix", response_model=BackfillBatchFixResponse)
def fix_tushare_backfill_batches(
    session: Annotated[Session, Depends(get_db_session)],
    start_date: date,
    end_date: date,
    dry_run: bool = True,
    stale_after_minutes: int = 180,
) -> BackfillBatchFixResponse:
    result = CoreMarketDataRepairService(session).fix_backfill_batches(
        start_date=start_date,
        end_date=end_date,
        dry_run=dry_run,
        stale_after_minutes=stale_after_minutes,
    )
    return BackfillBatchFixResponse(
        scanned_batches=result.scanned_batches,
        fixed_batches=result.fixed_batches,
        still_failed_batches=result.still_failed_batches,
        stale_running_batches=result.stale_running_batches,
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


def _core_completeness_response(report: CoreMarketCompletenessReport) -> CoreCompletenessResponse:
    return CoreCompletenessResponse(
        layer=report.layer,
        exchange=report.exchange,
        start_date=report.start_date,
        end_date=report.end_date,
        total_missing_trade_days=report.total_missing_trade_days,
        tables=[
            TableCompletenessResponse(
                api_name=table.api_name,
                table_name=table.table_name,
                expected_trade_days=table.expected_trade_days,
                present_trade_days=table.present_trade_days,
                missing_trade_days=table.missing_trade_days,
                latest_present_date=table.latest_present_date,
                completeness_ratio=table.completeness_ratio,
                missing_dates=table.missing_dates,
                repair_ranges=[
                    MissingDateRangeResponse(
                        start_date=repair_range.start_date,
                        end_date=repair_range.end_date,
                        days=repair_range.days,
                    )
                    for repair_range in table.repair_ranges[:10]
                ],
            )
            for table in report.tables
        ],
    )


def _backfill_job_response(session: Session, job: BackfillJob) -> BackfillJobResponse:
    sorted_batches = sorted(job.batches, key=lambda item: item.batch_index, reverse=True)
    recent_batches = [_backfill_batch_response(batch) for batch in sorted_batches[:5]]
    latest_batch = recent_batches[0] if recent_batches else None
    remaining_trade_days = _remaining_trade_days(session, job.cursor_date, job.end_date)
    batch_size = latest_batch.trade_days if latest_batch and latest_batch.trade_days > 0 else None
    estimated_remaining_batches = (
        _ceil_div(remaining_trade_days, batch_size)
        if remaining_trade_days is not None and batch_size is not None
        else None
    )
    return BackfillJobResponse(
        id=job.id,
        name=job.name,
        task_type=job.task_type,
        status=job.status,
        start_date=job.start_date,
        end_date=job.end_date,
        cursor_date=job.cursor_date,
        total_batches=job.total_batches,
        succeeded_batches=job.succeeded_batches,
        failed_batches=job.failed_batches,
        blocked_batches=job.blocked_batches,
        total_windows=job.total_windows,
        rows_fetched=job.rows_fetched,
        rows_upserted=job.rows_upserted,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=_compact_message(job.error_message),
        recent_batches=recent_batches,
        is_running=job.status == BACKFILL_RUNNING_STATUS,
        remaining_trade_days=remaining_trade_days,
        estimated_remaining_batches=estimated_remaining_batches,
        latest_batch=latest_batch,
    )


def _backfill_batch_response(batch: BackfillBatch) -> BackfillBatchResponse:
    return BackfillBatchResponse(
        batch_index=batch.batch_index,
        status=batch.status,
        cursor_date=batch.cursor_date,
        start_date=batch.start_date,
        end_date=batch.end_date,
        trade_days=batch.trade_days,
        windows=batch.windows,
        rows_fetched=batch.rows_fetched,
        rows_upserted=batch.rows_upserted,
        started_at=batch.started_at,
        finished_at=batch.finished_at,
        error_message=_compact_message(batch.error_message),
    )


def _repair_response(result: DataRepairResult) -> DataRepairResponse:
    return DataRepairResponse(
        start_date=result.plan.start_date,
        end_date=result.plan.end_date,
        missing_trade_days=result.plan.missing_trade_days,
        repair_ranges=[
            RepairRangeResponse(start_date=range_start, end_date=range_end, days=days)
            for range_start, range_end, days in result.plan.repair_ranges[:20]
        ],
        executed=result.executed,
        daily_quotes=result.daily_quotes,
        daily_indicators=result.daily_indicators,
        adj_factors=result.adj_factors,
    )


def _compact_message(value: str | None, *, max_length: int = 240) -> str | None:
    if value is None:
        return None
    message = value.strip().splitlines()[0]
    if len(message) <= max_length:
        return message
    return f"{message[:max_length]}..."


def _default_completeness_start_date() -> date:
    return date.today() - timedelta(days=450)


def _remaining_trade_days(
    session: Session,
    cursor_date: date | None,
    end_date: date | None,
) -> int | None:
    if cursor_date is None or end_date is None:
        return None
    value = session.execute(
        text(
            """
            SELECT count(*)
            FROM app.trade_calendars
            WHERE exchange = 'SSE'
              AND is_open = true
              AND cal_date > :cursor_date
              AND cal_date <= :end_date
            """
        ),
        {"cursor_date": cursor_date, "end_date": end_date},
    ).scalar_one()
    return int(value)


def _ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor

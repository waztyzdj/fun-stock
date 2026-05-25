from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date
from typing import Any, ParamSpec, TypeVar

from celery.utils.log import get_task_logger
from redis import Redis

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.engines.data_sync.tushare.scheduler import (
    DEFAULT_TS_CODE,
    TushareSchedulerRunResult,
    TushareSyncScheduler,
)
from app.repositories.data_sync import DataSyncRepository
from app.services.distributed_lock import RedisDistributedLock
from app.tasks.sync_tushare_scheduler import PROVIDER

logger = get_task_logger(__name__)
P = ParamSpec("P")
R = TypeVar("R")


def celery_task(*, name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        celery_app.task(name=name)(func)
        return func

    return decorator


@celery_task(name="app.tasks.tushare_celery.sync_tushare_due_small_batch")
def sync_tushare_due_small_batch() -> dict[str, Any]:
    settings = get_settings()
    api_names = _configured_api_names(settings.tushare_scheduler_api_names)
    with _tushare_sync_lock("due-small-batch") as acquired:
        if not acquired:
            logger.info("Skip Tushare sync because the distributed lock is already held.")
            return {"status": "skipped_locked"}

        with SessionLocal() as session:
            result = TushareSyncScheduler(session, ts_code=DEFAULT_TS_CODE).run_once(
                run_date=date.today(),
                max_items=settings.tushare_scheduler_max_items,
                continue_on_error=True,
                include_manual=False,
                api_names=api_names,
            )
        payload = _scheduler_result_payload(result)
        logger.info("Tushare scheduled sync finished: %s", payload)
        return payload


@celery_task(name="app.tasks.tushare_celery.retry_tushare_failed")
def retry_tushare_failed() -> dict[str, Any]:
    settings = get_settings()
    with _tushare_sync_lock("retry-failed") as acquired:
        if not acquired:
            logger.info("Skip Tushare retry because the distributed lock is already held.")
            return {"status": "skipped_locked"}

        with SessionLocal() as session:
            repository = DataSyncRepository(session)
            jobs = repository.list_retryable_failed_jobs(
                provider=PROVIDER,
                api_names=sorted(_configured_api_names(settings.tushare_scheduler_api_names)),
                limit=settings.tushare_scheduler_max_items,
            )
            api_names = {job.api_name for job in jobs}
            if not api_names:
                logger.info("No retryable failed Tushare jobs found.")
                return {"status": "no_retryable_failed_jobs"}

            result = TushareSyncScheduler(session, ts_code=DEFAULT_TS_CODE).run_once(
                run_date=date.today(),
                max_items=settings.tushare_scheduler_max_items,
                continue_on_error=True,
                include_manual=True,
                api_names=api_names,
                force_selected=True,
            )
        payload = _scheduler_result_payload(result)
        logger.info("Tushare retry finished: %s", payload)
        return payload


@celery_task(name="app.tasks.tushare_celery.log_tushare_alert_snapshot")
def log_tushare_alert_snapshot() -> dict[str, Any]:
    settings = get_settings()
    with SessionLocal() as session:
        repository = DataSyncRepository(session)
        problem_runs = repository.list_recent_problem_runs(
            provider=PROVIDER,
            limit=settings.tushare_scheduler_alert_limit,
        )
        blocked_jobs = repository.list_blocked_jobs(
            provider=PROVIDER,
            limit=settings.tushare_scheduler_alert_limit,
        )
        quality_alerts = repository.list_recent_quality_alerts(
            provider=PROVIDER,
            limit=settings.tushare_scheduler_alert_limit,
        )

    payload = {
        "status": "success",
        "problem_runs": len(problem_runs),
        "blocked_jobs": len(blocked_jobs),
        "quality_alerts": len(quality_alerts),
    }
    logger.warning("Tushare alert snapshot: %s", payload)
    return payload


def _configured_api_names(raw_value: str) -> set[str]:
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def _scheduler_result_payload(result: TushareSchedulerRunResult) -> dict[str, Any]:
    return {
        "status": "success",
        "success": result.successes,
        "failed": result.failures,
        "blocked": result.blocked,
        "skipped": result.skipped,
        "rows_fetched": result.rows_fetched,
        "rows_upserted": result.rows_upserted,
    }


def _tushare_sync_lock(name: str) -> AbstractContextManager[bool]:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    lock = RedisDistributedLock(client)
    return lock.acquire(name, ttl_seconds=settings.tushare_scheduler_lock_ttl_seconds)

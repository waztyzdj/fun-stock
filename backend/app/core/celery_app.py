from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "fun_stock",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
    include=["app.tasks.tushare_celery"],
)

celery_app.conf.update(
    timezone=settings.timezone,
    enable_utc=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=60 * 60,
    task_soft_time_limit=55 * 60,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "tushare-daily-small-batch": {
            "task": "app.tasks.tushare_celery.sync_tushare_due_small_batch",
            "schedule": crontab(hour=20, minute=0),
        },
        "tushare-weekly-small-batch": {
            "task": "app.tasks.tushare_celery.sync_tushare_due_small_batch",
            "schedule": crontab(hour=21, minute=0, day_of_week="sat"),
        },
        "tushare-retry-failed": {
            "task": "app.tasks.tushare_celery.retry_tushare_failed",
            "schedule": crontab(hour=20, minute=40),
        },
        "tushare-alert-snapshot": {
            "task": "app.tasks.tushare_celery.log_tushare_alert_snapshot",
            "schedule": crontab(hour=21, minute=20),
        },
    },
)

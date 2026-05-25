from app.models.data_sync import DataSyncJob
from app.repositories.data_sync import is_retryable_sync_job


def test_retryable_sync_job_excludes_insufficient_points_blocked_status() -> None:
    failed_job = DataSyncJob(provider="tushare", api_name="daily", sync_mode="daily")
    failed_job.status = "failed"
    blocked_job = DataSyncJob(provider="tushare", api_name="income", sync_mode="weekly")
    blocked_job.status = "blocked_insufficient_points"

    assert is_retryable_sync_job(failed_job)
    assert not is_retryable_sync_job(blocked_job)

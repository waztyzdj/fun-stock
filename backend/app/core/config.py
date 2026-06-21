from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fun Stock API"
    app_env: str = "local"
    debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+psycopg://fun_stock:fun_stock@postgres:5432/fun_stock"
    )
    redis_url: str = "redis://localhost:6380/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    timezone: str = "Asia/Shanghai"
    tushare_token: str | None = None
    tushare_scheduler_api_names: str = (
        "stock_basic,trade_cal,daily,daily_basic,adj_factor,index_daily"
    )
    tushare_scheduler_max_items: int = 5
    tushare_scheduler_alert_limit: int = 20
    tushare_scheduler_lock_ttl_seconds: int = 3600
    tushare_startup_catchup_enabled: bool = True
    tushare_startup_retry_failed_enabled: bool = True
    tushare_rate_limit_sleep_seconds: float = 20
    tushare_rate_limit_max_retries: int = 3
    tushare_network_retry_sleep_seconds: float = 60
    tushare_network_max_retries: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from sqlalchemy import Date, MetaData, Table, bindparam, func, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

POSTGRES_MAX_BIND_PARAMETERS = 65535
SAFE_MAX_BIND_PARAMETERS = 60000


class TushareRawRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.metadata = MetaData(schema="tushare")

    def upsert(self, table_name: str, records: Sequence[dict[str, Any]]) -> int:
        if not records:
            return 0

        table = self._table(table_name)
        primary_keys = [column.name for column in table.primary_key.columns]
        if not primary_keys:
            msg = f"tushare.{table_name} must have a primary key for idempotent ingestion."
            raise ValueError(msg)

        allowed_columns = {column.name for column in table.columns}
        date_columns = {
            column.name for column in table.columns if isinstance(column.type, Date)
        }
        normalized_records = [
            self._normalize_record(
                record,
                allowed_columns=allowed_columns,
                date_columns=date_columns,
            )
            for record in records
        ]
        normalized_records = [record for record in normalized_records if record]
        normalized_records = self._deduplicate_records(
            normalized_records,
            key_columns=primary_keys,
        )
        if not normalized_records:
            return 0

        rows_upserted = 0
        batch_size = self._batch_size(normalized_records)
        for start in range(0, len(normalized_records), batch_size):
            rows_upserted += self._upsert_batch(
                table=table,
                primary_keys=primary_keys,
                records=normalized_records[start : start + batch_size],
            )
        return rows_upserted

    def _upsert_batch(
        self,
        *,
        table: Table,
        primary_keys: list[str],
        records: Sequence[dict[str, Any]],
    ) -> int:
        statement = insert(table).values(records)
        update_columns: dict[str, object] = {
            column.name: statement.excluded[column.name]
            for column in table.columns
            if column.name not in primary_keys and column.name in records[0]
        }
        if "ingested_at" in table.c:
            update_columns["ingested_at"] = func.now()

        statement = statement.on_conflict_do_update(
            index_elements=[table.c[key] for key in primary_keys],
            set_=update_columns,
        )
        self.session.execute(statement)
        return len(records)

    def get_open_trade_dates_after(
        self,
        *,
        exchange: str,
        after_date: date,
        end_date: date,
    ) -> list[date]:
        table = self._table("trade_cal")
        result = self.session.execute(
            table.select()
            .with_only_columns(table.c.cal_date)
            .where(
                table.c.exchange == bindparam("exchange"),
                table.c.is_open == "1",
                table.c.cal_date > bindparam("after_date"),
                table.c.cal_date <= bindparam("end_date"),
            )
            .order_by(table.c.cal_date),
            {"exchange": exchange, "after_date": after_date, "end_date": end_date},
        )
        return [row[0] for row in result.all()]

    def _table(self, table_name: str) -> Table:
        return Table(table_name, self.metadata, autoload_with=self.session.bind)

    @staticmethod
    def _normalize_record(
        record: dict[str, Any],
        *,
        allowed_columns: Iterable[str],
        date_columns: Iterable[str] = (),
    ) -> dict[str, Any]:
        allowed = set(allowed_columns)
        date_column_names = set(date_columns)
        return {
            key: TushareRawRepository._normalize_value(
                value,
                is_date=key in date_column_names,
            )
            for key, value in record.items()
            if key in allowed
        }

    @staticmethod
    def _normalize_value(value: Any, *, is_date: bool = False) -> Any:
        if value == "":
            return None
        if is_date and value in {"0", "00000000", 0}:
            return None
        return value

    @staticmethod
    def _batch_size(records: Sequence[dict[str, Any]]) -> int:
        if not records:
            return 1
        parameter_count_per_row = max(len(record) for record in records)
        if parameter_count_per_row <= 0:
            return 1
        return max(1, min(len(records), SAFE_MAX_BIND_PARAMETERS // parameter_count_per_row))

    @staticmethod
    def _deduplicate_records(
        records: Sequence[dict[str, Any]],
        *,
        key_columns: Sequence[str],
    ) -> list[dict[str, Any]]:
        deduplicated: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in records:
            key = tuple(record.get(column) for column in key_columns)
            deduplicated[key] = record
        return list(deduplicated.values())

    def ensure_tables_exist(self, table_names: Sequence[str]) -> None:
        bind = self.session.get_bind()
        if not isinstance(bind, Engine | Connection):
            msg = "A SQLAlchemy engine or connection is required to inspect raw Tushare tables."
            raise RuntimeError(msg)
        inspector = inspect(bind)
        existing_tables = set(inspector.get_table_names(schema="tushare"))
        missing_tables = [
            table_name for table_name in table_names if table_name not in existing_tables
        ]
        if missing_tables:
            joined = ", ".join(f"tushare.{table_name}" for table_name in missing_tables)
            msg = f"Missing raw Tushare tables: {joined}. Run infra/postgres/init bootstrap first."
            raise RuntimeError(msg)

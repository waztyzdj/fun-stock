from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, bindparam, select, text
from sqlalchemy.orm import Session

from app.engines.factor.fundamental_factors import FUNDAMENTAL_FACTOR_SPECS
from app.models.factor import FactorDefinition, StrategyDefinition, StrategyVersion


@dataclass(frozen=True)
class FactorValueSnapshot:
    factor_code: str
    value: Decimal
    factor_date: date
    report_end_date: date | None = None


@dataclass(frozen=True)
class FactorValueTrendPoint:
    factor_code: str
    value: Decimal
    factor_date: date
    report_end_date: date | None


@dataclass(frozen=True)
class FactorCoverage:
    factor_code: str
    value_count: int
    stock_count: int
    latest_factor_date: date | None
    latest_report_end_date: date | None
    latest_value_count: int


@dataclass(frozen=True)
class FactorBuildStatus:
    total_value_count: int
    factor_count: int
    stock_count: int
    latest_factor_date: date | None
    latest_report_end_date: date | None
    latest_updated_at: datetime | None


@dataclass(frozen=True)
class FactorQuality:
    factor_code: str
    factor_name: str
    category: str
    status: str
    value_count: int
    stock_count: int
    latest_factor_date: date | None
    latest_value_count: int
    universe_stock_count: int
    coverage_ratio: Decimal
    missing_stock_count: int
    zero_value_count: int
    negative_value_count: int


@dataclass(frozen=True)
class StrategyListItem:
    id: int
    name: str
    description: str | None
    status: str


@dataclass(frozen=True)
class StrategyDetail:
    id: int
    name: str
    description: str | None
    status: str
    strategy_json: dict[str, object]


class FactorRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_factor_definitions(self) -> int:
        changed = 0
        for spec in FUNDAMENTAL_FACTOR_SPECS:
            definition = self.session.get(FactorDefinition, spec.code)
            if definition is None:
                definition = FactorDefinition(
                    code=spec.code,
                    name=spec.name,
                    category=spec.category,
                    unit=spec.unit,
                    period_type=spec.period_type,
                    source=f"tushare.{spec.source_table}.{spec.source_column}",
                    calculation_method=spec.calculation_method,
                    description=spec.description,
                    sort_direction=spec.sort_direction,
                    is_active=True,
                )
                self.session.add(definition)
            else:
                definition.name = spec.name
                definition.category = spec.category
                definition.unit = spec.unit
                definition.period_type = spec.period_type
                definition.source = f"tushare.{spec.source_table}.{spec.source_column}"
                definition.calculation_method = spec.calculation_method
                definition.description = spec.description
                definition.sort_direction = spec.sort_direction
                definition.is_active = True
            changed += 1
        self.session.flush()
        return changed

    def list_factor_definitions(self) -> list[FactorDefinition]:
        return list(
            self.session.scalars(
                select(FactorDefinition)
                .where(FactorDefinition.is_active.is_(True))
                .order_by(FactorDefinition.category, FactorDefinition.code)
            )
        )

    def factor_coverages(self) -> dict[str, FactorCoverage]:
        rows = self.session.execute(
            text(
                """
                WITH summary AS (
                    SELECT
                        factor_code,
                        count(*) AS value_count,
                        count(DISTINCT ts_code) AS stock_count,
                        max(factor_date) AS latest_factor_date,
                        max(report_end_date) AS latest_report_end_date
                    FROM app.factor_values
                    GROUP BY factor_code
                ),
                latest_values AS (
                    SELECT fv.factor_code, count(*) AS latest_value_count
                    FROM app.factor_values fv
                    JOIN summary s
                      ON s.factor_code = fv.factor_code
                     AND s.latest_factor_date = fv.factor_date
                    GROUP BY fv.factor_code
                )
                SELECT
                    s.factor_code,
                    s.value_count,
                    s.stock_count,
                    s.latest_factor_date,
                    s.latest_report_end_date,
                    COALESCE(l.latest_value_count, 0) AS latest_value_count
                FROM summary s
                LEFT JOIN latest_values l ON l.factor_code = s.factor_code
                """
            )
        ).all()
        return {
            row.factor_code: FactorCoverage(
                factor_code=row.factor_code,
                value_count=int(row.value_count),
                stock_count=int(row.stock_count),
                latest_factor_date=row.latest_factor_date,
                latest_report_end_date=row.latest_report_end_date,
                latest_value_count=int(row.latest_value_count),
            )
            for row in rows
        }

    def factor_build_status(self) -> FactorBuildStatus:
        row = self.session.execute(
            text(
                """
                SELECT
                    count(*) AS total_value_count,
                    count(DISTINCT factor_code) AS factor_count,
                    count(DISTINCT ts_code) AS stock_count,
                    max(factor_date) AS latest_factor_date,
                    max(report_end_date) AS latest_report_end_date,
                    max(updated_at) AS latest_updated_at
                FROM app.factor_values
                """
            )
        ).one()
        return FactorBuildStatus(
            total_value_count=int(row.total_value_count),
            factor_count=int(row.factor_count),
            stock_count=int(row.stock_count),
            latest_factor_date=row.latest_factor_date,
            latest_report_end_date=row.latest_report_end_date,
            latest_updated_at=row.latest_updated_at,
        )

    def factor_quality_report(self) -> list[FactorQuality]:
        self.upsert_factor_definitions()
        active_stock_count = self._active_stock_count()
        coverages = self.factor_coverages()
        value_stats = self._factor_value_stats()
        qualities: list[FactorQuality] = []
        for definition in self.list_factor_definitions():
            coverage = coverages.get(definition.code)
            stats = value_stats.get(definition.code, {"zero": 0, "negative": 0})
            stock_count = coverage.stock_count if coverage else 0
            coverage_ratio = (
                Decimal(stock_count) / Decimal(active_stock_count)
                if active_stock_count > 0
                else Decimal("0")
            )
            missing_stock_count = max(active_stock_count - stock_count, 0)
            qualities.append(
                FactorQuality(
                    factor_code=definition.code,
                    factor_name=definition.name,
                    category=definition.category,
                    status=_factor_quality_status(
                        stock_count=stock_count,
                        coverage_ratio=coverage_ratio,
                        latest_factor_date=coverage.latest_factor_date if coverage else None,
                    ),
                    value_count=coverage.value_count if coverage else 0,
                    stock_count=stock_count,
                    latest_factor_date=coverage.latest_factor_date if coverage else None,
                    latest_value_count=coverage.latest_value_count if coverage else 0,
                    universe_stock_count=active_stock_count,
                    coverage_ratio=coverage_ratio,
                    missing_stock_count=missing_stock_count,
                    zero_value_count=int(stats["zero"]),
                    negative_value_count=int(stats["negative"]),
                )
            )
        return qualities

    def rebuild_factor_values(self, *, start_date: date | None = None) -> int:
        self.upsert_factor_definitions()
        rows = 0
        for spec in FUNDAMENTAL_FACTOR_SPECS:
            rows += self._rebuild_factor_value(spec_code=spec.code, start_date=start_date)
        return rows

    def latest_factor_date(self) -> date | None:
        return self.session.execute(
            text("SELECT max(factor_date) FROM app.factor_values")
        ).scalar_one_or_none()

    def latest_factor_snapshots(
        self,
        *,
        ts_code: str,
        factor_codes: list[str],
        as_of_date: date | None = None,
    ) -> list[FactorValueSnapshot]:
        if not factor_codes:
            return []
        conditions = ["ts_code = :ts_code", "factor_code = ANY(:factor_codes)"]
        if as_of_date is not None:
            conditions.append("factor_date <= :as_of_date")
        where_clause = "\n                      AND ".join(conditions)
        rows = self.session.execute(
            text(
                f"""
                WITH ranked_values AS (
                    SELECT
                        factor_code,
                        value,
                        factor_date,
                        report_end_date,
                        row_number() OVER (
                            PARTITION BY factor_code
                            ORDER BY factor_date DESC
                        ) AS row_number
                    FROM app.factor_values
                    WHERE {where_clause}
                )
                SELECT factor_code, value, factor_date, report_end_date
                FROM ranked_values
                WHERE row_number = 1
                ORDER BY factor_code
                """
            ).bindparams(bindparam("factor_codes", expanding=False)),
            {
                "ts_code": ts_code,
                "factor_codes": factor_codes,
                "as_of_date": as_of_date,
            },
        ).all()
        return [
            FactorValueSnapshot(
                factor_code=row.factor_code,
                value=row.value,
                factor_date=row.factor_date,
                report_end_date=row.report_end_date,
            )
            for row in rows
        ]

    def factor_value_history(
        self,
        *,
        ts_code: str,
        factor_codes: list[str],
        limit_per_factor: int = 12,
    ) -> list[FactorValueTrendPoint]:
        if not factor_codes:
            return []
        rows = self.session.execute(
            text(
                """
                WITH ranked_values AS (
                    SELECT
                        factor_code,
                        value,
                        factor_date,
                        report_end_date,
                        row_number() OVER (
                            PARTITION BY factor_code
                            ORDER BY factor_date DESC
                        ) AS row_number
                    FROM app.factor_values
                    WHERE ts_code = :ts_code
                      AND factor_code = ANY(:factor_codes)
                )
                SELECT factor_code, value, factor_date, report_end_date
                FROM ranked_values
                WHERE row_number <= :limit_per_factor
                ORDER BY factor_code, factor_date
                """
            ).bindparams(bindparam("factor_codes", expanding=False)),
            {
                "ts_code": ts_code,
                "factor_codes": factor_codes,
                "limit_per_factor": limit_per_factor,
            },
        ).all()
        return [
            FactorValueTrendPoint(
                factor_code=row.factor_code,
                value=row.value,
                factor_date=row.factor_date,
                report_end_date=row.report_end_date,
            )
            for row in rows
        ]

    def save_strategy(
        self,
        *,
        name: str,
        description: str | None,
        strategy_json: dict[str, object],
    ) -> StrategyDefinition:
        strategy = StrategyDefinition(
            name=name,
            description=description,
            strategy_json=strategy_json,
            status="draft",
        )
        self.session.add(strategy)
        self.session.flush()
        self.session.add(
            StrategyVersion(
                strategy_id=strategy.id,
                version_no=1,
                strategy_json=strategy_json,
                notes="Initial draft version.",
            )
        )
        self.session.flush()
        return strategy

    def list_strategies(self, *, limit: int = 20) -> list[StrategyListItem]:
        strategies = self.session.scalars(
            select(StrategyDefinition)
            .order_by(StrategyDefinition.updated_at.desc(), StrategyDefinition.id.desc())
            .limit(limit)
        )
        return [
            StrategyListItem(
                id=strategy.id,
                name=strategy.name,
                description=strategy.description,
                status=strategy.status,
            )
            for strategy in strategies
        ]

    def get_strategy(self, strategy_id: int) -> StrategyDetail | None:
        strategy = self.session.get(StrategyDefinition, strategy_id)
        if strategy is None:
            return None
        return StrategyDetail(
            id=strategy.id,
            name=strategy.name,
            description=strategy.description,
            status=strategy.status,
            strategy_json=strategy.strategy_json,
        )

    def _rebuild_factor_value(self, *, spec_code: str, start_date: date | None) -> int:
        spec = next(item for item in FUNDAMENTAL_FACTOR_SPECS if item.code == spec_code)
        if spec.source_table == "fina_indicator":
            return self._upsert_fina_indicator_factor(
                factor_code=spec.code,
                source_column=spec.source_column,
                start_date=start_date,
            )
        if spec.source_table == "daily_basic":
            return self._upsert_daily_basic_factor(
                factor_code=spec.code,
                source_column=spec.source_column,
                start_date=start_date,
            )
        raise ValueError(f"Unsupported factor source table: {spec.source_table}")

    def _upsert_fina_indicator_factor(
        self,
        *,
        factor_code: str,
        source_column: str,
        start_date: date | None,
    ) -> int:
        result = self.session.execute(
            text(
                f"""
                INSERT INTO app.factor_values (
                    factor_code,
                    ts_code,
                    factor_date,
                    report_end_date,
                    value,
                    period_type,
                    ann_date,
                    source_table,
                    updated_at
                )
                SELECT
                    :factor_code,
                    ts_code,
                    COALESCE(ann_date, end_date),
                    end_date,
                    {source_column},
                    'report',
                    ann_date,
                    'tushare.fina_indicator',
                    now()
                FROM tushare.fina_indicator
                WHERE ts_code IS NOT NULL
                  AND end_date IS NOT NULL
                  AND {source_column} IS NOT NULL
                  AND (:start_date IS NULL OR end_date >= :start_date)
                ON CONFLICT (factor_code, ts_code, factor_date) DO UPDATE SET
                    value = EXCLUDED.value,
                    period_type = EXCLUDED.period_type,
                    ann_date = EXCLUDED.ann_date,
                    report_end_date = EXCLUDED.report_end_date,
                    source_table = EXCLUDED.source_table,
                    updated_at = now()
                """
            ).bindparams(bindparam("start_date", type_=Date)),
            {"factor_code": factor_code, "start_date": start_date},
        )
        rowcount = getattr(result, "rowcount", -1)
        return rowcount if rowcount != -1 else 0

    def _upsert_daily_basic_factor(
        self,
        *,
        factor_code: str,
        source_column: str,
        start_date: date | None,
    ) -> int:
        result = self.session.execute(
            text(
                f"""
                INSERT INTO app.factor_values (
                    factor_code,
                    ts_code,
                    factor_date,
                    report_end_date,
                    value,
                    period_type,
                    ann_date,
                    source_table,
                    updated_at
                )
                SELECT
                    :factor_code,
                    ts_code,
                    trade_date,
                    NULL,
                    {source_column},
                    'daily',
                    NULL,
                    'tushare.daily_basic',
                    now()
                FROM app.daily_indicators
                WHERE ts_code IS NOT NULL
                  AND trade_date IS NOT NULL
                  AND {source_column} IS NOT NULL
                  AND (:start_date IS NULL OR trade_date >= :start_date)
                ON CONFLICT (factor_code, ts_code, factor_date) DO UPDATE SET
                    value = EXCLUDED.value,
                    period_type = EXCLUDED.period_type,
                    ann_date = EXCLUDED.ann_date,
                    report_end_date = EXCLUDED.report_end_date,
                    source_table = EXCLUDED.source_table,
                    updated_at = now()
                """
            ).bindparams(bindparam("start_date", type_=Date)),
            {"factor_code": factor_code, "start_date": start_date},
        )
        rowcount = getattr(result, "rowcount", -1)
        return rowcount if rowcount != -1 else 0

    def _active_stock_count(self) -> int:
        count = self.session.execute(
            text(
                """
                SELECT count(*)
                FROM app.stocks
                WHERE list_status = 'L' OR list_status IS NULL
                """
            )
        ).scalar_one()
        return int(count)

    def _factor_value_stats(self) -> dict[str, dict[str, int]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    factor_code,
                    count(*) FILTER (WHERE value = 0) AS zero_value_count,
                    count(*) FILTER (WHERE value < 0) AS negative_value_count
                FROM app.factor_values
                GROUP BY factor_code
                """
            )
        ).all()
        return {
            row.factor_code: {
                "zero": int(row.zero_value_count),
                "negative": int(row.negative_value_count),
            }
            for row in rows
        }


def _factor_quality_status(
    *,
    stock_count: int,
    coverage_ratio: Decimal,
    latest_factor_date: date | None,
) -> str:
    if stock_count == 0 or latest_factor_date is None:
        return "empty"
    if coverage_ratio < Decimal("0.5"):
        return "warning"
    return "ready"

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class FactorDefinition(Base):
    __tablename__ = "factor_definitions"
    __table_args__ = (
        Index("ix_factor_definitions_category", "category"),
        {"schema": "app"},
    )

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    period_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    calculation_method: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_direction: Mapped[str] = mapped_column(String(8), nullable=False, default="desc")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    values: Mapped[list["FactorValue"]] = relationship(back_populates="definition")


class FactorValue(Base):
    __tablename__ = "factor_values"
    __table_args__ = (
        UniqueConstraint(
            "factor_code",
            "ts_code",
            "factor_date",
            name="uq_factor_values_factor_stock_date",
        ),
        Index("ix_factor_values_factor_code_date", "factor_code", "factor_date"),
        Index("ix_factor_values_ts_code_date", "ts_code", "factor_date"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    factor_code: Mapped[str] = mapped_column(
        ForeignKey("app.factor_definitions.code"), nullable=False
    )
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    factor_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_end_date: Mapped[date | None] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ann_date: Mapped[date | None] = mapped_column(Date)
    source_table: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    definition: Mapped[FactorDefinition] = relationship(back_populates="values")


class StrategyDefinition(Base):
    __tablename__ = "strategy_definitions"
    __table_args__ = (
        Index("ix_strategy_definitions_status", "status"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    strategy_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["StrategyVersion"]] = relationship(back_populates="strategy")


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (
        UniqueConstraint("strategy_id", "version_no", name="uq_strategy_versions_strategy_version"),
        Index("ix_strategy_versions_strategy_id", "strategy_id"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("app.strategy_definitions.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(nullable=False)
    strategy_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    strategy: Mapped[StrategyDefinition] = relationship(back_populates="versions")

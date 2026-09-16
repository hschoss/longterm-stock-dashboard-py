"""SQLAlchemy-Tabellendefinitionen. Einzige Stelle mit SQL/ORM-Zugriff (siehe
CLAUDE.md: 'SQL gibt es nur in storage/'). Schema laut docs/plan.md Abschnitt 3.
Schemaaenderungen ausschliesslich ueber Alembic-Migrationen
(storage/migrations/versions/)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Double,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Asset(Base):
    """ref.assets — aus config/assets.yaml synchronisiert."""

    __tablename__ = "assets"
    __table_args__ = {"schema": "ref"}

    asset_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    exchange_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    color: Mapped[str | None] = mapped_column(String(16))
    region: Mapped[str | None] = mapped_column(String(64))
    map_label: Mapped[str | None] = mapped_column(String(64))
    lat: Mapped[float | None] = mapped_column(Double)
    lon: Mapped[float | None] = mapped_column(Double)
    card_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class IndexCountryExposure(Base):
    """ref.index_country_exposure — Ablosung der aggregated/*_country_counts.csv
    (siehe docs/plan.md Abschnitt 3). Wird per Migrationsskript befuellt, solange die
    Quelle CSV-Dateien sind."""

    __tablename__ = "index_country_exposure"
    __table_args__ = (
        UniqueConstraint("index_asset_id", "as_of_date", "iso_alpha3", name="uq_index_country_exposure"),
        {"schema": "ref"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    index_asset_id: Mapped[int] = mapped_column(ForeignKey("ref.assets.asset_id"), nullable=False)
    as_of_date: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=False), nullable=False)
    country: Mapped[str | None] = mapped_column(String(128))
    iso_alpha3: Mapped[str] = mapped_column(String(3), nullable=False)
    company_count: Mapped[int | None] = mapped_column(Integer)
    security_count: Mapped[int | None] = mapped_column(Integer)
    total_weight_pct: Mapped[float | None] = mapped_column(Double)
    tax_residence_country: Mapped[str | None] = mapped_column(String(128))
    tax_residence_iso_alpha3: Mapped[str | None] = mapped_column(String(3))


class Price(Base):
    """market.prices — kanonische Kursreihe je Asset und Frequenz."""

    __tablename__ = "prices"
    __table_args__ = {"schema": "market"}

    asset_id: Mapped[int] = mapped_column(ForeignKey("ref.assets.asset_id"), primary_key=True)
    frequency: Mapped[str] = mapped_column(String(16), primary_key=True)
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    open: Mapped[float | None] = mapped_column(Numeric(18, 6))
    high: Mapped[float | None] = mapped_column(Numeric(18, 6))
    low: Mapped[float | None] = mapped_column(Numeric(18, 6))
    close: Mapped[float | None] = mapped_column(Numeric(18, 6))
    adj_close: Mapped[float | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    sync_run_id: Mapped[int | None] = mapped_column(ForeignKey("ops.job_runs.id"))


class Metric(Base):
    """analytics.metrics — vorberechnete Kennzahlen im Long-Format."""

    __tablename__ = "metrics"
    __table_args__ = {"schema": "analytics"}

    asset_id: Mapped[int] = mapped_column(ForeignKey("ref.assets.asset_id"), primary_key=True)
    frequency: Mapped[str] = mapped_column(String(16), primary_key=True)
    metric: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[str] = mapped_column(String(32), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    value: Mapped[float | None] = mapped_column(Double)
    job_run_id: Mapped[int | None] = mapped_column(ForeignKey("ops.job_runs.id"))


class JobRun(Base):
    """ops.job_runs — ein Eintrag je Batch-Lauf (sync/analytics/forecast/nightly/...)."""

    __tablename__ = "job_runs"
    __table_args__ = {"schema": "ops"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)


class JobRunItem(Base):
    """ops.job_run_items — ein Eintrag je Schritt und Asset innerhalb eines Laufs."""

    __tablename__ = "job_run_items"
    __table_args__ = {"schema": "ops"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(ForeignKey("ops.job_runs.id"), nullable=False)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("ref.assets.asset_id"))
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class SyncState(Base):
    """ops.sync_state — Wasserzeichen je Quelltabelle (Phase 2)."""

    __tablename__ = "sync_state"
    __table_args__ = {"schema": "ops"}

    source_table: Mapped[str] = mapped_column(String(128), primary_key=True)
    watermark_ts: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_run_id: Mapped[int | None] = mapped_column(ForeignKey("ops.job_runs.id"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

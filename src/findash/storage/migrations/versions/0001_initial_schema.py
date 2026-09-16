"""Initiales Schema: ref, ops, staging (leer), market, analytics.

Revision ID: 0001
Revises:
Create Date: 2026-09-16

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("ref", "staging", "market", "analytics", "ops")


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    op.create_table(
        "job_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("parameters", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        schema="ops",
    )

    op.create_table(
        "job_run_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_run_id", sa.BigInteger(), sa.ForeignKey("ops.job_runs.id"), nullable=False),
        sa.Column("asset_id", sa.BigInteger()),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("error", sa.Text()),
        schema="ops",
    )

    op.create_table(
        "sync_state",
        sa.Column("source_table", sa.String(128), primary_key=True),
        sa.Column("watermark_ts", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_run_id", sa.BigInteger(), sa.ForeignKey("ops.job_runs.id")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="ops",
    )

    op.create_table(
        "assets",
        sa.Column("asset_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("exchange_timezone", sa.String(64), nullable=False),
        sa.Column("source_key", sa.String(64)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("color", sa.String(16)),
        sa.Column("region", sa.String(64)),
        sa.Column("map_label", sa.String(64)),
        sa.Column("lat", sa.Double()),
        sa.Column("lon", sa.Double()),
        sa.Column("card_note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="ref",
    )

    op.create_table(
        "index_country_exposure",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("index_asset_id", sa.BigInteger(), sa.ForeignKey("ref.assets.asset_id"), nullable=False),
        sa.Column("as_of_date", sa.TIMESTAMP(timezone=False), nullable=False),
        sa.Column("country", sa.String(128)),
        sa.Column("iso_alpha3", sa.String(3), nullable=False),
        sa.Column("company_count", sa.Integer()),
        sa.Column("security_count", sa.Integer()),
        sa.Column("total_weight_pct", sa.Double()),
        sa.Column("tax_residence_country", sa.String(128)),
        sa.Column("tax_residence_iso_alpha3", sa.String(3)),
        sa.UniqueConstraint("index_asset_id", "as_of_date", "iso_alpha3", name="uq_index_country_exposure"),
        schema="ref",
    )

    op.create_table(
        "prices",
        sa.Column("asset_id", sa.BigInteger(), sa.ForeignKey("ref.assets.asset_id"), primary_key=True),
        sa.Column("frequency", sa.String(16), primary_key=True),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), primary_key=True),
        sa.Column("open", sa.Numeric(18, 6)),
        sa.Column("high", sa.Numeric(18, 6)),
        sa.Column("low", sa.Numeric(18, 6)),
        sa.Column("close", sa.Numeric(18, 6)),
        sa.Column("adj_close", sa.Numeric(18, 6)),
        sa.Column("volume", sa.BigInteger()),
        sa.Column("quality_status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("sync_run_id", sa.BigInteger(), sa.ForeignKey("ops.job_runs.id")),
        schema="market",
    )

    op.create_table(
        "metrics",
        sa.Column("asset_id", sa.BigInteger(), sa.ForeignKey("ref.assets.asset_id"), primary_key=True),
        sa.Column("frequency", sa.String(16), primary_key=True),
        sa.Column("metric", sa.String(64), primary_key=True),
        sa.Column("window", sa.String(32), primary_key=True),
        sa.Column("as_of", sa.TIMESTAMP(timezone=True), primary_key=True),
        sa.Column("value", sa.Double()),
        sa.Column("job_run_id", sa.BigInteger(), sa.ForeignKey("ops.job_runs.id")),
        schema="analytics",
    )


def downgrade() -> None:
    op.drop_table("metrics", schema="analytics")
    op.drop_table("prices", schema="market")
    op.drop_table("index_country_exposure", schema="ref")
    op.drop_table("assets", schema="ref")
    op.drop_table("sync_state", schema="ops")
    op.drop_table("job_run_items", schema="ops")
    op.drop_table("job_runs", schema="ops")
    for schema in SCHEMAS:
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")

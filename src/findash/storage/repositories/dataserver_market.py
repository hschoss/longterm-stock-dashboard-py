"""SELECT-only-Zugriffe auf das `derived.*`-Schema des externen `dataserver`.

Alle Funktionen liefern reine Python-Datenstrukturen (Listen von dataclasses / dicts),
niemals SQLAlchemy-ORM-Objekte. So bleibt `analytics/`/`app/` frei von Storage-Details.

Wenn `dataserver_url` nicht konfiguriert ist, geben die Funktionen leere Listen zurueck
und die Aufrufer koennen das per `dataserver_configured()` erkennen und die UI
sichtbar als "keine Verbindung" markieren (CLAUDE.md: fehlende Werte nie erfinden).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from findash.storage.dataserver import get_dataserver_engine


@dataclass(frozen=True)
class Instrument:
    target_index_id: str
    listing_variant: str
    source_symbol: str
    isin: str | None
    name: str | None
    issuer: str | None
    exchange_code: str | None
    exchange_timezone: str | None
    currency: str | None
    fund_base_currency: str | None
    domicile: str | None
    distribution_policy: str | None
    tracked_index: str | None
    instrument_type: str | None
    active_from: date | None
    active_to: date | None


@dataclass(frozen=True)
class PricePoint:
    trading_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    adjusted_close_provider: Decimal | None
    volume: int | None
    no_trading: bool
    revision_number: int | None
    currency: str | None


@dataclass(frozen=True)
class LatestPrice:
    target_index_id: str
    listing_variant: str
    source_symbol: str
    currency: str | None
    trading_date: date
    close: Decimal


@dataclass(frozen=True)
class CorporateAction:
    target_index_id: str
    listing_variant: str
    source_symbol: str
    action_date: date
    action_type: str
    value: Decimal
    currency: str | None


@dataclass(frozen=True)
class PipelineStatus:
    pipeline: str
    last_run_id: Any
    last_mode: str | None
    last_status: str | None
    last_started_at_utc: datetime | None
    last_finished_at_utc: datetime | None
    last_error: str | None
    last_success_at_utc: datetime | None
    last_failure_at_utc: datetime | None


@dataclass(frozen=True)
class DataFreshness:
    target_index_id: str
    listing_variant: str
    source_symbol: str
    last_trading_date: date | None
    trading_days: int | None
    first_trading_date: date | None


def dataserver_configured() -> bool:
    """`True`, wenn `dataserver_url` gesetzt ist und die Engine gebaut werden konnte."""

    return get_dataserver_engine() is not None


def _engine_or_none() -> Engine | None:
    return get_dataserver_engine()


def list_instruments() -> list[Instrument]:
    """Alle bekannten Instrumente aus `derived.v_instrument`.

    Leere Liste, falls der Dataserver nicht erreichbar/konfiguriert ist.
    """

    engine = _engine_or_none()
    if engine is None:
        return []
    stmt = text(
        """
        SELECT target_index_id, listing_variant, source_symbol, isin, name, issuer,
               exchange_code, exchange_timezone, currency, fund_base_currency,
               domicile, distribution_policy, tracked_index, instrument_type,
               active_from, active_to
        FROM derived.v_instrument
        ORDER BY target_index_id, listing_variant
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [Instrument(**dict(row)) for row in rows]


def latest_prices() -> list[LatestPrice]:
    """Letzter bekannter Handelstag je Instrument (nur `no_trading = false`)."""

    engine = _engine_or_none()
    if engine is None:
        return []
    stmt = text(
        """
        SELECT DISTINCT ON (target_index_id, listing_variant)
               target_index_id, listing_variant, source_symbol, currency,
               trading_date, close
        FROM derived.v_etf_daily_price_current
        WHERE NOT no_trading
        ORDER BY target_index_id, listing_variant, trading_date DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [LatestPrice(**dict(row)) for row in rows]


def price_history(
    target_index_id: str,
    listing_variant: str,
    since: date | None = None,
    include_no_trading: bool = False,
) -> list[PricePoint]:
    """Kurshistorie eines Instruments, aufsteigend nach `trading_date`."""

    engine = _engine_or_none()
    if engine is None:
        return []
    conditions = ["target_index_id = :tid", "listing_variant = :lv"]
    params: dict[str, Any] = {"tid": target_index_id, "lv": listing_variant}
    if not include_no_trading:
        conditions.append("NOT no_trading")
    if since is not None:
        conditions.append("trading_date >= :since")
        params["since"] = since
    where = " AND ".join(conditions)
    stmt = text(
        f"""
        SELECT trading_date, open, high, low, close, adjusted_close_provider,
               volume, no_trading, revision_number, currency
        FROM derived.v_etf_daily_price_current
        WHERE {where}
        ORDER BY trading_date
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt, params).mappings().all()
    return [PricePoint(**dict(row)) for row in rows]


def corporate_actions(
    target_index_id: str | None = None,
    listing_variant: str | None = None,
    action_type: str | None = None,
    limit: int = 200,
) -> list[CorporateAction]:
    """Corporate-Actions-Historie (Dividenden, Splits, Capital Gains)."""

    engine = _engine_or_none()
    if engine is None:
        return []
    conditions: list[str] = []
    params: dict[str, Any] = {"lim": int(limit)}
    if target_index_id is not None:
        conditions.append("target_index_id = :tid")
        params["tid"] = target_index_id
    if listing_variant is not None:
        conditions.append("listing_variant = :lv")
        params["lv"] = listing_variant
    if action_type is not None:
        conditions.append("action_type = :atype")
        params["atype"] = action_type
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    stmt = text(
        f"""
        SELECT target_index_id, listing_variant, source_symbol,
               action_date, action_type, value, currency
        FROM derived.v_corporate_action_current
        {where}
        ORDER BY action_date DESC
        LIMIT :lim
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt, params).mappings().all()
    return [CorporateAction(**dict(row)) for row in rows]


def pipeline_status() -> list[PipelineStatus]:
    engine = _engine_or_none()
    if engine is None:
        return []
    stmt = text(
        """
        SELECT pipeline, last_run_id, last_mode, last_status,
               last_started_at_utc, last_finished_at_utc,
               last_error, last_success_at_utc, last_failure_at_utc
        FROM derived.v_pipeline_status
        ORDER BY pipeline
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [PipelineStatus(**dict(row)) for row in rows]


def data_freshness() -> list[DataFreshness]:
    engine = _engine_or_none()
    if engine is None:
        return []
    stmt = text(
        """
        SELECT target_index_id, listing_variant, source_symbol,
               last_trading_date, trading_days, first_trading_date
        FROM derived.v_data_freshness
        ORDER BY target_index_id, listing_variant
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [DataFreshness(**dict(row)) for row in rows]

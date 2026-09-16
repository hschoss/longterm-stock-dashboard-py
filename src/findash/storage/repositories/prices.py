"""Lesender und schreibender Zugriff auf market.prices."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from findash.core.domain import Frequency
from findash.storage.tables import Price

PRICE_FRAME_COLUMNS = ["ts", "open", "high", "low", "close", "adj_close", "volume", "quality_status"]


def get_price_frame(
    session: Session,
    asset_id: int,
    frequency: Frequency = Frequency.DAILY,
) -> pd.DataFrame:
    """Liest eine Kursreihe als DataFrame, sortiert nach Zeit. Fehlende Werte bleiben
    NaN (keine Interpolation, keine Auffuellung)."""

    statement = (
        select(
            Price.ts,
            Price.open,
            Price.high,
            Price.low,
            Price.close,
            Price.adj_close,
            Price.volume,
            Price.quality_status,
        )
        .where(Price.asset_id == asset_id, Price.frequency == frequency.value)
        .order_by(Price.ts)
    )
    rows = session.execute(statement).all()
    frame = pd.DataFrame(rows, columns=PRICE_FRAME_COLUMNS)
    if frame.empty:
        return frame

    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    for column in ["open", "high", "low", "close", "adj_close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    return frame


def upsert_price_rows(session: Session, asset_id: int, frequency: Frequency, frame: pd.DataFrame) -> dict[str, int]:
    """Idempotenter Upsert auf dem natuerlichen Schluessel (asset_id, frequency, ts).
    frame braucht die Spalten aus PRICE_FRAME_COLUMNS (quality_status optional,
    Standard 'ok'). Verwendet von findash sync und findash seed-demo, nicht von der
    Web-App."""

    if frame.empty:
        return {"inserted": 0, "updated": 0}

    existing_rows = {
        price.ts: price
        for price in session.scalars(
            select(Price).where(Price.asset_id == asset_id, Price.frequency == frequency.value)
        )
    }

    inserted = 0
    updated = 0
    for _, row in frame.iterrows():
        ts = pd.Timestamp(row["ts"]).to_pydatetime()
        values = {
            "open": _optional_float(row.get("open")),
            "high": _optional_float(row.get("high")),
            "low": _optional_float(row.get("low")),
            "close": _optional_float(row.get("close")),
            "adj_close": _optional_float(row.get("adj_close")),
            "volume": _optional_int(row.get("volume")),
            "quality_status": row.get("quality_status") or "ok",
        }
        existing = existing_rows.get(ts)
        if existing is None:
            session.add(Price(asset_id=asset_id, frequency=frequency.value, ts=ts, **values))
            inserted += 1
        else:
            for field, value in values.items():
                setattr(existing, field, value)
            updated += 1

    return {"inserted": inserted, "updated": updated}


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)  # type: ignore[arg-type]


def _optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)  # type: ignore[call-overload]

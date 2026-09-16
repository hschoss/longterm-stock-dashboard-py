"""Duenne, nur lesende Datenzugriffsschicht fuer die Dash-App. Jede Funktion oeffnet
eine kurzlebige Session und gibt reine pandas/Python-Objekte zurueck -- die App haelt
keine Session offen und schreibt nie (siehe CLAUDE.md: 'app/ schreibt nie in die
Datenbank')."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from findash.core.domain import Frequency
from findash.storage.db import build_engine, build_session_factory, session_scope
from findash.storage.repositories.assets import get_asset_by_symbol, list_active_assets
from findash.storage.repositories.job_runs import get_last_successful_run
from findash.storage.repositories.prices import get_price_frame
from findash.storage.tables import Asset


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    engine = build_engine()
    return build_session_factory(engine)


def list_assets() -> list[dict[str, object]]:
    with session_scope(_session_factory()) as session:
        return [_asset_to_dict(asset) for asset in list_active_assets(session)]


def get_asset(symbol: str) -> dict[str, object] | None:
    with session_scope(_session_factory()) as session:
        asset = get_asset_by_symbol(session, symbol)
        return _asset_to_dict(asset) if asset is not None else None


def get_price_frame_for_symbol(symbol: str) -> pd.DataFrame:
    """Liefert den vollen Kursframe (inkl. quality_status) fuer die Datenqualitaets-
    Anzeige. Leerer DataFrame, wenn das Asset unbekannt ist oder keine Kursdaten
    vorliegen."""

    with session_scope(_session_factory()) as session:
        asset = get_asset_by_symbol(session, symbol)
        if asset is None:
            return pd.DataFrame()
        return get_price_frame(session, asset.asset_id, Frequency.DAILY)


def get_close_prices(symbol: str, price_field: str = "close") -> pd.Series:
    """Liefert eine mit ts indizierte Preisreihe fuer das gegebene Preisfeld
    ('close' oder 'adj_close'). Leere Reihe, wenn das Asset unbekannt ist oder keine
    Kursdaten vorliegen (kein Erfinden von Werten)."""

    frame = get_price_frame_for_symbol(symbol)
    if frame.empty:
        return pd.Series(dtype=float, name=price_field)
    series = frame.set_index("ts")[price_field]
    series.index.name = "ts"
    return series.rename(price_field)


def get_last_successful_sync() -> datetime | None:
    with session_scope(_session_factory()) as session:
        run = get_last_successful_run(session, job_type="sync")
        return run.finished_at if run is not None else None


def _asset_to_dict(asset: Asset) -> dict[str, object]:
    return {
        "asset_id": asset.asset_id,
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "color": asset.color,
        "region": asset.region,
        "map_label": asset.map_label,
        "lat": asset.lat,
        "lon": asset.lon,
        "card_note": asset.card_note,
    }

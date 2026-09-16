"""Lesender und schreibender Zugriff auf ref.assets. Schreibzugriff ist auf den
Sync von config/assets.yaml beschraenkt (findash sync assets), nicht auf die App."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from findash.core.config_models import AssetConfig
from findash.storage.tables import Asset


def list_active_assets(session: Session) -> list[Asset]:
    statement = select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.symbol)
    return list(session.scalars(statement))


def get_asset_by_symbol(session: Session, symbol: str) -> Asset | None:
    statement = select(Asset).where(Asset.symbol == symbol.strip().upper())
    return session.scalar(statement)


def upsert_asset_from_config(session: Session, config: AssetConfig) -> Asset:
    """Legt ein Asset an oder aktualisiert es anhand von config/assets.yaml.
    Natuerlicher Schluessel ist symbol."""

    symbol = config.symbol.strip().upper()
    asset = get_asset_by_symbol(session, symbol)
    if asset is None:
        asset = Asset(symbol=symbol)
        session.add(asset)

    asset.name = config.name
    asset.asset_type = config.asset_type
    asset.currency = config.currency
    asset.exchange_timezone = config.exchange_timezone
    asset.source_key = config.source_key
    asset.is_active = config.is_active
    asset.color = config.color
    asset.region = config.region
    asset.map_label = config.map_label
    asset.lat = config.lat
    asset.lon = config.lon
    asset.card_note = config.card_note
    return asset

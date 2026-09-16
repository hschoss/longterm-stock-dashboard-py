"""Pydantic-Modelle fuer die YAML-Dateien unter config/. Konfigurierbare Parameter
gehoeren hierher, nicht in den Code (siehe CLAUDE.md)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class AssetConfig(BaseModel):
    symbol: str
    name: str
    asset_type: str
    currency: str
    exchange_timezone: str
    source_key: str | None = None
    is_active: bool = True
    color: str | None = None
    region: str | None = None
    map_label: str | None = None
    lat: float | None = None
    lon: float | None = None
    card_note: str | None = None
    index_constituent_key: str | None = None
    """Verweist auf index_id in ref.index_country_exposure (aktuell noch die CSV unter
    data/index_constituents/aggregated/), sofern fuer dieses Asset eine
    Laender-Exposure-Weltkarte existiert."""


class AssetsConfig(BaseModel):
    assets: list[AssetConfig]


def load_assets_config(path: Path) -> AssetsConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AssetsConfig.model_validate(raw)


class AnalyticsConfig(BaseModel):
    """Fenster, Konfidenzniveaus und Perioden pro Jahr fuer die Ruecksschau-Analytics."""

    periods_per_year: dict[str, int] = Field(default_factory=lambda: {"daily": 252})
    risk_free_rate: float = 0.0
    var_confidence_levels: list[float] = Field(default_factory=lambda: [0.95, 0.99])
    moving_average_windows: list[int] = Field(default_factory=lambda: [20, 50, 200])
    rolling_return_windows_years: list[int] = Field(default_factory=lambda: [10, 15, 20])
    holding_period_years: list[int] = Field(default_factory=lambda: list(range(1, 21)))
    annual_return_histogram_bins: int = 10


def load_analytics_config(path: Path) -> AnalyticsConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AnalyticsConfig.model_validate(raw)

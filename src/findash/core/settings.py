"""Umgebungsbasierte Einstellungen. Werte kommen aus .env, nie aus hartcodierten Defaults
fuer produktive Daten (Datenbank-URL/Zeitzone haben lediglich lokale Entwicklungsdefaults)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://stock:stock@localhost:5432/stock_tracker"
    source_database_url: str | None = None
    sync_overlap_days: int = 10

    display_timezone: str = "Europe/Berlin"

    assets_config_path: Path = Path("config/assets.yaml")
    sync_mapping_config_path: Path = Path("config/sync_mapping.yaml")
    analytics_config_path: Path = Path("config/analytics.yaml")
    forecasting_config_path: Path = Path("config/forecasting.yaml")

    stale_forecast_hours: float = 36.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Liest die Einstellungen einmal pro Prozess (siehe .env)."""

    return Settings()

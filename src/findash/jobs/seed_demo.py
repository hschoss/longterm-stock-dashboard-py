"""findash seed-demo: deterministische Beispieldaten, damit die App ohne
Quelldatenbank startbar ist (CLAUDE.md/docs/auftrag.md Abschnitt 10). Erzeugt fuer
jedes Asset aus config/assets.yaml eine plausible, aber synthetische Tageskursreihe --
keine echten Marktdaten."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from findash.core.config_models import load_assets_config
from findash.core.domain import Frequency
from findash.core.settings import Settings, get_settings
from findash.storage.db import build_engine, build_session_factory, session_scope
from findash.storage.repositories.assets import upsert_asset_from_config
from findash.storage.repositories.prices import upsert_price_rows

logger = logging.getLogger(__name__)

SEED_START = "2005-01-01"
SEED_END = "2024-12-31"


def _synthetic_daily_frame(seed: int, annual_drift: float, annual_volatility: float) -> pd.DataFrame:
    dates = pd.bdate_range(SEED_START, SEED_END, tz="UTC")
    rng = np.random.default_rng(seed)
    daily_drift = annual_drift / 252.0
    daily_volatility = annual_volatility / np.sqrt(252.0)
    daily_log_returns = rng.normal(daily_drift, daily_volatility, size=len(dates))
    close = 100.0 * np.exp(np.cumsum(daily_log_returns))

    return pd.DataFrame(
        {
            "ts": dates,
            "open": close,
            "high": close * 1.004,
            "low": close * 0.996,
            "close": close,
            "adj_close": close,
            "volume": rng.integers(1_000, 500_000, size=len(dates)),
            "quality_status": "ok",
        }
    )


def _seed_parameters(index: int) -> tuple[float, float]:
    """Deterministisch je Position in config/assets.yaml, damit wiederholte Laeufe
    dieselben Daten erzeugen."""

    annual_drift = 0.05 + 0.01 * (index % 4)
    annual_volatility = 0.12 + 0.03 * (index % 3)
    return annual_drift, annual_volatility


def seed_demo(settings: Settings | None = None) -> dict[str, int]:
    settings = settings or get_settings()
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    assets_config = load_assets_config(settings.assets_config_path)

    summary: dict[str, int] = {}
    with session_scope(session_factory) as session:
        for index, asset_config in enumerate(assets_config.assets):
            asset = upsert_asset_from_config(session, asset_config)
            session.flush()

            annual_drift, annual_volatility = _seed_parameters(index)
            frame = _synthetic_daily_frame(
                seed=1000 + index, annual_drift=annual_drift, annual_volatility=annual_volatility
            )
            result = upsert_price_rows(session, asset.asset_id, Frequency.DAILY, frame)
            summary[asset_config.symbol] = result["inserted"] + result["updated"]
            logger.info("seed-demo: %s -> %s Zeilen", asset_config.symbol, summary[asset_config.symbol])

    return summary

"""Gleitende Durchschnitte auf Preiszeitreihen (docs/auftrag.md Abschnitt 8.2:
'gleitende Durchschnitte mit konfigurierbaren Fenstern')."""

from __future__ import annotations

import pandas as pd


def simple_moving_average(prices: pd.Series, window: int) -> pd.Series:
    """Einfacher gleitender Mittelwert (SMA) ueber `window` Beobachtungen. NaN,
    solange das Fenster noch nicht voll ist."""

    clean = pd.to_numeric(prices, errors="coerce").dropna()
    if clean.empty:
        return pd.Series(dtype=float, name=f"sma_{window}")
    return clean.rolling(window=window, min_periods=window).mean().rename(f"sma_{window}")

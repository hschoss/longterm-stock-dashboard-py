"""Resampling von OHLCV-Zeitreihen auf eine groebere Frequenz."""

from __future__ import annotations

from typing import Literal

import pandas as pd

ResampleRule = Literal["W", "ME", "QE", "YE"]

_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "adj_close": "last", "volume": "sum"}


def resample_ohlcv(frame: pd.DataFrame, rule: ResampleRule) -> pd.DataFrame:
    """frame braucht einen DatetimeIndex und eine Teilmenge der Spalten in _AGG."""

    if frame.empty:
        return frame.copy()

    columns_present = {column: how for column, how in _AGG.items() if column in frame.columns}
    resampled = frame.resample(rule).agg(columns_present)
    price_columns = [c for c in ["close", "adj_close"] if c in resampled.columns]
    if price_columns:
        resampled = resampled.dropna(subset=price_columns, how="all")
    return resampled

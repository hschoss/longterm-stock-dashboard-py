"""Trendregression auf Kurszeitreihen. Fasst die drei fruehren Implementierungen
(linear/exponentiell/log2 aus dem alten app/services/stats_service.py) zu einer
einzigen Funktion zusammen (siehe docs/plan.md Abschnitt 6)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from findash.core.domain import TrendType


@dataclass(frozen=True)
class TrendResult:
    trend: pd.Series
    """Trendwert je Zeitpunkt, in derselben Einheit wie der Eingabepreis."""
    deviation_pct: pd.Series
    """Abweichung vom Trend in Prozent: (Preis / Trend - 1) * 100."""
    params: dict[str, float]
    r_squared: float


def _days_since_start(index: pd.DatetimeIndex) -> np.ndarray:
    return (index - index[0]).days.to_numpy(dtype=float)


def fit_trend(prices: pd.Series, trend_type: TrendType) -> TrendResult:
    """Passt eine Trendlinie an eine mit Datum indizierte Preisreihe an.

    - LINEAR: price = a * days + b
    - EXPONENTIAL: price = a * exp(b * days)
    - LOG2: log2(price) = a * log2(days + 1) + b  (Trend im log2-Raum, danach
      zurücktransformiert)

    Wirft ValueError bei weniger als zwei gueltigen, positiven Preispunkten.
    """

    working = pd.to_numeric(prices, errors="coerce").dropna().sort_index()
    working = working[working > 0]
    if len(working) < 2:
        raise ValueError("Mindestens zwei positive Preispunkte werden fuer eine Regression benoetigt.")

    days = _days_since_start(working.index)
    y = working.to_numpy(dtype=float)

    if trend_type == TrendType.LINEAR:
        a, b = np.polyfit(days, y, deg=1)
        trend_values = a * days + b
        params = {"a": float(a), "b": float(b)}
    elif trend_type == TrendType.EXPONENTIAL:
        b, log_a = np.polyfit(days, np.log(y), deg=1)
        a = float(np.exp(log_a))
        trend_values = a * np.exp(b * days)
        params = {"a": a, "b": float(b)}
    elif trend_type == TrendType.LOG2:
        log2_x = np.log2(days + 1.0)
        log2_y = np.log2(y)
        a, b = np.polyfit(log2_x, log2_y, deg=1)
        trend_values = np.power(2.0, a * log2_x + b)
        params = {"a": float(a), "b": float(b)}
    else:  # pragma: no cover - StrEnum erschoepft die Faelle oben
        raise ValueError(f"Unbekannter Trendtyp: {trend_type}")

    residuals_log = np.log(y) - np.log(trend_values)
    total_sum_squares = float(np.sum((np.log(y) - np.mean(np.log(y))) ** 2))
    residual_sum_squares = float(np.sum(residuals_log**2))
    r_squared = 1.0 - residual_sum_squares / total_sum_squares if total_sum_squares else 1.0

    trend = pd.Series(trend_values, index=working.index, name="trend")
    deviation_pct = ((working / trend) - 1.0) * 100.0
    return TrendResult(
        trend=trend, deviation_pct=deviation_pct.rename("deviation_pct"), params=params, r_squared=r_squared
    )

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from findash.analytics.regression import fit_trend
from findash.core.domain import TrendType


def test_fit_trend_linear_recovers_slope() -> None:
    dates = pd.date_range("2020-01-01", periods=100, freq="D", tz="UTC")
    days = np.arange(100, dtype=float)
    prices = pd.Series(50.0 + 2.0 * days, index=dates)

    result = fit_trend(prices, TrendType.LINEAR)
    assert result.params["a"] == pytest.approx(2.0, rel=1e-6)
    assert result.deviation_pct.abs().max() < 1e-6


def test_fit_trend_exponential_recovers_growth_rate(synthetic_daily_prices: pd.Series) -> None:
    result = fit_trend(synthetic_daily_prices, TrendType.EXPONENTIAL)
    assert result.params["b"] == pytest.approx(0.0003, rel=0.2)
    assert result.r_squared > 0.9


def test_fit_trend_log2_deviation_oscillates_around_zero(synthetic_daily_prices: pd.Series) -> None:
    result = fit_trend(synthetic_daily_prices, TrendType.LOG2)
    assert result.deviation_pct.mean() == pytest.approx(0.0, abs=5.0)


def test_fit_trend_requires_two_points(empty_prices: pd.Series) -> None:
    with pytest.raises(ValueError):
        fit_trend(empty_prices, TrendType.LINEAR)

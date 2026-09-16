from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from findash.analytics.returns import (
    annual_returns,
    annualized_return,
    cagr_between,
    log_returns,
    simple_returns,
)


def test_simple_returns_matches_pct_change() -> None:
    prices = pd.Series([100.0, 110.0, 99.0])
    result = simple_returns(prices)
    assert math.isnan(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.10)
    assert result.iloc[2] == pytest.approx(-0.10)


def test_log_returns_matches_formula() -> None:
    prices = pd.Series([100.0, 110.0])
    result = log_returns(prices)
    assert result.iloc[1] == pytest.approx(np.log(1.1))


def test_annualized_return_of_growing_series_is_positive(synthetic_daily_prices: pd.Series) -> None:
    returns = simple_returns(synthetic_daily_prices)
    assert annualized_return(returns, periods_per_year=252) > 0


def test_annualized_return_empty_returns_nan(empty_prices: pd.Series) -> None:
    assert math.isnan(annualized_return(simple_returns(empty_prices), periods_per_year=252))


def test_annual_returns_one_value_per_year_after_first() -> None:
    dates = pd.date_range("2020-01-01", "2023-12-31", freq="D", tz="UTC")
    prices = pd.Series(np.linspace(100, 200, len(dates)), index=dates)
    result = annual_returns(prices)
    assert list(result.index) == [2021, 2022, 2023]


def test_cagr_between_known_values() -> None:
    dates = pd.date_range("2010-01-01", "2020-12-31", freq="D", tz="UTC")
    prices = pd.Series(100.0, index=dates)
    prices.loc["2020-12-31"] = 200.0
    value = cagr_between(prices, 2010, 2020)
    assert value == pytest.approx(2.0 ** (1 / 10) - 1)


def test_cagr_between_missing_year_returns_nan() -> None:
    dates = pd.date_range("2015-01-01", "2018-12-31", freq="D", tz="UTC")
    prices = pd.Series(100.0, index=dates)
    assert math.isnan(cagr_between(prices, 2000, 2018))

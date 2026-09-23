from __future__ import annotations

import math

import pandas as pd
import pytest

from findash.analytics.returns import simple_returns
from findash.analytics.risk import (
    annualized_volatility,
    expected_shortfall,
    rolling_annualized_volatility,
    sharpe_ratio,
    value_at_risk,
)


def test_annualized_volatility_of_constant_series_is_zero() -> None:
    returns = pd.Series([0.01] * 10)
    assert annualized_volatility(returns, periods_per_year=252) == pytest.approx(0.0, abs=1e-9)


def test_sharpe_ratio_empty_is_nan(empty_prices: pd.Series) -> None:
    assert math.isnan(sharpe_ratio(simple_returns(empty_prices), periods_per_year=252))


def test_value_at_risk_is_positive_for_losses() -> None:
    returns = pd.Series([-0.05, -0.02, 0.01, 0.03, -0.10, 0.02, 0.04, -0.01, 0.0, 0.05])
    var_95 = value_at_risk(returns, confidence=0.95)
    assert var_95 > 0


def test_expected_shortfall_is_at_least_var() -> None:
    returns = pd.Series([-0.05, -0.02, 0.01, 0.03, -0.10, 0.02, 0.04, -0.01, 0.0, 0.05])
    var_95 = value_at_risk(returns, confidence=0.95)
    es_95 = expected_shortfall(returns, confidence=0.95)
    assert es_95 >= var_95


def test_rolling_annualized_volatility_matches_static_calculation() -> None:
    returns = pd.Series([0.01, -0.01] * 150)
    rolling = rolling_annualized_volatility(returns, window=50, periods_per_year=252)
    expected = annualized_volatility(returns.iloc[-50:], periods_per_year=252)
    assert rolling.dropna().iloc[-1] == pytest.approx(expected)


def test_rolling_annualized_volatility_nan_before_window_fills() -> None:
    returns = pd.Series([0.01] * 10)
    rolling = rolling_annualized_volatility(returns, window=20, periods_per_year=252)
    assert rolling.dropna().empty

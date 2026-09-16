from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from findash.analytics.rolling import rolling_annualized_return


def test_rolling_annualized_return_of_constant_growth() -> None:
    dates = pd.date_range("2000-01-01", "2020-12-31", freq="D")
    days = np.arange(len(dates), dtype=float)
    prices = pd.Series(100.0 * np.exp(0.07 * days / 365.25), index=dates)

    rolling = rolling_annualized_return(prices, window_years=10).dropna()
    assert not rolling.empty
    assert rolling.iloc[-1] == pytest.approx(0.07, rel=0.05)


def test_rolling_annualized_return_empty_before_first_window() -> None:
    dates = pd.date_range("2020-01-01", periods=100, freq="D")
    prices = pd.Series(100.0, index=dates)
    rolling = rolling_annualized_return(prices, window_years=10)
    assert rolling.dropna().empty

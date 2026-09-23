from __future__ import annotations

import pandas as pd
import pytest

from findash.analytics.moving_average import simple_moving_average


def test_simple_moving_average_of_constant_series_equals_constant() -> None:
    prices = pd.Series([10.0] * 20)
    sma = simple_moving_average(prices, window=5)
    assert sma.dropna().iloc[-1] == pytest.approx(10.0)


def test_simple_moving_average_nan_before_window_fills() -> None:
    prices = pd.Series([10.0] * 3)
    sma = simple_moving_average(prices, window=5)
    assert sma.dropna().empty


def test_simple_moving_average_empty_input() -> None:
    sma = simple_moving_average(pd.Series(dtype=float), window=5)
    assert sma.empty

from __future__ import annotations

import pandas as pd
import pytest

from findash.analytics.savings_plan import simulate_savings_plan


def test_simulate_savings_plan_tracks_deposits_and_value() -> None:
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D", tz="UTC")
    prices = pd.Series(100.0, index=dates)

    result = simulate_savings_plan(
        prices,
        contribution=100.0,
        frequency="yearly",
        start=pd.Timestamp("2020-01-01", tz="UTC"),
        end=pd.Timestamp("2022-12-31", tz="UTC"),
    )

    assert len(result) == 3
    assert result["cumulative_deposits"].iloc[-1] == pytest.approx(300.0)
    assert result["portfolio_value"].iloc[-1] == pytest.approx(300.0)


def test_simulate_savings_plan_empty_prices_returns_empty_frame(empty_prices: pd.Series) -> None:
    result = simulate_savings_plan(
        empty_prices,
        contribution=50.0,
        frequency="monthly",
        start=pd.Timestamp("2020-01-01"),
        end=pd.Timestamp("2020-12-31"),
    )
    assert result.empty

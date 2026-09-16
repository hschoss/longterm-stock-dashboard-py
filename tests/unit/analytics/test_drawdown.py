from __future__ import annotations

import pandas as pd
import pytest

from findash.analytics.drawdown import drawdown_series, recovery_periods


def test_drawdown_series_zero_at_new_highs() -> None:
    prices = pd.Series([100.0, 110.0, 90.0, 120.0])
    dd = drawdown_series(prices)
    assert dd["drawdown_pct"].iloc[1] == pytest.approx(0.0)
    assert dd["drawdown_pct"].iloc[2] < 0
    assert dd["drawdown_pct"].iloc[3] == pytest.approx(0.0)


def test_recovery_periods_finds_trough_and_recovery() -> None:
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    prices = pd.Series([100.0, 80.0, 70.0, 90.0, 110.0], index=dates)
    recoveries = recovery_periods(prices)

    assert len(recoveries) == 1
    row = recoveries.iloc[0]
    assert row["trough_date"] == dates[2]
    assert row["drawdown_pct"] == pytest.approx(-30.0)
    assert row["recovery_date"] == dates[4]
    assert row["recovery_days"] == 2


def test_recovery_periods_unrecovered_trough_has_no_recovery_date() -> None:
    dates = pd.date_range("2020-01-01", periods=3, freq="D")
    prices = pd.Series([100.0, 80.0, 85.0], index=dates)
    recoveries = recovery_periods(prices)

    assert len(recoveries) == 1
    assert pd.isna(recoveries.iloc[0]["recovery_date"])

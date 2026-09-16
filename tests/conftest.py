from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_daily_prices() -> pd.Series:
    """15 Jahre deterministische Tageskurse mit exponentiellem Wachstum plus
    Sinusrauschen, fuer Regressions-, Drawdown-, Rolling- und Triangle-Tests."""

    dates = pd.date_range("2010-01-01", "2024-12-31", freq="D", tz="UTC")
    days = np.arange(len(dates), dtype=float)
    trend = 100.0 * np.exp(0.0003 * days)
    noise = 1.0 + 0.05 * np.sin(days / 17.0)
    prices = trend * noise
    return pd.Series(prices, index=dates, name="close")


@pytest.fixture
def empty_prices() -> pd.Series:
    return pd.Series(dtype=float, name="close")

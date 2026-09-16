from __future__ import annotations

import pandas as pd
import pytest

from findash.analytics.resample import resample_ohlcv


def test_resample_ohlcv_yearly_aggregation() -> None:
    dates = pd.date_range("2020-01-01", "2021-12-31", freq="D", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": range(len(dates)),
            "adj_close": range(len(dates)),
            "volume": 10,
        },
        index=dates,
    )

    resampled = resample_ohlcv(frame, "YE")
    assert len(resampled) == 2
    assert resampled["high"].iloc[0] == pytest.approx(2.0)
    assert resampled["volume"].iloc[0] == pytest.approx(10 * 366)


def test_resample_ohlcv_empty_frame_returns_empty() -> None:
    frame = pd.DataFrame(columns=["close"])
    assert resample_ohlcv(frame, "ME").empty

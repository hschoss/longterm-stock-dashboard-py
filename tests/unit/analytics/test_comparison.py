from __future__ import annotations

import pandas as pd
import pytest

from findash.analytics.comparison import align_series, normalize_to_100


def test_normalize_to_100_starts_at_100() -> None:
    prices = pd.Series([50.0, 60.0, 40.0])
    normalized = normalize_to_100(prices)
    assert normalized.iloc[0] == pytest.approx(100.0)
    assert normalized.iloc[2] == pytest.approx(80.0)


def test_normalize_to_100_rejects_all_negative() -> None:
    with pytest.raises(ValueError):
        normalize_to_100(pd.Series([-1.0, -2.0]))


def test_align_series_uses_common_dates_only() -> None:
    dates_a = pd.date_range("2020-01-01", periods=5, freq="D")
    dates_b = pd.date_range("2020-01-03", periods=5, freq="D")
    series_a = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0], index=dates_a)
    series_b = pd.Series([50.0, 51.0, 52.0, 53.0, 54.0], index=dates_b)

    aligned = align_series({"a": series_a, "b": series_b})
    assert len(aligned) == 3
    assert aligned["a"].iloc[0] == pytest.approx(100.0)
    assert aligned["b"].iloc[0] == pytest.approx(100.0)


def test_align_series_requires_at_least_two() -> None:
    with pytest.raises(ValueError):
        align_series({"a": pd.Series([1.0, 2.0])})

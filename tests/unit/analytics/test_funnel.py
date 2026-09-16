from __future__ import annotations

from findash.analytics.funnel import holding_period_return_stats


def test_holding_period_return_stats_shape(synthetic_daily_prices) -> None:
    stats = holding_period_return_stats(synthetic_daily_prices, holding_years=[1, 5, 10])
    assert list(stats["holding_years"]) == [1, 5, 10]
    assert (stats["min_return"] <= stats["median_return"]).all()
    assert (stats["median_return"] <= stats["max_return"]).all()
    assert stats["share_negative"].between(0.0, 1.0).all()

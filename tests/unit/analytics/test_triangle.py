from __future__ import annotations

from findash.analytics.triangle import lump_sum_return_triangle, savings_plan_return_triangle


def test_lump_sum_return_triangle_is_positive_and_upper_triangular(synthetic_daily_prices) -> None:
    matrix = lump_sum_return_triangle(synthetic_daily_prices)
    assert matrix.loc[2011, 2021] > 0
    assert matrix.loc[2021, 2011] != matrix.loc[2021, 2011]  # untere Haelfte bleibt NaN


def test_savings_plan_return_triangle_is_populated_for_valid_pairs(synthetic_daily_prices) -> None:
    matrix = savings_plan_return_triangle(synthetic_daily_prices, contribution=100.0)
    assert matrix.loc[2011, 2021] == matrix.loc[2011, 2021]  # kein NaN
    assert matrix.loc[2011, 2011] != matrix.loc[2011, 2011]  # Diagonale bleibt NaN

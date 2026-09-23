from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.analytics.comparison import align_series
from findash.analytics.drawdown import drawdown_series
from findash.analytics.funnel import holding_period_return_stats
from findash.analytics.moving_average import simple_moving_average
from findash.analytics.regression import fit_trend
from findash.analytics.returns import annual_returns, simple_returns
from findash.analytics.risk import rolling_annualized_volatility
from findash.analytics.rolling import rolling_annualized_return
from findash.analytics.savings_plan import simulate_savings_plan
from findash.analytics.triangle import lump_sum_return_triangle
from findash.app.figures.annual_returns import build_annual_returns_bar_figure
from findash.app.figures.comparison import build_normalized_comparison_figure
from findash.app.figures.drawdown import build_drawdown_figure
from findash.app.figures.holding_period_funnel import build_holding_period_funnel_figure
from findash.app.figures.price import build_price_figure
from findash.app.figures.return_triangle import build_return_triangle_figure
from findash.app.figures.rolling_returns import build_rolling_returns_figure
from findash.app.figures.rolling_volatility import build_rolling_volatility_figure
from findash.app.figures.savings_plan import build_savings_plan_figure
from findash.app.figures.trend_regression import build_trend_regression_figure
from findash.core.domain import TrendType, YScale


def test_price_figure_has_one_trace(synthetic_daily_prices: pd.Series) -> None:
    figure = build_price_figure(synthetic_daily_prices, y_scale=YScale.LOG)
    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1
    assert figure.layout.yaxis.type == "log"


def test_price_figure_has_rangeslider_and_rangeselector_by_default(synthetic_daily_prices: pd.Series) -> None:
    figure = build_price_figure(synthetic_daily_prices)
    assert figure.layout.xaxis.rangeslider.visible is True
    assert figure.layout.xaxis.rangeselector.buttons is not None


def test_price_figure_without_range_controls(synthetic_daily_prices: pd.Series) -> None:
    figure = build_price_figure(synthetic_daily_prices, show_range_controls=False)
    assert figure.layout.xaxis.rangeslider.visible is False


def test_price_figure_with_regression_and_moving_average_overlays(synthetic_daily_prices: pd.Series) -> None:
    trend = fit_trend(synthetic_daily_prices, TrendType.LINEAR)
    sma = simple_moving_average(synthetic_daily_prices, window=50)
    figure = build_price_figure(
        synthetic_daily_prices,
        regression_traces={"Lineare Regression": trend.trend},
        moving_average_traces={"SMA 50": sma},
    )
    assert len(figure.data) == 3


def test_price_figure_with_drawdown_layer_has_two_rows(synthetic_daily_prices: pd.Series) -> None:
    drawdown = drawdown_series(synthetic_daily_prices)["drawdown_pct"]
    figure = build_price_figure(synthetic_daily_prices, drawdown=drawdown)
    assert len(figure.data) == 2
    assert figure.layout.yaxis2.title.text == "Drawdown %"


def test_trend_regression_figure_has_three_traces(synthetic_daily_prices: pd.Series) -> None:
    figure = build_trend_regression_figure(synthetic_daily_prices, TrendType.EXPONENTIAL)
    assert len(figure.data) == 3


def test_annual_returns_bar_figure(synthetic_daily_prices: pd.Series) -> None:
    figure = build_annual_returns_bar_figure(annual_returns(synthetic_daily_prices))
    assert len(figure.data[0].x) > 0


def test_drawdown_figure(synthetic_daily_prices: pd.Series) -> None:
    figure = build_drawdown_figure(drawdown_series(synthetic_daily_prices), prices=synthetic_daily_prices)
    assert len(figure.data) >= 1


def test_rolling_returns_figure(synthetic_daily_prices: pd.Series) -> None:
    series = {"10 Jahre": rolling_annualized_return(synthetic_daily_prices, 10)}
    figure = build_rolling_returns_figure(series)
    assert len(figure.data) == 1


def test_rolling_volatility_figure(synthetic_daily_prices: pd.Series) -> None:
    returns = simple_returns(synthetic_daily_prices)
    rolling = rolling_annualized_volatility(returns, window=252, periods_per_year=252)
    figure = build_rolling_volatility_figure(rolling)
    assert len(figure.data) == 1


def test_holding_period_funnel_figure(synthetic_daily_prices: pd.Series) -> None:
    stats = holding_period_return_stats(synthetic_daily_prices, [1, 5, 10])
    figure = build_holding_period_funnel_figure(stats)
    assert len(figure.data) == 3


def test_return_triangle_figure(synthetic_daily_prices: pd.Series) -> None:
    matrix = lump_sum_return_triangle(synthetic_daily_prices)
    figure = build_return_triangle_figure(matrix)
    assert figure.data[0].type == "heatmap"


def test_comparison_figure(synthetic_daily_prices: pd.Series) -> None:
    other = synthetic_daily_prices * 0.5
    aligned = align_series({"A": synthetic_daily_prices, "B": other})
    figure = build_normalized_comparison_figure(aligned)
    assert len(figure.data) == 2


def test_savings_plan_figure(synthetic_daily_prices: pd.Series) -> None:
    simulation = simulate_savings_plan(
        synthetic_daily_prices,
        contribution=100.0,
        frequency="yearly",
        start=synthetic_daily_prices.index[0],
        end=synthetic_daily_prices.index[-1],
    )
    figure = build_savings_plan_figure(simulation)
    assert len(figure.data) == 2

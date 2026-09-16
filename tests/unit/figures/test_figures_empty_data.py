"""Jeder Figure-Builder muss mit leeren Daten eine Figur statt eines Fehlers liefern
(siehe CLAUDE.md: 'Figure-Builder ... auch mit leeren Daten testbar')."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures.annual_returns import build_annual_returns_bar_figure
from findash.app.figures.comparison import build_normalized_comparison_figure
from findash.app.figures.drawdown import build_drawdown_figure
from findash.app.figures.holding_period_funnel import build_holding_period_funnel_figure
from findash.app.figures.price import build_price_figure
from findash.app.figures.return_triangle import build_return_triangle_figure
from findash.app.figures.returns_histogram import build_returns_histogram_figure
from findash.app.figures.rolling_returns import build_rolling_returns_figure
from findash.app.figures.savings_plan import build_savings_plan_figure
from findash.app.figures.trend_regression import build_trend_regression_figure
from findash.app.figures.world_map import build_country_exposure_figure


def test_price_figure_empty() -> None:
    assert isinstance(build_price_figure(pd.Series(dtype=float)), go.Figure)


def test_trend_regression_figure_empty() -> None:
    assert isinstance(build_trend_regression_figure(pd.Series(dtype=float)), go.Figure)


def test_annual_returns_bar_figure_empty() -> None:
    assert isinstance(build_annual_returns_bar_figure(pd.Series(dtype=float)), go.Figure)


def test_returns_histogram_figure_empty() -> None:
    assert isinstance(build_returns_histogram_figure(pd.Series(dtype=float)), go.Figure)


def test_holding_period_funnel_figure_empty() -> None:
    assert isinstance(build_holding_period_funnel_figure(pd.DataFrame()), go.Figure)


def test_rolling_returns_figure_empty() -> None:
    assert isinstance(build_rolling_returns_figure({}), go.Figure)


def test_drawdown_figure_empty() -> None:
    assert isinstance(build_drawdown_figure(pd.DataFrame()), go.Figure)


def test_savings_plan_figure_empty() -> None:
    assert isinstance(build_savings_plan_figure(pd.DataFrame()), go.Figure)


def test_return_triangle_figure_empty() -> None:
    assert isinstance(build_return_triangle_figure(pd.DataFrame()), go.Figure)


def test_comparison_figure_empty() -> None:
    assert isinstance(build_normalized_comparison_figure(pd.DataFrame()), go.Figure)


def test_world_map_figure_missing_column() -> None:
    assert isinstance(build_country_exposure_figure(pd.DataFrame(), selected_index_key=None), go.Figure)

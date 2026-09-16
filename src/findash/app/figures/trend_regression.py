"""Log-Chart mit Trendlinie (linear/exponentiell/log2) und Abweichung vom Trend in
einem zweiten Panel (Checkliste: 'Log-Chart mit exponentieller Trendlinie und
Abweichung vom Trend')."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from findash.analytics.regression import fit_trend
from findash.app.figures._common import apply_mobile_layout, empty_figure
from findash.core.domain import TrendType


def build_trend_regression_figure(prices: pd.Series, trend_type: TrendType | str = TrendType.LOG2) -> go.Figure:
    try:
        result = fit_trend(prices, TrendType(trend_type))
    except ValueError:
        return empty_figure("Zu wenige gueltige Kursdaten fuer eine Regression.")

    clean = pd.to_numeric(prices, errors="coerce").dropna()
    clean = clean[clean.index.isin(result.trend.index)]

    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.08)
    figure.add_trace(go.Scatter(x=clean.index, y=clean, mode="lines", name="Kurs"), row=1, col=1)
    figure.add_trace(go.Scatter(x=result.trend.index, y=result.trend, mode="lines", name="Trend"), row=1, col=1)
    figure.add_trace(
        go.Scatter(x=result.deviation_pct.index, y=result.deviation_pct, mode="lines", name="Abweichung %"),
        row=2,
        col=1,
    )
    figure.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
    figure.update_yaxes(type="log", title_text="Kurs (log)", row=1, col=1)
    figure.update_yaxes(title_text="Abweichung %", row=2, col=1)
    figure.update_layout(title=f"Trend ({trend_type}), R²={result.r_squared:.3f}", dragmode=False)
    return apply_mobile_layout(figure)

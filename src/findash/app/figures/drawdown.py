"""Drawdown-Chart mit Fuellung unter 0 % und Hover fuer Tiefpunkt/Erholungsdauer."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.analytics.drawdown import recovery_periods
from findash.app.figures._common import apply_mobile_layout, empty_figure


def build_drawdown_figure(drawdown: pd.DataFrame, prices: pd.Series | None = None) -> go.Figure:
    if drawdown.empty:
        return empty_figure("Keine Drawdown-Daten verfuegbar.")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=drawdown.index,
            y=drawdown["drawdown_pct"],
            mode="lines",
            fill="tozeroy",
            name="Drawdown %",
            hovertemplate="%{x|%Y-%m-%d}: %{y:.1f}%<extra></extra>",
        )
    )

    if prices is not None:
        recoveries = recovery_periods(prices)
        if not recoveries.empty:
            figure.add_trace(
                go.Scatter(
                    x=recoveries["trough_date"],
                    y=recoveries["drawdown_pct"],
                    mode="markers",
                    name="Tiefpunkt",
                    customdata=recoveries[["recovery_days"]].to_numpy(),
                    hovertemplate="Tief %{x|%Y-%m-%d}: %{y:.1f}%<br>Erholung: %{customdata[0]} Tage<extra></extra>",
                )
            )

    figure.update_layout(title="Drawdown", yaxis_title="Drawdown %", dragmode=False)
    return apply_mobile_layout(figure)

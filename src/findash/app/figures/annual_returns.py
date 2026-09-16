"""Jahresrenditen als rot/gruen eingefaerbtes Balkendiagramm."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure

POSITIVE_COLOR = "#16a34a"
NEGATIVE_COLOR = "#dc2626"


def build_annual_returns_bar_figure(returns: pd.Series) -> go.Figure:
    clean = returns.dropna()
    if clean.empty:
        return empty_figure("Keine Jahresrenditen verfuegbar.")

    colors = [POSITIVE_COLOR if value >= 0 else NEGATIVE_COLOR for value in clean]
    figure = go.Figure(
        go.Bar(
            x=clean.index,
            y=clean * 100.0,
            marker_color=colors,
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        )
    )
    figure.update_layout(title="Jahresrenditen", yaxis_title="Rendite %", dragmode=False)
    return apply_mobile_layout(figure)

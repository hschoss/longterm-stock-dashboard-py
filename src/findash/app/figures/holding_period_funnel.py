"""Rendite-Spannweite nach Haltedauer ('Trichter'): Min/Median/Max als gefuellte
Baender."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure

REQUIRED_COLUMNS = ["holding_years", "min_return", "median_return", "max_return"]


def build_holding_period_funnel_figure(stats: pd.DataFrame) -> go.Figure:
    if not set(REQUIRED_COLUMNS).issubset(stats.columns):
        return empty_figure("Keine Daten fuer die gewaehlten Haltedauern.")

    clean = stats.dropna(subset=["min_return", "max_return", "median_return"])
    if clean.empty:
        return empty_figure("Keine Daten fuer die gewaehlten Haltedauern.")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=clean["holding_years"],
            y=clean["max_return"] * 100.0,
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=clean["holding_years"],
            y=clean["min_return"] * 100.0,
            mode="lines",
            fill="tonexty",
            line={"width": 0},
            name="Min-Max-Spanne",
        )
    )
    figure.add_trace(
        go.Scatter(x=clean["holding_years"], y=clean["median_return"] * 100.0, mode="lines+markers", name="Median")
    )
    figure.update_layout(
        title="Annualisierte Rendite nach Haltedauer",
        xaxis_title="Haltedauer (Jahre)",
        yaxis_title="Annualisierte Rendite %",
        dragmode=False,
    )
    return apply_mobile_layout(figure)

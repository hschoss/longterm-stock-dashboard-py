"""Rollierende annualisierte Volatilitaet ueber ein gleitendes Fenster."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure


def build_rolling_volatility_figure(rolling_volatility: pd.Series) -> go.Figure:
    clean = rolling_volatility.dropna()
    if clean.empty:
        return empty_figure("Keine rollierende Volatilitaet verfuegbar.")

    figure = go.Figure()
    figure.add_trace(go.Scatter(x=clean.index, y=clean.to_numpy() * 100.0, mode="lines", name="Volatilitaet"))
    figure.update_layout(
        title="Rollierende annualisierte Volatilitaet",
        yaxis_title="Volatilitaet %",
        dragmode=False,
    )
    return apply_mobile_layout(figure)

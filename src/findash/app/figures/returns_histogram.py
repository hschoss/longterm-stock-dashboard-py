"""Histogramm der Jahresrenditen mit einstellbarer Bingroesse."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure


def build_returns_histogram_figure(returns: pd.Series, bins: int = 10) -> go.Figure:
    clean = returns.dropna()
    if clean.empty:
        return empty_figure("Keine Renditen verfuegbar.")

    figure = go.Figure(go.Histogram(x=clean * 100.0, nbinsx=max(bins, 1)))
    figure.update_layout(title="Verteilung der Jahresrenditen", xaxis_title="Rendite %", yaxis_title="Anzahl Jahre")
    return apply_mobile_layout(figure)

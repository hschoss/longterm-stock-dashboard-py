"""Rollierende annualisierte Renditen ueber mehrere Fensterlaengen (z. B. 10/15/20 Jahre)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure


def build_rolling_returns_figure(series_by_window: dict[str, pd.Series]) -> go.Figure:
    non_empty = {label: series.dropna() for label, series in series_by_window.items() if not series.dropna().empty}
    if not non_empty:
        return empty_figure("Keine rollierenden Renditen fuer die gewaehlten Fenster verfuegbar.")

    figure = go.Figure()
    for label, series in non_empty.items():
        figure.add_trace(go.Scatter(x=series.index, y=series * 100.0, mode="lines", name=label))
    figure.add_hline(y=0, line_dash="dash", line_color="gray")
    figure.update_layout(
        title="Rollierende annualisierte Rendite",
        yaxis_title="Annualisierte Rendite %",
        dragmode=False,
    )
    return apply_mobile_layout(figure)

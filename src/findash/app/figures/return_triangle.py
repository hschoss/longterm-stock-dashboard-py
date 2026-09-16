"""Renditedreieck (Kaufjahr x Verkaufsjahr) als Heatmap mit Zahlen in den Zellen."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure


def build_return_triangle_figure(matrix: pd.DataFrame, title: str = "Renditedreieck") -> go.Figure:
    if matrix.empty or matrix.isna().all(axis=None):
        return empty_figure("Keine Daten fuer ein Renditedreieck verfuegbar.")

    percent = matrix * 100.0
    figure = go.Figure(
        go.Heatmap(
            z=percent.to_numpy(),
            x=[str(year) for year in percent.columns],
            y=[str(year) for year in percent.index],
            colorscale="RdYlGn",
            zmid=0,
            texttemplate="%{z:.1f}",
            hovertemplate="Kauf %{y}, Verkauf %{x}: %{z:.1f}% p.a.<extra></extra>",
            colorbar_title="% p.a.",
        )
    )
    figure.update_layout(title=title, xaxis_title="Verkaufsjahr", yaxis_title="Kaufjahr", dragmode=False)
    return apply_mobile_layout(figure)

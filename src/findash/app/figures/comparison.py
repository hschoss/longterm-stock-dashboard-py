"""Normalisierter Vergleich mehrerer Reihen (Start = 100). Deckt sowohl den
Mehrfach-Asset-Vergleich als auch 'Kursindex vs. Net-Return-Index, USD vs. EUR,
nominal vs. inflationsbereinigt' ab: jede Spalte in `aligned` ist eine zu- oder
abschaltbare Variante mit demselben zugrunde liegenden Preisfeld."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure


def build_normalized_comparison_figure(aligned: pd.DataFrame) -> go.Figure:
    if aligned.empty:
        return empty_figure("Keine gemeinsame Zeitreihe fuer den Vergleich verfuegbar.")

    figure = go.Figure()
    for column in aligned.columns:
        figure.add_trace(go.Scatter(x=aligned.index, y=aligned[column], mode="lines", name=str(column)))
    figure.add_hline(y=100, line_dash="dash", line_color="gray")
    figure.update_layout(
        title="Normalisierter Vergleich (Start = 100)", yaxis_title="Index (Start = 100)", dragmode=False
    )
    return apply_mobile_layout(figure)

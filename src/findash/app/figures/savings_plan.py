"""Sparplan-Simulation: Einzahlungen vs. Depotwert als zwei gefuellte Flaechen."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure


def build_savings_plan_figure(simulation: pd.DataFrame) -> go.Figure:
    if simulation.empty:
        return empty_figure("Keine Sparplan-Simulation fuer die gewaehlten Parameter verfuegbar.")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=simulation.index,
            y=simulation["cumulative_deposits"],
            mode="lines",
            name="Einzahlungen",
            fill="tozeroy",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=simulation.index,
            y=simulation["portfolio_value"],
            mode="lines",
            name="Depotwert",
            fill="tonexty",
        )
    )
    figure.update_layout(title="Sparplan: Einzahlungen vs. Depotwert", yaxis_title="EUR", dragmode=False)
    return apply_mobile_layout(figure)

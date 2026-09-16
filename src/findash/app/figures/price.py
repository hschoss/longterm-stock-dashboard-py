"""Kurschart mit linearer/logarithmischer Y-Achse (Checkliste: 'Kurschart mit
linearer y-Achse' und 'Logarithmischer Kurschart'). Beide sind dieselbe Figur, nur der
Achsentyp unterscheidet sich -- deshalb ein Baustein mit Umschalter statt zweier."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure
from findash.core.domain import YScale


def build_price_figure(
    prices: pd.Series, y_scale: YScale | str = YScale.LINEAR, title: str = "Kursverlauf"
) -> go.Figure:
    clean = pd.to_numeric(prices, errors="coerce").dropna()
    if clean.empty:
        return empty_figure("Keine Kursdaten verfuegbar.")

    figure = go.Figure()
    figure.add_trace(go.Scatter(x=clean.index, y=clean.to_numpy(), mode="lines", name=str(prices.name or "Kurs")))
    figure.update_layout(title=title, yaxis_type=str(y_scale), dragmode=False)
    return apply_mobile_layout(figure)

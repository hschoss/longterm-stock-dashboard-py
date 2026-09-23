"""Kurschart mit linearer/logarithmischer Y-Achse, optionalen Overlay-Layern
(Regressionen, gleitende Durchschnitte), optionalem Drawdown-Panel und nativer
Plotly-Zeitbereichssteuerung (Range Slider + Schnellwahl-Buttons -- Standardloesung
des Oekosystems statt einer eigenen UI-Komponente). Reine Funktion: alle
Overlay-Daten kommen fertig berechnet herein, hier wird nur gerendert (Trennung von
Berechnungslogik und Render-Komponente)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from findash.app.figures._common import apply_mobile_layout, empty_figure
from findash.core.domain import YScale

_RANGE_SELECTOR_BUTTONS = [
    {"count": 1, "label": "1M", "step": "month", "stepmode": "backward"},
    {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
    {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
    {"count": 1, "label": "1J", "step": "year", "stepmode": "backward"},
    {"count": 3, "label": "3J", "step": "year", "stepmode": "backward"},
    {"count": 5, "label": "5J", "step": "year", "stepmode": "backward"},
    {"count": 10, "label": "10J", "step": "year", "stepmode": "backward"},
    {"step": "all", "label": "Max"},
]


def build_price_figure(
    prices: pd.Series,
    y_scale: YScale | str = YScale.LINEAR,
    title: str = "Kursverlauf",
    regression_traces: dict[str, pd.Series] | None = None,
    moving_average_traces: dict[str, pd.Series] | None = None,
    drawdown: pd.Series | None = None,
    show_range_controls: bool = True,
) -> go.Figure:
    clean = pd.to_numeric(prices, errors="coerce").dropna()
    if clean.empty:
        return empty_figure("Keine Kursdaten verfuegbar.")

    show_drawdown = drawdown is not None and not drawdown.dropna().empty
    if show_drawdown:
        figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.06)
        price_row: dict[str, int] = {"row": 1, "col": 1}
    else:
        figure = go.Figure()
        price_row = {}

    figure.add_trace(
        go.Scatter(x=clean.index, y=clean.to_numpy(), mode="lines", name=str(prices.name or "Kurs")), **price_row
    )

    for label, series in (moving_average_traces or {}).items():
        trace_series = series.dropna()
        if trace_series.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=trace_series.index,
                y=trace_series.to_numpy(),
                mode="lines",
                name=label,
                line={"width": 1.5, "dash": "dot"},
            ),
            **price_row,
        )

    for label, series in (regression_traces or {}).items():
        trace_series = series.dropna()
        if trace_series.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=trace_series.index,
                y=trace_series.to_numpy(),
                mode="lines",
                name=label,
                line={"width": 2, "dash": "dash"},
            ),
            **price_row,
        )

    if show_drawdown:
        assert drawdown is not None
        dd = drawdown.dropna()
        figure.add_trace(
            go.Scatter(
                x=dd.index,
                y=dd.to_numpy(),
                mode="lines",
                fill="tozeroy",
                name="Drawdown %",
                hovertemplate="%{x|%Y-%m-%d}: %{y:.1f}%<extra></extra>",
            ),
            row=2,
            col=1,
        )
        figure.update_yaxes(type=str(y_scale), title_text="Kurs", row=1, col=1)
        figure.update_yaxes(title_text="Drawdown %", row=2, col=1)
        figure.update_xaxes(rangeslider={"visible": False}, row=1, col=1)
        figure.update_xaxes(
            rangeslider={"visible": show_range_controls, "thickness": 0.06},
            rangeselector={"buttons": _RANGE_SELECTOR_BUTTONS} if show_range_controls else None,
            row=2,
            col=1,
        )
    else:
        figure.update_layout(yaxis_type=str(y_scale))
        figure.update_xaxes(
            rangeslider={"visible": show_range_controls, "thickness": 0.08},
            rangeselector={"buttons": _RANGE_SELECTOR_BUTTONS} if show_range_controls else None,
        )

    figure.update_layout(title=title, dragmode=False)
    return apply_mobile_layout(figure)

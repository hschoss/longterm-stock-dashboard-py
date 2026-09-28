"""ETF-Detailansicht (`/kurse`).

Zeigt die Kurshistorie eines Instruments als Kerzenchart mit Zeitraum-Toggle
(1M/3M/6M/YTD/1J/5J/Max) und Listing-Umschalter (US/EU, sofern vorhanden).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html
from dash.development.base_component import Component

from findash.storage.repositories.dataserver_market import (
    dataserver_configured,
    list_instruments,
    price_history,
)

dash.register_page(__name__, path="/kurse", name="ETF-Kurse")

_RANGES: dict[str, int | None] = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "YTD": None,
    "1J": 365,
    "5J": 5 * 365,
    "Max": None,
}


class _InstrumentOption(NamedTuple):
    target_index_id: str
    listing_variant: str
    label: str


def _instrument_options() -> list[_InstrumentOption]:
    options: list[_InstrumentOption] = []
    for inst in list_instruments():
        label = f"{inst.tracked_index or inst.target_index_id} · {inst.listing_variant} · {inst.source_symbol}"
        options.append(_InstrumentOption(inst.target_index_id, inst.listing_variant, label))
    return options


def layout(index: str | None = None, listing: str | None = None, **_: object) -> Component:
    if not dataserver_configured():
        return dbc.Alert(
            "Der externe dataserver ist nicht konfiguriert (DATASERVER_URL fehlt).",
            color="warning",
        )

    options = _instrument_options()
    if not options:
        return dbc.Alert("Keine Instrumente verfuegbar.", color="warning")

    if index and listing:
        default = f"{index}|{listing}"
    else:
        default = f"{options[0].target_index_id}|{options[0].listing_variant}"
    dropdown_options = [
        {"label": opt.label, "value": f"{opt.target_index_id}|{opt.listing_variant}"} for opt in options
    ]

    return html.Div(
        [
            html.H1("ETF-Kurse", className="mb-3"),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Dropdown(
                            id="kurse-instrument",
                            options=dropdown_options,
                            value=default,
                            clearable=False,
                        ),
                        xs=12,
                        md=8,
                    ),
                    dbc.Col(
                        dcc.Dropdown(
                            id="kurse-range",
                            options=[{"label": key, "value": key} for key in _RANGES],
                            value="1J",
                            clearable=False,
                        ),
                        xs=12,
                        md=4,
                    ),
                ],
                className="g-2 mb-3",
            ),
            dcc.Graph(id="kurse-chart", config={"displayModeBar": False, "responsive": True}),
            html.P("Keine Anlageberatung.", className="text-body-secondary small mt-2"),
        ]
    )


def _cutoff(range_key: str) -> date | None:
    if range_key == "YTD":
        return date(date.today().year, 1, 1)
    days = _RANGES.get(range_key)
    if days is None:
        return None
    return date.today() - timedelta(days=days)


@callback(
    Output("kurse-chart", "figure"),
    Input("kurse-instrument", "value"),
    Input("kurse-range", "value"),
)
def _update_chart(selection: str | None, range_key: str | None) -> go.Figure:
    figure = go.Figure()
    if not selection:
        return figure
    target_index_id, _, listing_variant = selection.partition("|")
    since = _cutoff(range_key or "1J")
    history = price_history(target_index_id, listing_variant, since=since)
    if not history:
        figure.update_layout(
            annotations=[
                {
                    "text": "keine Daten",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                }
            ]
        )
        return figure

    figure.add_trace(
        go.Candlestick(
            x=[p.trading_date for p in history],
            open=[float(p.open) if p.open is not None else None for p in history],
            high=[float(p.high) if p.high is not None else None for p in history],
            low=[float(p.low) if p.low is not None else None for p in history],
            close=[float(p.close) if p.close is not None else None for p in history],
            name=f"{target_index_id} {listing_variant}",
        )
    )
    figure.update_layout(
        margin={"l": 40, "r": 20, "t": 20, "b": 30},
        xaxis={"rangeslider": {"visible": False}},
        yaxis={"title": history[0].currency or ""},
        dragmode="pan",
    )
    return figure

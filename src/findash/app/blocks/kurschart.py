"""Kurschart-Baustein mit linear/log-Umschalter. Referenzimplementierung fuer das
AIO-Muster mit Pattern-Matching-Callback (CLAUDE.md: 'Callbacks nutzen
Pattern-Matching'): der Callback wird einmal auf Klassenebene registriert und bedient
alle Instanzen ueber MATCH."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import MATCH, Input, Output, callback, ctx, dcc

from findash.app.figures.price import build_price_figure

PriceProvider = Callable[[], pd.Series]


class KurschartAIO(dbc.Card):
    class ids:
        graph = staticmethod(lambda aio_id: {"component": "KurschartAIO", "subcomponent": "graph", "aio_id": aio_id})
        y_scale = staticmethod(
            lambda aio_id: {"component": "KurschartAIO", "subcomponent": "y_scale", "aio_id": aio_id}
        )

    _providers: dict[str, PriceProvider] = {}

    def __init__(self, price_provider: PriceProvider, title: str = "Kursverlauf", aio_id: str | None = None) -> None:
        aio_id = aio_id or str(uuid.uuid4())
        KurschartAIO._providers[aio_id] = price_provider

        super().__init__(
            className="mb-3",
            children=dbc.CardBody(
                [
                    dbc.RadioItems(
                        id=self.ids.y_scale(aio_id),
                        options=[{"label": "Linear", "value": "linear"}, {"label": "Log", "value": "log"}],
                        value="linear",
                        inline=True,
                        className="mb-2",
                    ),
                    dcc.Graph(
                        id=self.ids.graph(aio_id),
                        figure=build_price_figure(price_provider(), y_scale="linear", title=title),
                        config={"displayModeBar": False, "responsive": True},
                    ),
                ]
            ),
        )

    @callback(Output(ids.graph(MATCH), "figure"), Input(ids.y_scale(MATCH), "value"))
    def _update_figure(y_scale: str) -> go.Figure:
        aio_id = ctx.triggered_id["aio_id"]
        provider = KurschartAIO._providers[aio_id]
        return build_price_figure(provider(), y_scale=y_scale)

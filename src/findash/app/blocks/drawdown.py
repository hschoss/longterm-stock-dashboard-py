"""Drawdown-Baustein (Bonus-Baustein Nr. 4, zeigt, wie leicht sich der Baukasten
erweitern laesst -- Analytics- und Figure-Modul existieren schon aus Phase 0/1)."""

from __future__ import annotations

import uuid

import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc

from findash.analytics.drawdown import drawdown_series
from findash.app.figures.drawdown import build_drawdown_figure


class DrawdownAIO(dbc.Card):
    class ids:
        graph = staticmethod(lambda aio_id: {"component": "DrawdownAIO", "subcomponent": "graph", "aio_id": aio_id})

    def __init__(self, prices: pd.Series, aio_id: str | None = None) -> None:
        aio_id = aio_id or str(uuid.uuid4())
        figure = build_drawdown_figure(drawdown_series(prices), prices=prices)
        super().__init__(
            className="mb-3",
            children=dbc.CardBody(
                dcc.Graph(
                    id=self.ids.graph(aio_id), figure=figure, config={"displayModeBar": False, "responsive": True}
                )
            ),
        )

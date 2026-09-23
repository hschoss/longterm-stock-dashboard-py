"""Generischer Chart-Baustein: nimmt eine fertige Plotly-Figur entgegen und kapselt
nur die Card/Graph-Huelle (dbc.Card > CardBody > dcc.Graph). Alle statischen
Chart-Module einer Detailseite (Drawdown, rollierende Rendite, rollierende
Volatilitaet, Renditeverteilung, ...) sind Aufrufe dieses einen Bausteins mit
unterschiedlichen Figuren -- der Baustein selbst ist nie fuer ein Produkt oder
einen Chart-Typ hart verdrahtet, nur die uebergebene Figur aendert sich
(docs/auftrag.md Abschnitt 4.3, Entscheidung 'Python-natives Baukastenmuster' in
docs/entscheidungen.md)."""

from __future__ import annotations

import uuid

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc


class ChartCardAIO(dbc.Card):
    class ids:
        graph = staticmethod(lambda aio_id: {"component": "ChartCardAIO", "subcomponent": "graph", "aio_id": aio_id})

    def __init__(self, figure: go.Figure, aio_id: str | None = None) -> None:
        aio_id = aio_id or str(uuid.uuid4())
        super().__init__(
            className="mb-3",
            children=dbc.CardBody(
                dcc.Graph(
                    id=self.ids.graph(aio_id), figure=figure, config={"displayModeBar": False, "responsive": True}
                )
            ),
        )

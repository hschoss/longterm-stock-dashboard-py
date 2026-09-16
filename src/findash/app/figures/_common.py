"""Gemeinsame Hilfsfunktion fuer alle Figure-Builder: ein leerer Zustand mit
Hinweistext statt eines Fehlers, wenn keine Daten vorliegen (siehe CLAUDE.md:
'Figure-Builder, auch mit leeren Daten testbar')."""

from __future__ import annotations

import plotly.graph_objects as go

MOBILE_MARGIN = {"l": 40, "r": 10, "t": 40, "b": 30}


def empty_figure(message: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 14},
            }
        ],
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin=MOBILE_MARGIN,
    )
    return figure


def apply_mobile_layout(figure: go.Figure) -> go.Figure:
    """Kompakte Raender, horizontale Legende unter dem Chart, responsive -- fuer die
    Nutzung am iPhone (docs/auftrag.md Abschnitt 7)."""

    figure.update_layout(
        margin=MOBILE_MARGIN,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.25, "xanchor": "left", "x": 0},
        autosize=True,
    )
    return figure

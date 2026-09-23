"""Kopf-Baustein einer Produkt-Detailseite: Name, Symbol, Hinweis 'Keine
Anlageberatung' und Datenstand/letzter Sync. Produktunabhaengig -- bekommt Asset und
Sync-Zeitpunkt ausschliesslich als Daten, ist fuer kein Symbol fest verdrahtet."""

from __future__ import annotations

import uuid
from datetime import datetime

import dash_bootstrap_components as dbc
from dash import html


class AssetHeaderAIO(dbc.Card):
    class ids:
        card = staticmethod(lambda aio_id: {"component": "AssetHeaderAIO", "subcomponent": "card", "aio_id": aio_id})

    def __init__(self, asset: dict[str, object], last_sync: datetime | None, aio_id: str | None = None) -> None:
        aio_id = aio_id or str(uuid.uuid4())
        sync_text = (
            f"Datenstand / letzter erfolgreicher Sync: {last_sync:%Y-%m-%d %H:%M}"
            if last_sync
            else "Datenstand / letzter erfolgreicher Sync: kein Sync-Lauf vorhanden"
        )

        super().__init__(
            id=self.ids.card(aio_id),
            className="mb-3",
            children=dbc.CardBody(
                [
                    html.H1(str(asset["name"]), className="mb-1"),
                    html.P(f"Symbol: {asset['symbol']}", className="text-body-secondary mb-1"),
                    html.P(
                        "Keine Anlageberatung. Nur zu Analyse- und Forschungszwecken.",
                        className="small fst-italic mb-1",
                    ),
                    html.P(sync_text, className="small text-body-secondary mb-0"),
                ]
            ),
        )

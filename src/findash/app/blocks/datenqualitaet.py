"""Datenqualitaets-Baustein: Verteilung der quality_status-Werte je Asset plus
Zeitpunkt des letzten erfolgreichen Syncs. Zeigt ehrlich 'kein Sync-Lauf vorhanden',
solange Phase 2 (Sync) nicht existiert -- keine erfundenen Werte (CLAUDE.md)."""

from __future__ import annotations

import uuid
from datetime import datetime

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html

_STATUS_COLOR = {"ok": "success", "flagged": "warning", "missing": "danger"}


class DatenqualitaetAIO(dbc.Card):
    class ids:
        card = staticmethod(lambda aio_id: {"component": "DatenqualitaetAIO", "subcomponent": "card", "aio_id": aio_id})

    def __init__(self, price_frame: pd.DataFrame, last_sync_at: datetime | None, aio_id: str | None = None) -> None:
        aio_id = aio_id or str(uuid.uuid4())
        badges = _status_badges(price_frame)
        sync_text = (
            f"Letzter erfolgreicher Sync: {last_sync_at:%Y-%m-%d %H:%M}"
            if last_sync_at
            else "Letzter erfolgreicher Sync: kein Sync-Lauf vorhanden"
        )

        super().__init__(
            id=self.ids.card(aio_id),
            className="mb-3",
            children=dbc.CardBody(
                [
                    html.Div("Datenqualitaet", className="text-body-secondary small mb-2"),
                    html.Div(badges, className="mb-2"),
                    html.Div(sync_text, className="small text-body-secondary"),
                ]
            ),
        )


def _status_badges(price_frame: pd.DataFrame) -> list[dbc.Badge]:
    if price_frame.empty or "quality_status" not in price_frame.columns:
        return [dbc.Badge("keine Daten", color="secondary", className="me-2")]

    counts = price_frame["quality_status"].value_counts()
    return [
        dbc.Badge(f"{status}: {count}", color=_STATUS_COLOR.get(status, "secondary"), className="me-2")
        for status, count in counts.items()
    ]

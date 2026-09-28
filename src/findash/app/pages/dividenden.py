"""Dividenden- und Corporate-Action-Uebersicht (`/dividenden`)."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import html
from dash.development.base_component import Component

from findash.storage.repositories.dataserver_market import corporate_actions, dataserver_configured

dash.register_page(__name__, path="/dividenden", name="Dividenden")

_HEADERS = ["Datum", "Index", "Listing", "Symbol", "Typ", "Wert", "Waehrung"]


def layout() -> Component:
    if not dataserver_configured():
        return dbc.Alert(
            "Der externe dataserver ist nicht konfiguriert (DATASERVER_URL fehlt).",
            color="warning",
        )

    try:
        actions = corporate_actions(action_type="dividend", limit=200)
    except Exception as exc:  # pragma: no cover
        return dbc.Alert(f"Dividendenliste konnte nicht geladen werden: {exc}", color="danger")

    if not actions:
        return dbc.Alert("Keine Dividenden gefunden.", color="warning")

    header = html.Thead(html.Tr([html.Th(name) for name in _HEADERS]))
    rows = [
        html.Tr(
            [
                html.Td(f"{a.action_date:%Y-%m-%d}"),
                html.Td(a.target_index_id),
                html.Td(a.listing_variant),
                html.Td(a.source_symbol),
                html.Td(a.action_type),
                html.Td(f"{float(a.value):,.4f}"),
                html.Td(a.currency or ""),
            ]
        )
        for a in actions
    ]
    body = html.Tbody(rows)

    return html.Div(
        [
            html.H1("Dividenden", className="mb-3"),
            dbc.Table([header, body], striped=True, bordered=False, hover=True, responsive=True, size="sm"),
            html.P("Keine Anlageberatung.", className="text-body-secondary small"),
        ]
    )

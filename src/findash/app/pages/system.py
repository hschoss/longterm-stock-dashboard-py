"""System-Statusseite (`/system`).

Zeigt Pipeline-Status und Datenaktualitaet aus dem `dataserver`.
Fehlerhafte Pipelines werden sichtbar rot markiert (nichts stillschweigend beschoenigen).
"""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import html
from dash.development.base_component import Component

from findash.storage.dataserver import dataserver_healthy
from findash.storage.repositories.dataserver_market import (
    data_freshness,
    dataserver_configured,
    pipeline_status,
)

dash.register_page(__name__, path="/system", name="System")


def _status_badge(status: str | None) -> Component:
    if status is None:
        return dbc.Badge("unbekannt", color="secondary")
    color = {"ok": "success", "success": "success", "failed": "danger", "error": "danger"}.get(
        status.lower(), "warning"
    )
    return dbc.Badge(status, color=color)


def _pipeline_table() -> Component:
    rows = pipeline_status()
    if not rows:
        return dbc.Alert("Keine Pipeline-Eintraege gefunden.", color="warning")
    header = html.Thead(
        html.Tr(
            [
                html.Th("Pipeline"),
                html.Th("Status"),
                html.Th("Modus"),
                html.Th("Start (UTC)"),
                html.Th("Ende (UTC)"),
                html.Th("Letzter Erfolg (UTC)"),
                html.Th("Letzter Fehler"),
            ]
        )
    )
    body = html.Tbody(
        [
            html.Tr(
                [
                    html.Td(row.pipeline),
                    html.Td(_status_badge(row.last_status)),
                    html.Td(row.last_mode or ""),
                    html.Td(f"{row.last_started_at_utc:%Y-%m-%d %H:%M}" if row.last_started_at_utc else ""),
                    html.Td(f"{row.last_finished_at_utc:%Y-%m-%d %H:%M}" if row.last_finished_at_utc else ""),
                    html.Td(f"{row.last_success_at_utc:%Y-%m-%d %H:%M}" if row.last_success_at_utc else ""),
                    html.Td(html.Small(row.last_error or "", className="text-body-secondary")),
                ]
            )
            for row in rows
        ]
    )
    return dbc.Table([header, body], striped=True, hover=True, responsive=True, size="sm")


def _freshness_table() -> Component:
    rows = data_freshness()
    if not rows:
        return dbc.Alert("Keine Freshness-Daten gefunden.", color="warning")
    header = html.Thead(
        html.Tr(
            [
                html.Th("Index"),
                html.Th("Listing"),
                html.Th("Symbol"),
                html.Th("Letzter Handelstag"),
                html.Th("Handelstage"),
                html.Th("Datenbeginn"),
            ]
        )
    )
    body = html.Tbody(
        [
            html.Tr(
                [
                    html.Td(row.target_index_id),
                    html.Td(row.listing_variant),
                    html.Td(row.source_symbol),
                    html.Td(f"{row.last_trading_date:%Y-%m-%d}" if row.last_trading_date else ""),
                    html.Td(str(row.trading_days) if row.trading_days is not None else ""),
                    html.Td(f"{row.first_trading_date:%Y-%m-%d}" if row.first_trading_date else ""),
                ]
            )
            for row in rows
        ]
    )
    return dbc.Table([header, body], striped=True, hover=True, responsive=True, size="sm")


def layout() -> Component:
    if not dataserver_configured():
        return dbc.Alert(
            "Der externe dataserver ist nicht konfiguriert (DATASERVER_URL fehlt).",
            color="warning",
        )

    connection_ok = dataserver_healthy()
    connection_alert = dbc.Alert(
        f"Dataserver erreichbar: {'ja' if connection_ok else 'nein'}",
        color="success" if connection_ok else "danger",
    )

    try:
        pipeline_view = _pipeline_table()
        freshness_view = _freshness_table()
    except Exception as exc:  # pragma: no cover
        return dbc.Alert(f"Systemstatus konnte nicht geladen werden: {exc}", color="danger")

    return html.Div(
        [
            html.H1("System", className="mb-3"),
            connection_alert,
            html.H2("Pipelines", className="h4 mt-3 mb-2"),
            pipeline_view,
            html.H2("Datenaktualitaet", className="h4 mt-4 mb-2"),
            freshness_view,
        ]
    )

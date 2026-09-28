"""ETF-Uebersichtsseite (`/etf`).

Zeigt alle im `dataserver` bekannten Indizes mit letztem Schlusskurs und einfachen
Performance-Fenstern (1W / 1M / YTD / 1Y). Die Berechnungen sind bewusst leicht:
`storage/repositories/dataserver_market.py` liefert Rohdaten, hier werden nur
Prozente aus zwei Kursen bestimmt (CLAUDE.md: keine schweren Berechnungen in `app/`).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import NamedTuple

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.development.base_component import Component

from findash.storage.repositories.dataserver_market import (
    Instrument,
    LatestPrice,
    dataserver_configured,
    latest_prices,
    list_instruments,
    price_history,
)

dash.register_page(__name__, path="/etf", name="ETF-Uebersicht")

_MISSING = html.Span("keine Daten", className="text-body-secondary")


class _Row(NamedTuple):
    instrument: Instrument
    latest: LatestPrice | None
    pct_1w: float | None
    pct_1m: float | None
    pct_ytd: float | None
    pct_1y: float | None


def _first_close_since(target_index_id: str, listing_variant: str, cutoff: date) -> Decimal | None:
    history = price_history(target_index_id, listing_variant, since=cutoff)
    if not history:
        return None
    return next((p.close for p in history if p.close is not None), None)


def _percent_change(from_close: Decimal | None, to_close: Decimal | None) -> float | None:
    if from_close is None or to_close is None or from_close == 0:
        return None
    try:
        return float((to_close / from_close - 1) * 100)
    except (ArithmeticError, ValueError):
        return None


def _build_rows() -> list[_Row]:
    instruments = list_instruments()
    latest_by_key = {(p.target_index_id, p.listing_variant): p for p in latest_prices()}
    today = date.today()
    year_start = date(today.year, 1, 1)

    rows: list[_Row] = []
    for inst in instruments:
        key = (inst.target_index_id, inst.listing_variant)
        latest = latest_by_key.get(key)
        if latest is None:
            rows.append(_Row(inst, None, None, None, None, None))
            continue

        close_now = latest.close
        rows.append(
            _Row(
                instrument=inst,
                latest=latest,
                pct_1w=_percent_change(
                    _first_close_since(inst.target_index_id, inst.listing_variant, today - timedelta(days=7)),
                    close_now,
                ),
                pct_1m=_percent_change(
                    _first_close_since(inst.target_index_id, inst.listing_variant, today - timedelta(days=30)),
                    close_now,
                ),
                pct_ytd=_percent_change(
                    _first_close_since(inst.target_index_id, inst.listing_variant, year_start),
                    close_now,
                ),
                pct_1y=_percent_change(
                    _first_close_since(inst.target_index_id, inst.listing_variant, today - timedelta(days=365)),
                    close_now,
                ),
            )
        )
    return rows


def _fmt_pct(value: float | None) -> Component:
    if value is None:
        return _MISSING
    color = "text-success" if value >= 0 else "text-danger"
    return html.Span(f"{value:+.2f}%", className=color)


def _fmt_price(value: Decimal | None, currency: str | None) -> Component:
    if value is None:
        return _MISSING
    return html.Span(f"{float(value):,.2f} {currency or ''}".strip())


def _card(row: _Row) -> dbc.Col:
    inst = row.instrument
    header = html.Div(
        [
            html.Strong(inst.name or inst.source_symbol),
            html.Br(),
            html.Span(
                f"{inst.source_symbol} · {inst.exchange_code or '-'} · {inst.currency or '-'}",
                className="text-body-secondary small",
            ),
        ]
    )
    trading_date_text = f"Stand: {row.latest.trading_date:%Y-%m-%d}" if row.latest else "Stand: keine Daten"
    body = dbc.Row(
        [
            dbc.Col(
                [
                    html.Div("Schlusskurs", className="small text-body-secondary"),
                    html.Div(_fmt_price(row.latest.close if row.latest else None, inst.currency), className="fs-5"),
                    html.Div(trading_date_text, className="small text-body-secondary"),
                ],
                xs=12,
                md=6,
            ),
            dbc.Col(
                [
                    html.Div([html.Span("1W ", className="small text-body-secondary"), _fmt_pct(row.pct_1w)]),
                    html.Div([html.Span("1M ", className="small text-body-secondary"), _fmt_pct(row.pct_1m)]),
                    html.Div([html.Span("YTD ", className="small text-body-secondary"), _fmt_pct(row.pct_ytd)]),
                    html.Div([html.Span("1J ", className="small text-body-secondary"), _fmt_pct(row.pct_1y)]),
                ],
                xs=12,
                md=6,
            ),
        ],
        className="g-2",
    )
    link = dcc.Link(
        dbc.Card([dbc.CardHeader(header), dbc.CardBody(body)], className="h-100"),
        href=f"/kurse?index={inst.target_index_id}&listing={inst.listing_variant}",
        className="text-decoration-none text-reset",
    )
    return dbc.Col(link, xs=12, md=6, xl=4, className="mb-3")


def layout() -> Component:
    if not dataserver_configured():
        return dbc.Alert(
            "Der externe dataserver ist nicht konfiguriert (DATASERVER_URL fehlt). "
            "Die ETF-Uebersicht bleibt leer, bis die Verbindung eingerichtet ist.",
            color="warning",
        )

    try:
        rows = _build_rows()
    except Exception as exc:  # pragma: no cover - haengt vom Laufzeitzustand des Dataservers ab
        return dbc.Alert(f"ETF-Uebersicht konnte nicht geladen werden: {exc}", color="danger")

    if not rows:
        return dbc.Alert(
            "Keine Instrumente aus derived.v_instrument gelesen.",
            color="warning",
        )

    return html.Div(
        [
            html.H1("ETF-Uebersicht", className="mb-3"),
            html.P(
                "Aktuelle Kurse und einfache Zeitfenster. Keine Anlageberatung.",
                className="text-body-secondary",
            ),
            dbc.Row([_card(row) for row in rows], className="g-3"),
        ]
    )

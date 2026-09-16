"""Rueckschau-Seite ('/rueckschau/<asset_symbol>'): Kennzahlen, Kurschart,
Datenqualitaet und Drawdown fuer ein Asset (Phase-3-Minimalumfang plus Drawdown als
Beispiel fuer einen leicht ergaenzten Baustein)."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import html

from findash.app.blocks.datenqualitaet import DatenqualitaetAIO
from findash.app.blocks.drawdown import DrawdownAIO
from findash.app.blocks.kennzahlen import KennzahlenAIO
from findash.app.blocks.kurschart import KurschartAIO
from findash.app.data_access import (
    get_asset,
    get_close_prices,
    get_last_successful_sync,
    get_price_frame_for_symbol,
)
from findash.core.config_models import load_analytics_config
from findash.core.settings import get_settings

dash.register_page(__name__, path_template="/rueckschau/<asset_symbol>", name="Rueckschau")


def layout(asset_symbol: str | None = None) -> html.Div:
    if not asset_symbol:
        return html.Div(dbc.Alert("Kein Asset ausgewaehlt.", color="warning"))

    try:
        asset = get_asset(asset_symbol)
    except Exception as exc:  # pragma: no cover - haengt vom Laufzeitzustand der DB ab
        return html.Div(dbc.Alert(f"Asset konnte nicht geladen werden: {exc}", color="danger"))

    if asset is None:
        return html.Div(
            dbc.Alert(
                f"Asset '{asset_symbol}' ist nicht in config/assets.yaml bekannt oder noch nicht synchronisiert "
                "(findash sync run bzw. findash seed-demo).",
                color="warning",
            )
        )

    prices = get_close_prices(asset_symbol)
    price_frame = get_price_frame_for_symbol(asset_symbol)
    analytics_config = load_analytics_config(get_settings().analytics_config_path)
    periods_per_year = analytics_config.periods_per_year.get("daily", 252)

    if prices.dropna().empty:
        return html.Div(
            [
                html.H1(str(asset["name"])),
                dbc.Alert(
                    "Fuer dieses Asset liegen noch keine Kursdaten vor. "
                    "Fuehre 'findash seed-demo' aus oder warte auf den ersten Sync-Lauf.",
                    color="warning",
                ),
            ]
        )

    return html.Div(
        [
            html.H1(str(asset["name"]), className="mb-1"),
            html.P(f"Symbol: {asset['symbol']}", className="text-body-secondary mb-3"),
            KennzahlenAIO(prices, periods_per_year=periods_per_year, risk_free_rate=analytics_config.risk_free_rate),
            KurschartAIO(lambda: prices, title=f"{asset['symbol']}: Kursverlauf"),
            dbc.Row(
                [
                    dbc.Col(DrawdownAIO(prices), xs=12, md=6),
                    dbc.Col(DatenqualitaetAIO(price_frame, get_last_successful_sync()), xs=12, md=6),
                ],
                className="g-3",
            ),
        ]
    )

"""Rueckschau-Seite ('/rueckschau/<asset_symbol>'): baut die Detailansicht eines
Assets aus einer vertikal gestapelten Liste wiederverwendbarer, produktunabhaengiger
Module zusammen. Jedes Modul bekommt ausschliesslich die Daten des aktuell gewaehlten
Assets -- kein Modul ist fest fuer ein Symbol programmiert; ein neues Chart-Modul ist
ein weiterer ChartCardAIO-Aufruf mit einer anderen Figur, keine Aenderung an den
Bausteinen selbst (docs/auftrag.md Abschnitt 4.3). Die Zusammensetzung bleibt
expliziter Python-Code auf der Seite statt eines Plugin-Systems oder einer
YAML-Seitenkomposition (docs/entscheidungen.md, Abschnitt 'Baukastenmuster')."""

from __future__ import annotations

from datetime import datetime

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import html
from dash.development.base_component import Component

from findash.analytics.drawdown import drawdown_series
from findash.analytics.returns import annual_returns, simple_returns
from findash.analytics.risk import rolling_annualized_volatility
from findash.analytics.rolling import rolling_annualized_return
from findash.app.blocks.chart_card import ChartCardAIO
from findash.app.blocks.datenqualitaet import DatenqualitaetAIO
from findash.app.blocks.header import AssetHeaderAIO
from findash.app.blocks.kennzahlen import KennzahlenAIO
from findash.app.blocks.kurschart import KurschartAIO
from findash.app.data_access import (
    get_asset,
    get_close_prices,
    get_last_successful_sync,
    get_price_frame_for_symbol,
)
from findash.app.figures.drawdown import build_drawdown_figure
from findash.app.figures.returns_histogram import build_returns_histogram_figure
from findash.app.figures.rolling_returns import build_rolling_returns_figure
from findash.app.figures.rolling_volatility import build_rolling_volatility_figure
from findash.core.config_models import load_analytics_config
from findash.core.settings import get_settings

dash.register_page(__name__, path_template="/rueckschau/<asset_symbol>", name="Rueckschau")


def _detail_modules(
    asset: dict[str, object],
    prices: pd.Series,
    price_frame: pd.DataFrame,
    last_sync: datetime | None,
) -> list[Component]:
    """Modul-Katalog der Detailseite. Jeder Eintrag ist ein eigenstaendiger,
    wiederverwendbarer Baustein, der nur mit den Daten des gewaehlten Assets
    aufgerufen wird -- alle Produkte durchlaufen dieselben Modul-Typen, lediglich
    die Daten unterscheiden sich."""

    analytics_config = load_analytics_config(get_settings().analytics_config_path)
    periods_per_year = analytics_config.periods_per_year.get("daily", 252)
    returns = simple_returns(prices)

    rolling_returns_by_window = {
        f"{years} Jahre": rolling_annualized_return(prices, window_years=years)
        for years in analytics_config.rolling_return_windows_years
    }

    return [
        AssetHeaderAIO(asset, last_sync),
        KennzahlenAIO(prices, periods_per_year=periods_per_year, risk_free_rate=analytics_config.risk_free_rate),
        KurschartAIO(lambda: prices, title=f"{asset['symbol']}: Kursverlauf"),
        ChartCardAIO(build_drawdown_figure(drawdown_series(prices), prices=prices)),
        ChartCardAIO(build_rolling_returns_figure(rolling_returns_by_window)),
        ChartCardAIO(
            build_rolling_volatility_figure(
                rolling_annualized_volatility(returns, window=periods_per_year, periods_per_year=periods_per_year)
            )
        ),
        ChartCardAIO(
            build_returns_histogram_figure(annual_returns(prices), bins=analytics_config.annual_return_histogram_bins)
        ),
        DatenqualitaetAIO(price_frame, last_sync),
    ]


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
    last_sync = get_last_successful_sync()

    if prices.dropna().empty:
        return html.Div(
            [
                AssetHeaderAIO(asset, last_sync),
                dbc.Alert(
                    "Fuer dieses Asset liegen noch keine Kursdaten vor. "
                    "Fuehre 'findash seed-demo' aus oder warte auf den ersten Sync-Lauf.",
                    color="warning",
                ),
            ]
        )

    return html.Div(_detail_modules(asset, prices, price_frame, last_sync))

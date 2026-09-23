"""Uebersichtsseite ('/'): Asset-Karten-Raster + Weltkarte der Laender-Exposure
(docs/plan.md Abschnitt 4)."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html
from dash.development.base_component import Component

from findash.app.data_access import get_close_prices, list_assets
from findash.app.figures.price import build_price_figure
from findash.app.figures.world_map import DEFAULT_MAP_METRIC, VALID_MAP_METRICS, build_country_exposure_figure
from findash.core.config_models import load_assets_config
from findash.core.settings import get_settings
from findash.storage.repositories.index_constituents import load_all_index_country_exposure

dash.register_page(__name__, path="/", name="Uebersicht")

MAP_METRIC_OPTIONS = [
    {"label": "Unternehmen", "value": "company_count"},
    {"label": "Wertpapiere", "value": "security_count"},
    {"label": "Gewicht %", "value": "total_weight_pct"},
]


def _index_metadata() -> tuple[list[dict[str, str]], dict[str, str], dict[str, str]]:
    """Liest Label/Farbe je index_constituent_key direkt aus config/assets.yaml --
    die Weltkarte zeigt Indexaggregate, keine einzelne Asset-Auswahl."""

    assets_config = load_assets_config(get_settings().assets_config_path)
    options: list[dict[str, str]] = []
    labels: dict[str, str] = {}
    colors: dict[str, str] = {}
    for asset in assets_config.assets:
        if not asset.index_constituent_key:
            continue
        label = asset.map_label or asset.name
        options.append({"label": label, "value": asset.index_constituent_key})
        labels[asset.index_constituent_key] = label
        if asset.color:
            colors[asset.index_constituent_key] = asset.color
    return options, labels, colors


def _asset_card(asset: dict[str, object]) -> dbc.Col:
    prices = get_close_prices(str(asset["symbol"])).dropna()
    if prices.empty:
        last_price_text, change_text = "keine Daten", ""
    else:
        last_price_text = f"{prices.iloc[-1]:,.2f}"
        change = float(prices.iloc[-1] / prices.iloc[-2] - 1.0) if len(prices) >= 2 else float("nan")
        change_text = f"{change * 100:+.2f}%" if change == change else ""

    mini_figure = build_price_figure(prices.tail(252), title="", show_range_controls=False)
    mini_figure.update_layout(height=110, showlegend=False, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    mini_figure.update_xaxes(visible=False)
    mini_figure.update_yaxes(visible=False)

    return dbc.Col(
        dcc.Link(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.H5(str(asset["name"]), className="card-title"),
                        html.P(
                            f"{asset['symbol']} • {last_price_text} • {change_text}",
                            className="text-body-secondary small",
                        ),
                        dcc.Graph(figure=mini_figure, config={"staticPlot": True}, style={"height": "110px"}),
                    ]
                ),
                style={"borderLeft": f"4px solid {asset.get('color') or '#94a3b8'}"},
                className="h-100",
            ),
            href=f"/rueckschau/{asset['symbol']}",
            className="text-decoration-none text-reset",
        ),
        xs=12,
        md=6,
        xl=4,
        className="mb-3",
    )


def layout() -> Component:
    try:
        assets = list_assets()
    except Exception as exc:  # pragma: no cover - haengt vom Laufzeitzustand der DB ab
        return dbc.Alert(f"Assets konnten nicht geladen werden: {exc}", color="danger")

    index_options, _, _ = _index_metadata()
    default_index = index_options[0]["value"] if index_options else None

    return html.Div(
        [
            html.H1("Uebersicht", className="mb-3"),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Dropdown(
                            id="home-map-index",
                            options=[*index_options, {"label": "Alle", "value": "all"}],
                            value=default_index,
                            clearable=False,
                        ),
                        xs=12,
                        md=6,
                    ),
                    dbc.Col(
                        dcc.Dropdown(
                            id="home-map-metric",
                            options=MAP_METRIC_OPTIONS,
                            value=DEFAULT_MAP_METRIC,
                            clearable=False,
                        ),
                        xs=12,
                        md=6,
                    ),
                ],
                className="g-2 mb-3",
            ),
            dcc.Graph(id="home-world-map", config={"displayModeBar": False, "responsive": True}),
            html.H2("Getrackte Assets", className="mt-4 mb-3"),
            dbc.Row([_asset_card(asset) for asset in assets], className="g-3"),
        ]
    )


@callback(
    Output("home-world-map", "figure"),
    Input("home-map-index", "value"),
    Input("home-map-metric", "value"),
)
def _update_world_map(selected_index: str | None, metric: str | None) -> go.Figure:
    _, labels, colors = _index_metadata()
    metric = metric if metric in VALID_MAP_METRICS else DEFAULT_MAP_METRIC
    country_counts = load_all_index_country_exposure()
    selected = None if not selected_index or selected_index == "all" else selected_index
    return build_country_exposure_figure(country_counts, selected, metric, labels, colors)

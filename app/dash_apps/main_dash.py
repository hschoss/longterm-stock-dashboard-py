from __future__ import annotations

import numpy as np
import pandas as pd
from flask import current_app

from app.services.data_service import ensure_price_data, get_asset_by_symbol
from app.services.stats_service import calculate_exponential_regression, calculate_linear_regression

try:
    from dash import Dash, Input, Output, dcc, html, ctx
    from dash.exceptions import PreventUpdate
    import plotly.graph_objects as go
except ModuleNotFoundError:  # pragma: no cover - optional in bare test environments
    Dash = None
    Input = None
    Output = None
    dcc = None
    html = None
    ctx = None
    PreventUpdate = RuntimeError
    go = None


PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close"]
DASH_URL_BASE = "/dash/"


def parse_symbol_from_pathname(pathname: str | None) -> str | None:
    if not pathname or not pathname.startswith("/dash/assets/"):
        return None
    remainder = pathname.removeprefix("/dash/assets/").strip("/")
    normalized = remainder.strip().upper()
    return normalized or None


def get_available_price_columns(df: pd.DataFrame) -> list[str]:
    available: list[str] = []
    for column in PRICE_COLUMNS:
        if column not in df.columns:
            continue
        numeric_values = pd.to_numeric(df[column], errors="coerce")
        if numeric_values.notna().any():
            available.append(column)
    return available


def prepare_asset_dataframe(symbol: str) -> pd.DataFrame:
    asset = get_asset_by_symbol(symbol)
    if asset is None:
        raise ValueError(f"Unknown asset symbol '{symbol}'.")

    frame = ensure_price_data(asset["symbol"]).copy()
    if "Date" not in frame.columns:
        raise ValueError(f"Price data for '{symbol}' does not contain a Date column.")

    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    if frame.empty:
        raise ValueError(f"Price data for '{symbol}' does not contain valid dates.")

    for column in PRICE_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    return frame


def _build_empty_figure(message: str):
    if go is None:
        return {"data": [], "layout": {"title": message}}

    figure = go.Figure()
    figure.update_layout(title=message, template="plotly_white", xaxis_title="Datum", yaxis_title="Preis")
    return figure


def _apply_log2_transform(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    transformed = pd.Series(np.nan, index=series.index, dtype=float)
    positive_mask = numeric > 0
    transformed.loc[positive_mask] = np.log2(numeric.loc[positive_mask].to_numpy(dtype=float))
    return transformed


def _build_slider_marks(dates: pd.Series) -> dict[int, str]:
    if dates.empty:
        return {}

    max_marks = min(8, len(dates))
    positions = np.linspace(0, len(dates) - 1, num=max_marks, dtype=int)
    unique_positions = sorted(set(int(position) for position in positions))
    return {position: dates.iloc[position].strftime("%Y-%m") for position in unique_positions}


def _clamp_range(start_idx: int, end_idx: int, max_index: int) -> tuple[int, int]:
    start = max(0, min(start_idx, max_index))
    end = max(0, min(end_idx, max_index))
    if start > end:
        start, end = end, start
    return start, end


def build_world_map_figure(assets: list[dict]) -> go.Figure | dict:
    if go is None:
        return {"data": [], "layout": {"title": "ETF-Regionen auf der Weltkarte"}}

    mapped_assets = [asset for asset in assets if asset.get("lat") is not None and asset.get("lon") is not None]
    figure = go.Figure()
    if mapped_assets:
        figure.add_trace(
            go.Scattergeo(
                lon=[asset["lon"] for asset in mapped_assets],
                lat=[asset["lat"] for asset in mapped_assets],
                text=[
                    f"{asset['name']}<br>{asset['symbol']}<br>{asset.get('region', '')}"
                    for asset in mapped_assets
                ],
                customdata=[asset["symbol"] for asset in mapped_assets],
                mode="markers+text",
                textposition="top center",
                marker={
                    "size": 12,
                    "opacity": 0.85,
                    "line": {"width": 1, "color": "#16324f"},
                    "color": "#2f7de1",
                },
                hovertemplate="%{text}<extra></extra>",
            )
        )

    figure.update_layout(
        title="ETF-Regionen auf der Weltkarte",
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "showcountries": True,
            "showcoastlines": True,
            "landcolor": "#eef3f8",
            "countrycolor": "#b7c5d8",
            "coastlinecolor": "#8ea1bb",
        },
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
        template="plotly_white",
    )
    return figure


def build_navbar() -> html.Nav:
    assets = current_app.config.get("TRACKED_ASSETS", [])
    return html.Nav(
        [
            dcc.Link("Longterm Stock Dashboard", href="/dash/", className="nav-brand"),
            html.Div(
                [
                    dcc.Link("Weltkarte", href="/dash/", className="nav-link"),
                    dcc.Dropdown(
                        id="asset-switcher",
                        options=[
                            {"label": f"{asset['name']} ({asset['symbol']})", "value": asset["symbol"]}
                            for asset in assets
                        ],
                        placeholder="ETF auswählen",
                        clearable=True,
                        className="nav-switcher",
                    ),
                ],
                className="nav-actions",
            ),
        ],
        className="top-nav",
    )


def build_overview_layout() -> html.Div:
    assets = current_app.config.get("TRACKED_ASSETS", [])
    return html.Div(
        [
            html.Section(
                [
                    html.H1("Globale ETF-Uebersicht"),
                    html.P(
                        "Die Marker zeigen repräsentative Regionen der getrackten ETFs. "
                        "Die Ansicht dient nur der Visualisierung und ist keine Investmentberatung."
                    ),
                    dcc.Graph(
                        id="world-map",
                        figure=build_world_map_figure(assets),
                        config={"displayModeBar": True},
                    ),
                ],
                className="overview-section",
            ),
            html.Section(
                [
                    html.H2("Getrackte ETFs"),
                    html.Div(
                        [
                            dcc.Link(
                                html.Div(
                                    [
                                        html.H3(asset["name"]),
                                        html.P(f"Symbol: {asset['symbol']}"),
                                        html.P(f"Index: {asset.get('index', 'n/a')}"),
                                        html.P(f"Region: {asset.get('region', 'n/a')}"),
                                        html.P(f"ISIN: {asset.get('isin', 'n/a')}"),
                                    ],
                                    className="asset-card",
                                ),
                                href=f"/dash/assets/{asset['symbol']}",
                                className="asset-card-link",
                            )
                            for asset in assets
                        ],
                        className="asset-grid",
                    ),
                ],
                className="asset-list-section",
            ),
        ],
        className="dash-page overview-page",
    )


def build_not_found_layout(symbol: str | None = None) -> html.Div:
    message = f"Das Asset '{symbol}' wurde nicht gefunden." if symbol else "Die angeforderte Seite wurde nicht gefunden."
    return html.Div(
        [
            html.H1("Nicht gefunden"),
            html.P(message),
            dcc.Link("Zur Weltkarte", href="/dash/", className="button-link"),
        ],
        className="dash-page not-found-page",
    )


def build_asset_detail_layout(symbol: str) -> html.Div:
    asset = get_asset_by_symbol(symbol)
    if asset is None:
        return build_not_found_layout(symbol)

    return html.Div(
        [
            html.Section(
                [
                    html.Div(
                        [
                            html.H1(asset["name"]),
                            html.P(f"Symbol: {asset['symbol']}"),
                            html.P(f"Index: {asset.get('index', 'n/a')} | Region: {asset.get('region', 'n/a')}"),
                        ],
                        className="detail-header-copy",
                    ),
                    html.Div(
                        [
                            html.Span(f"WKN: {asset.get('wkn') or '—'}"),
                            html.Span(f"ISIN: {asset.get('isin') or '—'}"),
                            html.Span(f"Provider: {asset.get('provider') or '—'}"),
                            html.Span(f"Ausschuettung: {asset.get('distribution') or '—'}"),
                        ],
                        className="summary-card detail-meta",
                    ),
                    html.P(
                        [
                            dcc.Link("Zur Weltkarte", href="/dash/"),
                            html.Span(" | "),
                            html.A("Kursdaten aktualisieren", href=f"/stocks/{asset['symbol']}/refresh"),
                        ]
                    ),
                ],
                className="detail-header",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Kurswert"),
                                    dcc.Dropdown(id="price-column-dropdown", options=[], value=None, clearable=False),
                                ],
                                className="control-card",
                            ),
                            html.Div(
                                [
                                    html.Label("Y-Achse"),
                                    dcc.RadioItems(
                                        id="y-scale-radio",
                                        options=[
                                            {"label": "Linear", "value": "linear"},
                                            {"label": "Log2-transformiert", "value": "log2"},
                                        ],
                                        value="linear",
                                        inline=True,
                                    ),
                                ],
                                className="control-card",
                            ),
                            html.Div(
                                [
                                    html.Label("Regression"),
                                    dcc.RadioItems(
                                        id="regression-radio",
                                        options=[
                                            {"label": "Keine Regression", "value": "none"},
                                            {"label": "Lineare Regression", "value": "linear"},
                                            {"label": "Exponentielle Regression", "value": "exponential"},
                                        ],
                                        value="none",
                                        inline=True,
                                    ),
                                ],
                                className="control-card",
                            ),
                        ],
                        className="controls-row",
                    ),
                    html.Div(id="asset-status", className="summary-card"),
                    dcc.Graph(id="asset-price-graph"),
                    dcc.RangeSlider(
                        id="date-range-slider",
                        min=0,
                        max=1,
                        step=1,
                        value=[0, 1],
                        marks=None,
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                    html.Div(id="regression-summary", className="summary-card"),
                ],
                className="detail-chart-section",
            ),
        ],
        className="dash-page detail-page",
    )


def build_asset_figure(
    df: pd.DataFrame,
    symbol: str,
    price_column: str,
    y_scale: str,
    regression_type: str,
    start_idx: int,
    end_idx: int,
) -> tuple[go.Figure | dict, dict | None]:
    if df.empty:
        return _build_empty_figure("Keine Kursdaten verfuegbar."), None
    if price_column not in df.columns:
        raise ValueError(f"Price column '{price_column}' is not available.")

    working = df.copy()
    working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    working = working.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    if working.empty:
        return _build_empty_figure("Keine gueltigen Datumswerte verfuegbar."), None

    start, end = _clamp_range(start_idx, end_idx, len(working) - 1)
    visible_df = working.iloc[start : end + 1].copy()
    visible_df[price_column] = pd.to_numeric(visible_df[price_column], errors="coerce")
    visible_df = visible_df[np.isfinite(visible_df[price_column].to_numpy(dtype=float))].copy()
    if visible_df.empty:
        return _build_empty_figure("Keine gueltigen Preiswerte im ausgewaehlten Zeitraum."), None

    regression_series = None
    regression_meta = None
    if regression_type == "linear":
        regression_series, regression_meta = calculate_linear_regression(visible_df, price_column)
    elif regression_type == "exponential":
        regression_series, regression_meta = calculate_exponential_regression(visible_df, price_column)
    elif regression_type != "none":
        raise ValueError(f"Unsupported regression type: {regression_type}")

    if go is None:
        return _build_empty_figure(f"{symbol}: {price_column}"), regression_meta

    price_display = visible_df[price_column].astype(float)
    regression_display = regression_series.astype(float) if regression_series is not None else None
    y_axis_title = "Preis"
    if y_scale == "log2":
        price_display = _apply_log2_transform(price_display)
        if regression_display is not None:
            regression_display = _apply_log2_transform(regression_display)
        y_axis_title = "log2(Preis)"
    elif y_scale != "linear":
        raise ValueError(f"Unsupported y scale: {y_scale}")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=visible_df["Date"],
            y=price_display,
            mode="lines",
            name=price_column,
            hovertemplate="%{x|%Y-%m-%d}<br>Wert=%{y:.4f}<extra></extra>",
        )
    )
    if regression_display is not None:
        regression_label = "Lineare Regression" if regression_type == "linear" else "Exponentielle Regression"
        figure.add_trace(
            go.Scatter(
                x=visible_df.loc[regression_display.index, "Date"],
                y=regression_display,
                mode="lines",
                name=regression_label,
                hovertemplate="%{x|%Y-%m-%d}<br>Regression=%{y:.4f}<extra></extra>",
            )
        )

    figure.update_layout(
        title=f"{symbol}: {price_column}",
        xaxis_title="Datum",
        yaxis_title=y_axis_title,
        hovermode="x unified",
        template="plotly_white",
    )
    figure.update_xaxes(rangeslider_visible=True)
    return figure, regression_meta


def register_main_dash_app(server) -> None:
    if server.extensions.get("main_dash_registered"):
        return
    if Dash is None or dcc is None or html is None or Input is None or Output is None:
        server.extensions["main_dash_registered"] = False
        return

    dash_app = Dash(
        __name__,
        server=server,
        url_base_pathname=DASH_URL_BASE,
        suppress_callback_exceptions=True,
        external_stylesheets=["/static/style.css"],
        title="Longterm Stock Dashboard",
    )

    def build_shell():
        assets = current_app.config.get("TRACKED_ASSETS", [])
        return html.Div(
            [
                dcc.Location(id="url", refresh=False),
                dcc.Store(id="assets-store", data=assets),
                build_navbar(),
                html.Main(id="page-content", className="dash-main"),
            ],
            className="dash-shell",
        )

    dash_app.layout = build_shell

    @dash_app.callback(Output("page-content", "children"), Input("url", "pathname"))
    def display_page(pathname: str | None):
        if pathname in ("/dash/", "/dash", None):
            return build_overview_layout()

        symbol = parse_symbol_from_pathname(pathname)
        if symbol is not None:
            return build_asset_detail_layout(symbol)

        return build_not_found_layout()

    @dash_app.callback(Output("asset-switcher", "value"), Input("url", "pathname"))
    def sync_asset_switcher(pathname: str | None):
        return parse_symbol_from_pathname(pathname)

    @dash_app.callback(
        Output("url", "pathname"),
        Input("asset-switcher", "value"),
        Input("world-map", "clickData"),
        prevent_initial_call=True,
    )
    def navigate_to_asset(symbol: str | None, click_data: dict | None):
        if ctx is None:
            raise PreventUpdate

        trigger = ctx.triggered_id
        if trigger == "asset-switcher":
            return "/dash/" if not symbol else f"/dash/assets/{symbol}"

        if trigger == "world-map":
            if not click_data or not click_data.get("points"):
                raise PreventUpdate
            clicked_symbol = click_data["points"][0].get("customdata")
            if not clicked_symbol:
                raise PreventUpdate
            return f"/dash/assets/{clicked_symbol}"

        raise PreventUpdate

    @dash_app.callback(
        Output("price-column-dropdown", "options"),
        Output("price-column-dropdown", "value"),
        Output("date-range-slider", "min"),
        Output("date-range-slider", "max"),
        Output("date-range-slider", "value"),
        Output("date-range-slider", "marks"),
        Output("asset-status", "children"),
        Input("url", "pathname"),
    )
    def initialize_asset_controls(pathname: str | None):
        symbol = parse_symbol_from_pathname(pathname)
        if symbol is None:
            raise PreventUpdate

        try:
            frame = prepare_asset_dataframe(symbol)
        except Exception as exc:
            return [], None, 0, 1, [0, 1], {}, f"Daten fuer '{symbol}' konnten nicht geladen werden: {exc}"

        columns = get_available_price_columns(frame)
        if not columns:
            return [], None, 0, 1, [0, 1], {}, f"Fuer '{symbol}' sind keine verwendbaren Kurs-Spalten vorhanden."

        options = [{"label": column, "value": column} for column in columns]
        default_value = "Adj Close" if "Adj Close" in columns else "Close" if "Close" in columns else columns[0]
        max_index = len(frame) - 1
        marks = _build_slider_marks(frame["Date"])
        status = (
            f"{symbol}: {len(frame)} Datenpunkte von "
            f"{frame['Date'].iloc[0].strftime('%Y-%m-%d')} bis {frame['Date'].iloc[-1].strftime('%Y-%m-%d')}"
        )
        return options, default_value, 0, max_index, [0, max_index], marks, status

    @dash_app.callback(
        Output("asset-price-graph", "figure"),
        Output("regression-summary", "children"),
        Input("url", "pathname"),
        Input("price-column-dropdown", "value"),
        Input("y-scale-radio", "value"),
        Input("regression-radio", "value"),
        Input("date-range-slider", "value"),
    )
    def update_asset_graph(
        pathname: str | None,
        price_column: str | None,
        y_scale: str,
        regression_type: str,
        date_range: list[int] | None,
    ):
        symbol = parse_symbol_from_pathname(pathname)
        if symbol is None:
            raise PreventUpdate
        if price_column is None:
            return _build_empty_figure("Keine Preisspalte ausgewaehlt."), "Keine Preisspalte ausgewaehlt."

        try:
            frame = prepare_asset_dataframe(symbol)
            slider_value = date_range or [0, max(len(frame) - 1, 0)]
            figure, regression_meta = build_asset_figure(
                frame,
                symbol=symbol,
                price_column=price_column,
                y_scale=y_scale,
                regression_type=regression_type,
                start_idx=int(slider_value[0]),
                end_idx=int(slider_value[1]),
            )
        except Exception as exc:
            return _build_empty_figure(f"{symbol}: Fehler"), f"Die Grafik konnte nicht aktualisiert werden: {exc}"

        if regression_type == "none":
            summary = "Keine Regression ausgewaehlt."
        elif regression_meta is None:
            summary = "Keine Regression verfuegbar."
        elif regression_meta["type"] == "linear":
            summary = (
                f"Lineare Regression: price = {regression_meta['a']:.6f} * days + {regression_meta['b']:.6f} "
                f"({regression_meta['row_count']} Punkte)"
            )
        else:
            summary = (
                f"Exponentielle Regression: price = {regression_meta['a']:.6f} * exp({regression_meta['b']:.6f} * days) "
                f"({regression_meta['row_count']} Punkte)"
            )
        return figure, summary

    server.extensions["main_dash_app"] = dash_app
    server.extensions["main_dash_registered"] = True

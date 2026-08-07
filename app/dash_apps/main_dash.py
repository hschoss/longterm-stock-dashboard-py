from __future__ import annotations

from urllib.parse import parse_qs

import numpy as np
import pandas as pd
from flask import current_app

from app.charts.plotly_charts import DEFAULT_MAP_METRIC, VALID_MAP_METRICS, build_etf_country_exposure_map
from app.index_config import INDEX_COLOR_CONFIG, MAP_ENABLED_INDEX_IDS, get_asset_map_color_style, get_index_color_config
from app.extensions import session_scope
from app.services.data_service import (
    get_asset_by_symbol,
    get_price_frame,
    get_stock,
    load_all_index_country_counts,
)

try:
    from dash import Dash, Input, Output, State, dcc, html, ctx
    from dash.exceptions import PreventUpdate
    import plotly.graph_objects as go
except ModuleNotFoundError:  # pragma: no cover - optional in bare test environments
    Dash = None
    Input = None
    Output = None
    State = None
    dcc = None
    html = None
    ctx = None
    PreventUpdate = RuntimeError
    go = None


PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close"]
DASH_URL_BASE = "/dash/"


def get_refresh_status(search: str | None):
    if not search:
        return None

    query = parse_qs(search.lstrip("?"))
    status = query.get("refresh", [None])[0]

    if status == "success":
        inserted = query.get("inserted", ["0"])[0]
        updated = query.get("updated", ["0"])[0]

        return html.Div(
            (
                f"Kursdaten erfolgreich aktualisiert. "
                f"Neu eingefügt: {inserted}; aktualisiert: {updated}."
            ),
            className="summary-card refresh-success",
        )

    if status == "error":
        message = query.get("message", ["Unbekannter Fehler"])[0]

        return html.Div(
            f"Kursdaten konnten nicht aktualisiert werden: {message}",
            className="summary-card refresh-error",
        )

    return None




def parse_symbol_from_pathname(pathname: str | None) -> str | None:
    if not pathname or not pathname.startswith("/dash/assets/"):
        return None
    remainder = pathname.removeprefix("/dash/assets/").strip("/")
    normalized = remainder.strip().upper()
    return normalized or None


def parse_compare_symbols_from_search(search: str | None) -> tuple[str | None, str | None]:
    if not search:
        return None, None
    query = search[1:] if search.startswith("?") else search
    parsed = parse_qs(query)
    left = parsed.get("left", [None])[0]
    right = parsed.get("right", [None])[0]
    return (left.strip().upper() if left else None), (right.strip().upper() if right else None)


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

    with session_scope() as session:
        stock = get_stock(session, asset["symbol"])

        if stock is None:
            raise ValueError(
                f"Für '{asset['symbol']}' sind noch keine Kursdaten in der "
                "Datenbank vorhanden. Bitte zuerst Kursdaten aktualisieren."
            )

        frame = get_price_frame(session, stock)

    if frame.empty:
        raise ValueError(
            f"Für '{asset['symbol']}' sind keine Kursdaten in der Datenbank vorhanden."
        )

    frame = frame.rename(
        columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "adjusted_close": "Adj Close",
            "volume": "Volume",
        }
    )

    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    for column in PRICE_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if frame.empty:
        raise ValueError(f"No valid database rows available for '{asset['symbol']}'.")

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


def _format_slider_number(value: float) -> str:
    absolute_value = abs(value)
    if absolute_value >= 1_000 or (absolute_value > 0 and absolute_value < 0.01):
        return f"{value:.2e}"
    if absolute_value >= 100:
        return f"{value:.0f}"
    if absolute_value >= 10:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _expand_axis_bounds(min_value: float, max_value: float) -> tuple[float, float]:
    if min_value > max_value:
        min_value, max_value = max_value, min_value

    if np.isclose(min_value, max_value):
        padding = max(abs(min_value) * 0.05, 1.0)
        return min_value - padding, max_value + padding

    padding = (max_value - min_value) * 0.05
    return min_value - padding, max_value + padding


def _build_numeric_slider_marks(min_value: float, max_value: float) -> dict[float, str]:
    positions = np.linspace(min_value, max_value, num=5)
    unique_positions = sorted(set(float(position) for position in positions))
    return {position: _format_slider_number(position) for position in unique_positions}


def _calculate_slider_step(min_value: float, max_value: float) -> float:
    span = max_value - min_value
    if span <= 0:
        return 0.01
    return max(span / 250.0, 0.01)


def _clamp_numeric_range(current_range: list[float] | tuple[float, float] | None, min_value: float, max_value: float) -> list[float]:
    if current_range is None or len(current_range) != 2:
        return [min_value, max_value]

    start = min(max(float(current_range[0]), min_value), max_value)
    end = min(max(float(current_range[1]), min_value), max_value)
    if start > end:
        start, end = end, start

    if np.isclose(start, end):
        return [min_value, max_value]
    return [start, end]


def _clamp_range(start_idx: int, end_idx: int, max_index: int) -> tuple[int, int]:
    start = max(0, min(start_idx, max_index))
    end = max(0, min(end_idx, max_index))
    if start > end:
        start, end = end, start
    return start, end


MAP_METRIC_OPTIONS = [
    {"label": "Company count", "value": "company_count"},
    {"label": "Security count", "value": "security_count"},
    {"label": "Total weight %", "value": "total_weight_pct"},
]
MAP_METRIC_LABELS = {option["value"]: option["label"] for option in MAP_METRIC_OPTIONS}
PREFERRED_MAP_INDEX_ORDER = ["sp500", "msci_canada", "msci_japan", "stoxx_europe_600", "emerging_markets"]


def _build_empty_map_figure(message: str):
    if go is None:
        return {"data": [], "layout": {"title": message}}

    figure = go.Figure()
    figure.update_layout(
        title="Company exposure by country",
        template="plotly_white",
        height=520,
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "showcountries": True,
            "showcoastlines": True,
            "landcolor": "#f8fafc",
            "countrycolor": "#cbd5e1",
            "coastlinecolor": "#94a3b8",
            "showocean": True,
            "oceancolor": "#eff6ff",
            "bgcolor": "#f8fafc",
        },
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 14, "color": "#475569"},
            }
        ],
    )
    return figure


def _load_overview_country_counts() -> tuple[pd.DataFrame, str | None]:
    try:
        country_counts_df = load_all_index_country_counts()
    except FileNotFoundError:
        return pd.DataFrame(), "Country exposure data is not available yet. Run scripts/clean_index_constituents.py first."
    except Exception as exc:
        return pd.DataFrame(), f"Country exposure data could not be loaded: {exc}"

    if country_counts_df.empty:
        return pd.DataFrame(), "Country exposure data is empty."
    if "index_id" not in country_counts_df.columns or "index_name" not in country_counts_df.columns:
        return pd.DataFrame(), "Country exposure data is missing required index columns."

    working = country_counts_df.copy()
    working["index_id"] = working["index_id"].fillna("").astype(str).str.strip().str.lower()
    working["index_name"] = working["index_name"].fillna("").astype(str).str.strip()
    working = working[working["index_id"] != ""].copy()
    if working.empty:
        return pd.DataFrame(), "Country exposure data does not contain any usable index rows."
    return working, None


def _build_overview_index_options(country_counts_df: pd.DataFrame) -> tuple[list[dict[str, str]], str | None]:
    if country_counts_df.empty:
        return [], None

    unique_rows = country_counts_df[["index_id", "index_name"]].drop_duplicates()
    label_by_index_id = {
        str(row["index_id"]): str(row["index_name"]) or INDEX_COLOR_CONFIG.get(str(row["index_id"]), {}).get("label", str(row["index_id"]))
        for _, row in unique_rows.iterrows()
    }
    ordered_index_ids = [index_id for index_id in PREFERRED_MAP_INDEX_ORDER if index_id in label_by_index_id]
    ordered_index_ids.extend(sorted(index_id for index_id in label_by_index_id if index_id not in ordered_index_ids))

    options = [{"label": label_by_index_id[index_id], "value": index_id} for index_id in ordered_index_ids]
    if len(options) > 1:
        options.append({"label": "All", "value": "all"})

    if "sp500" in label_by_index_id:
        default_value = "sp500"
    elif options:
        default_value = options[0]["value"]
    else:
        default_value = None
    return options, default_value


def _build_overview_map_status(country_counts_df: pd.DataFrame, selected_index_id: str, color_metric: str) -> str:
    metric_label = MAP_METRIC_LABELS.get(color_metric, MAP_METRIC_LABELS[DEFAULT_MAP_METRIC])
    if selected_index_id == "all":
        country_count = int(country_counts_df["iso_alpha3"].fillna("").astype(str).str.strip().ne("").sum()) if "iso_alpha3" in country_counts_df.columns else len(country_counts_df)
        return f"Showing all available index datasets. Overlapping countries can visually blend. Color metric: {metric_label}. Rows shown: {country_count}."

    filtered_df = country_counts_df[country_counts_df["index_id"] == selected_index_id].copy()
    if filtered_df.empty:
        return f"No country exposure data is available for '{selected_index_id}'."

    index_name = filtered_df["index_name"].iloc[0]
    country_count = int(filtered_df["iso_alpha3"].fillna("").astype(str).str.strip().ne("").sum()) if "iso_alpha3" in filtered_df.columns else len(filtered_df)
    return f"Showing {index_name} colored by {metric_label}. Countries shown: {country_count}."


def build_navbar() -> html.Nav:
    assets = current_app.config.get("TRACKED_ASSETS", [])
    return html.Nav(
        [
            dcc.Link("Longterm Stock Dashboard", href="/dash/", className="nav-brand"),
            html.Div(
                [
                    dcc.Link("Weltkarte", href="/dash/", className="nav-link"),
                    dcc.Link("Vergleich", href="/dash/compare", className="nav-link"),
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
    country_counts_df, load_error = _load_overview_country_counts()
    index_options, default_index_value = _build_overview_index_options(country_counts_df)
    initial_status = load_error or "Select an ETF / index and a metric to explore company exposure by country."

    return html.Div(
        [
            html.Section(
                [
                    html.H1("Globale ETF-Uebersicht"),
                    html.P(
                        "The world map colors countries by constituent company exposure using the prepared index composition data. "
                        "Tax residence remains a proxy and is not verified legal tax-residence data."
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("ETF / Index"),
                                    dcc.Dropdown(
                                        id="overview-index-dropdown",
                                        options=index_options,
                                        value=default_index_value,
                                        clearable=False,
                                        placeholder="Index auswählen",
                                    ),
                                ],
                                className="control-card",
                            ),
                            html.Div(
                                [
                                    html.Label("Color by"),
                                    dcc.Dropdown(
                                        id="overview-metric-dropdown",
                                        options=MAP_METRIC_OPTIONS,
                                        value=DEFAULT_MAP_METRIC,
                                        clearable=False,
                                    ),
                                ],
                                className="control-card",
                            ),
                        ],
                        className="controls-row",
                    ),
                    html.Div(id="world-map-status", className="summary-card", children=initial_status),
                    dcc.Graph(
                        id="world-map",
                        figure=_build_empty_map_figure(initial_status),
                        config={"displayModeBar": True, "responsive": True},
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
                                        html.Div(
                                            [
                                                html.Span(
                                                    get_index_color_config(asset["index_id"])['label'],
                                                    className="etf-index-badge",
                                                ),
                                            ],
                                            className="asset-card-header",
                                        ),
                                        html.H3(asset["name"]),
                                        html.P(f"Symbol: {asset['symbol']}"),
                                        html.P(f"Index: {asset.get('index', 'n/a')}"),
                                        html.P(f"Region: {asset.get('region', 'n/a')}"),
                                        html.P(f"ISIN: {asset.get('isin', 'n/a')}"),
                                        html.P(asset.get("card_note", ""), className="asset-card-note"),
                                    ],
                                    className="asset-card",
                                    style=get_asset_map_color_style(asset["index_id"]),
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


def build_compare_layout() -> html.Div:
    assets = current_app.config.get("TRACKED_ASSETS", [])
    default_left = assets[0]["symbol"] if assets else None
    default_right = assets[1]["symbol"] if len(assets) > 1 else None
    return html.Div(
        [
            html.Section(
                [
                    html.H1("ETF-Vergleich"),
                    html.P(
                        "Beide Kurse werden auf den ersten gemeinsamen gueltigen Wert im gewaehlten Zeitraum normalisiert. "
                        "Der Startwert ist 100. Die Ansicht ist eine historische Visualisierung und keine Investmentberatung."
                    ),
                ],
                className="overview-section",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Linkes Asset"),
                                    dcc.Dropdown(
                                        id="compare-left-symbol",
                                        options=[
                                            {"label": f"{asset['name']} ({asset['symbol']})", "value": asset["symbol"]}
                                            for asset in assets
                                        ],
                                        value=default_left,
                                        clearable=False,
                                    ),
                                ],
                                className="compare-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Rechtes Asset"),
                                    dcc.Dropdown(
                                        id="compare-right-symbol",
                                        options=[
                                            {"label": f"{asset['name']} ({asset['symbol']})", "value": asset["symbol"]}
                                            for asset in assets
                                        ],
                                        value=default_right,
                                        clearable=False,
                                    ),
                                ],
                                className="compare-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Kurswert"),
                                    dcc.Dropdown(
                                        id="compare-price-column",
                                        options=[
                                            {"label": "Adj Close", "value": "Adj Close"},
                                            {"label": "Close", "value": "Close"},
                                            {"label": "Open", "value": "Open"},
                                            {"label": "High", "value": "High"},
                                            {"label": "Low", "value": "Low"},
                                        ],
                                        value="Adj Close",
                                        clearable=False,
                                    ),
                                ],
                                className="compare-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Y-Anzeige"),
                                    dcc.RadioItems(
                                        id="compare-y-scale",
                                        options=[
                                            {"label": "Linear", "value": "linear"},
                                            {"label": "Log2", "value": "log2"},
                                        ],
                                        value="linear",
                                        inline=True,
                                    ),
                                ],
                                className="compare-control",
                            ),
                        ],
                        className="compare-controls",
                    ),
                    html.Div(id="compare-status", className="summary-card"),
                    dcc.Graph(id="compare-graph"),
                    dcc.RangeSlider(
                        id="compare-date-range-slider",
                        min=0,
                        max=1,
                        step=1,
                        value=[0, 1],
                        marks=None,
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                    html.Div(id="compare-summary", className="compare-summary"),
                ],
                className="detail-chart-section compare-page",
            ),
        ],
        className="dash-page compare-page",
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



def build_asset_detail_layout(
    symbol: str,
    search: str | None = None,
) -> html.Div:
    asset = get_asset_by_symbol(symbol)
    if asset is None:
        return build_not_found_layout(symbol)

    refresh_status = get_refresh_status(search)

    return html.Div(
        [
            html.Section(
                [
                    html.Div(
                        [
                            html.H1(asset["name"]),
                            html.P(f"Symbol: {asset['symbol']}"),
                            html.P(
                                f"Index: {asset.get('index', 'n/a')} | "
                                f"Region: {asset.get('region', 'n/a')}"
                            ),
                        ],
                        className="detail-header-copy",
                    ),
                    html.Div(
                        [
                            html.Span(f"WKN: {asset.get('wkn') or '—'}"),
                            html.Span(f"ISIN: {asset.get('isin') or '—'}"),
                            html.Span(f"Provider: {asset.get('provider') or '—'}"),
                            html.Span(
                                f"Ausschuettung: {asset.get('distribution') or '—'}"
                            ),
                        ],
                        className="summary-card detail-meta",
                    ),
                    html.Div(
                        [
                            dcc.Link("Zur Weltkarte", href="/dash/"),
                            html.Span(" | "),
                            html.Form(
                                [
                                    html.Button(
                                        "Kursdaten aktualisieren",
                                        type="submit",
                                        className="button-link",
                                    )
                                ],
                                action=f"/stocks/{asset['symbol']}/refresh",
                                method="post",
                                style={"display": "inline"},
                            ),
                        ],
                        className="detail-actions",
                    ),
                    html.Div(
                        refresh_status,
                        className="summary-card refresh-status",
                    )
                    if refresh_status
                    else None,
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
                                    dcc.Dropdown(
                                        id="price-column-dropdown",
                                        options=[],
                                        value=None,
                                        clearable=False,
                                    ),
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
                                            {
                                                "label": "Log2-transformiert",
                                                "value": "log2",
                                            },
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
                                            {
                                                "label": "Keine Regression",
                                                "value": "none",
                                            },
                                            {
                                                "label": "Lineare Regression",
                                                "value": "linear",
                                            },
                                            {
                                                "label": "Exponentielle Regression",
                                                "value": "exponential",
                                            },
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
                    html.Div(
                        [
                            dcc.Graph(
                                id="asset-price-graph",
                                config={"scrollZoom": True},
                                className="asset-price-graph",
                            ),
                            html.Div(
                                [
                                    html.Label("Y-Bereich"),
                                    dcc.RangeSlider(
                                        id="asset-y-range-slider",
                                        min=0,
                                        max=1,
                                        step=0.01,
                                        value=[0, 1],
                                        marks={0: "0", 1: "1"},
                                        allowCross=False,
                                        vertical=True,
                                        verticalHeight=420,
                                        tooltip={
                                            "placement": "left",
                                            "always_visible": False,
                                        },
                                        className="asset-y-range-slider",
                                        updatemode="drag",
                                    ),
                                ],
                                className="asset-y-slider-card",
                            ),
                        ],
                        className="asset-chart-with-y-slider",
                    ),
                    dcc.RangeSlider(
                        id="date-range-slider",
                        min=0,
                        max=1,
                        step=1,
                        value=[0, 1],
                        marks=None,
                        tooltip={
                            "placement": "bottom",
                            "always_visible": False,
                        },
                    ),
                    html.Div(
                        id="regression-summary",
                        className="summary-card",
                    ),
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
    y_axis_range: list[float] | tuple[float, float] | None = None,
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
        dragmode="pan",
    )
    figure.update_xaxes(rangeslider_visible=True)
    if y_axis_range is not None and len(y_axis_range) == 2:
        y_start, y_end = sorted((float(y_axis_range[0]), float(y_axis_range[1])))
        if np.isfinite(y_start) and np.isfinite(y_end) and not np.isclose(y_start, y_end):
            figure.update_yaxes(range=[y_start, y_end])
    return figure, regression_meta


def build_asset_y_slider_state(
    df: pd.DataFrame,
    price_column: str,
    y_scale: str,
    regression_type: str,
    start_idx: int,
    end_idx: int,
    current_range: list[float] | tuple[float, float] | None = None,
) -> tuple[float, float, list[float], dict[float, str], float]:
    if df.empty:
        raise ValueError("No price data is available for the y-axis slider.")
    if price_column not in df.columns:
        raise ValueError(f"Price column '{price_column}' is not available.")

    working = df.copy()
    working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    working = working.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    if working.empty:
        raise ValueError("No valid dates are available for the y-axis slider.")

    start, end = _clamp_range(start_idx, end_idx, len(working) - 1)
    visible_df = working.iloc[start : end + 1].copy()
    visible_df[price_column] = pd.to_numeric(visible_df[price_column], errors="coerce")
    visible_df = visible_df[np.isfinite(visible_df[price_column].to_numpy(dtype=float))].copy()
    if visible_df.empty:
        raise ValueError("No valid price values are available for the y-axis slider.")

    displayed_series = visible_df[price_column].astype(float)
    regression_series = None
    if regression_type == "linear":
        regression_series, _ = calculate_linear_regression(visible_df, price_column)
    elif regression_type == "exponential":
        regression_series, _ = calculate_exponential_regression(visible_df, price_column)
    elif regression_type != "none":
        raise ValueError(f"Unsupported regression type: {regression_type}")

    if y_scale == "log2":
        displayed_series = _apply_log2_transform(displayed_series)
        if regression_series is not None:
            regression_series = _apply_log2_transform(regression_series.astype(float))
    elif y_scale != "linear":
        raise ValueError(f"Unsupported y scale: {y_scale}")

    series_parts = [displayed_series]
    if regression_series is not None:
        series_parts.append(regression_series.astype(float))

    combined_values = pd.concat(series_parts, ignore_index=True)
    combined_values = combined_values[np.isfinite(combined_values.to_numpy(dtype=float))]
    if combined_values.empty:
        raise ValueError("No valid display values are available for the y-axis slider.")

    min_value, max_value = _expand_axis_bounds(float(combined_values.min()), float(combined_values.max()))
    return (
        min_value,
        max_value,
        _clamp_numeric_range(current_range, min_value, max_value),
        _build_numeric_slider_marks(min_value, max_value),
        _calculate_slider_step(min_value, max_value),
    )


def _align_common_price_frame(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    price_column: str,
) -> tuple[pd.DataFrame, str]:
    aligned_normalized, actual_price_column = align_two_normalized_series(left_df, right_df, price_column)

    left_working = left_df.copy()
    right_working = right_df.copy()
    left_working["Date"] = pd.to_datetime(left_working["Date"], errors="coerce")
    right_working["Date"] = pd.to_datetime(right_working["Date"], errors="coerce")
    left_working = left_working.dropna(subset=["Date"]).sort_values("Date")
    right_working = right_working.dropna(subset=["Date"]).sort_values("Date")
    left_working[actual_price_column] = pd.to_numeric(left_working[actual_price_column], errors="coerce")
    right_working[actual_price_column] = pd.to_numeric(right_working[actual_price_column], errors="coerce")
    left_working = left_working[np.isfinite(left_working[actual_price_column].to_numpy(dtype=float))]
    right_working = right_working[np.isfinite(right_working[actual_price_column].to_numpy(dtype=float))]
    left_working = left_working[left_working[actual_price_column] > 0]
    right_working = right_working[right_working[actual_price_column] > 0]

    aligned_prices = left_working[["Date", actual_price_column]].merge(
        right_working[["Date", actual_price_column]],
        on="Date",
        how="inner",
        suffixes=("_left", "_right"),
    )
    aligned_prices = aligned_prices.sort_values("Date").reset_index(drop=True)
    if len(aligned_prices) < 2:
        raise ValueError("At least two common valid price points are required for comparison.")

    if len(aligned_prices) != len(aligned_normalized):
        raise ValueError("Aligned comparison series are inconsistent.")
    return aligned_prices, actual_price_column


def build_compare_figure(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_symbol: str,
    right_symbol: str,
    price_column: str,
    y_scale: str,
    start_idx: int,
    end_idx: int,
) -> tuple[go.Figure | dict, dict]:
    aligned_prices, actual_price_column = _align_common_price_frame(left_df, right_df, price_column)
    start, end = _clamp_range(start_idx, end_idx, len(aligned_prices) - 1)
    visible_prices = aligned_prices.iloc[start : end + 1].copy().reset_index(drop=True)
    if len(visible_prices) < 2:
        raise ValueError("At least two common data points are required in the selected range.")

    left_start_price = float(visible_prices[f"{actual_price_column}_left"].iloc[0])
    right_start_price = float(visible_prices[f"{actual_price_column}_right"].iloc[0])
    visible_prices["Left Relative Value"] = visible_prices[f"{actual_price_column}_left"] / left_start_price * 100.0
    visible_prices["Right Relative Value"] = visible_prices[f"{actual_price_column}_right"] / right_start_price * 100.0

    left_relative = visible_prices["Left Relative Value"].astype(float)
    right_relative = visible_prices["Right Relative Value"].astype(float)
    y_axis_title = "Relativer Wert, Start = 100"
    reference_y = 100.0
    reference_label = "Start = 100"
    if y_scale == "log2":
        left_display = np.log2(left_relative / 100.0)
        right_display = np.log2(right_relative / 100.0)
        y_axis_title = "log2(relativer Wert / 100)"
        reference_y = 0.0
        reference_label = "Start"
    elif y_scale == "linear":
        left_display = left_relative
        right_display = right_relative
    else:
        raise ValueError(f"Unsupported compare y scale: {y_scale}")

    if go is None:
        return _build_empty_figure(f"Relativer Vergleich: {left_symbol} vs. {right_symbol}"), {
            "left_symbol": left_symbol,
            "right_symbol": right_symbol,
            "price_column": actual_price_column,
        }

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=visible_prices["Date"],
            y=left_display,
            mode="lines",
            name=left_symbol,
            hovertemplate="%{x|%Y-%m-%d}<br>Wert=%{y:.4f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=visible_prices["Date"],
            y=right_display,
            mode="lines",
            name=right_symbol,
            hovertemplate="%{x|%Y-%m-%d}<br>Wert=%{y:.4f}<extra></extra>",
        )
    )
    figure.add_hline(y=reference_y, line_dash="dash", annotation_text=reference_label)
    figure.update_layout(
        title=f"Relativer Vergleich: {left_symbol} vs. {right_symbol}",
        xaxis_title="Datum",
        yaxis_title=y_axis_title,
        hovermode="x unified",
        template="plotly_white",
    )

    left_end_relative = float(left_relative.iloc[-1])
    right_end_relative = float(right_relative.iloc[-1])
    left_growth_percent = left_end_relative - 100.0
    right_growth_percent = right_end_relative - 100.0
    if left_end_relative > right_end_relative:
        winner = left_symbol
    elif right_end_relative > left_end_relative:
        winner = right_symbol
    else:
        winner = "Gleichstand"

    metrics = {
        "left_symbol": left_symbol,
        "right_symbol": right_symbol,
        "left_start": left_start_price,
        "right_start": right_start_price,
        "left_end_relative": left_end_relative,
        "right_end_relative": right_end_relative,
        "left_growth_percent": left_growth_percent,
        "right_growth_percent": right_growth_percent,
        "winner": winner,
        "visible_start_date": visible_prices["Date"].iloc[0].strftime("%Y-%m-%d"),
        "visible_end_date": visible_prices["Date"].iloc[-1].strftime("%Y-%m-%d"),
        "row_count": int(len(visible_prices)),
        "price_column": actual_price_column,
    }
    return figure, metrics


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

    @dash_app.callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
        Input("url", "search"),
    )
    def display_page(pathname: str | None, search: str | None):
        if pathname in ("/dash/", "/dash", None):
            return build_overview_layout()
    
        if pathname in ("/dash/compare", "/dash/compare/"):
            return build_compare_layout()
    
        symbol = parse_symbol_from_pathname(pathname)
        if symbol is not None:
            return build_asset_detail_layout(symbol, search)
    
        return build_not_found_layout()



    @dash_app.callback(Output("asset-switcher", "value"), Input("url", "pathname"))
    def sync_asset_switcher(pathname: str | None):
        return parse_symbol_from_pathname(pathname)

    @dash_app.callback(
        Output("compare-left-symbol", "value"),
        Output("compare-right-symbol", "value"),
        Input("url", "search"),
        prevent_initial_call=False,
    )
    def initialize_compare_symbols(search: str | None):
        assets = current_app.config.get("TRACKED_ASSETS", [])
        default_left = assets[0]["symbol"] if assets else None
        default_right = assets[1]["symbol"] if len(assets) > 1 else None
        left, right = parse_compare_symbols_from_search(search)
        valid_symbols = {asset["symbol"] for asset in assets}
        return (left if left in valid_symbols else default_left), (right if right in valid_symbols else default_right)

    @dash_app.callback(
        Output("url", "pathname"),
        Input("asset-switcher", "value"),
        prevent_initial_call=True,
    )
    def navigate_to_asset(symbol: str | None):
        return "/dash/" if not symbol else f"/dash/assets/{symbol}"

    @dash_app.callback(
        Output("world-map", "figure"),
        Output("world-map-status", "children"),
        Input("overview-index-dropdown", "value"),
        Input("overview-metric-dropdown", "value"),
    )
    def update_overview_map(selected_index_id: str | None, color_metric: str | None):
        country_counts_df, load_error = _load_overview_country_counts()
        if load_error:
            return _build_empty_map_figure(load_error), load_error

        index_options, default_index_value = _build_overview_index_options(country_counts_df)
        if not index_options or default_index_value is None:
            message = "No ETF / index country exposure datasets are available."
            return _build_empty_map_figure(message), message

        valid_values = {option["value"] for option in index_options}
        effective_index_id = selected_index_id if selected_index_id in valid_values else default_index_value
        effective_metric = color_metric if color_metric in VALID_MAP_METRICS else DEFAULT_MAP_METRIC

        try:
            figure = build_etf_country_exposure_map(
                country_counts_df,
                selected_index_id=None if effective_index_id == "all" else effective_index_id,
                color_metric=effective_metric,
            )
        except Exception as exc:
            message = f"The world map could not be rendered: {exc}"
            return _build_empty_map_figure(message), message

        status = _build_overview_map_status(country_counts_df, effective_index_id, effective_metric)
        return figure, status

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
        Input("asset-y-range-slider", "value"),
    )
    def update_asset_graph(
        pathname: str | None,
        price_column: str | None,
        y_scale: str,
        regression_type: str,
        date_range: list[int] | None,
        y_axis_range: list[float] | None,
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
                y_axis_range=y_axis_range,
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

    @dash_app.callback(
        Output("asset-y-range-slider", "min"),
        Output("asset-y-range-slider", "max"),
        Output("asset-y-range-slider", "value"),
        Output("asset-y-range-slider", "marks"),
        Output("asset-y-range-slider", "step"),
        Input("url", "pathname"),
        Input("price-column-dropdown", "value"),
        Input("y-scale-radio", "value"),
        Input("regression-radio", "value"),
        Input("date-range-slider", "value"),
        State("asset-y-range-slider", "value"),
    )
    def initialize_asset_y_axis_slider(
        pathname: str | None,
        price_column: str | None,
        y_scale: str,
        regression_type: str,
        date_range: list[int] | None,
        current_y_range: list[float] | None,
    ):
        symbol = parse_symbol_from_pathname(pathname)
        if symbol is None:
            raise PreventUpdate
        if price_column is None:
            return 0.0, 1.0, [0.0, 1.0], {0.0: "0", 1.0: "1"}, 0.01

        try:
            frame = prepare_asset_dataframe(symbol)
            slider_value = date_range or [0, max(len(frame) - 1, 0)]
            return build_asset_y_slider_state(
                frame,
                price_column=price_column,
                y_scale=y_scale,
                regression_type=regression_type,
                start_idx=int(slider_value[0]),
                end_idx=int(slider_value[1]),
                current_range=current_y_range,
            )
        except Exception:
            return 0.0, 1.0, [0.0, 1.0], {0.0: "0", 1.0: "1"}, 0.01

    @dash_app.callback(
        Output("compare-date-range-slider", "min"),
        Output("compare-date-range-slider", "max"),
        Output("compare-date-range-slider", "value"),
        Output("compare-date-range-slider", "marks"),
        Output("compare-status", "children"),
        Input("compare-left-symbol", "value"),
        Input("compare-right-symbol", "value"),
        Input("compare-price-column", "value"),
    )
    def initialize_compare_slider(
        left_symbol: str | None,
        right_symbol: str | None,
        price_column: str | None,
    ):
        if not left_symbol or not right_symbol or not price_column:
            raise PreventUpdate
        if left_symbol == right_symbol:
            return 0, 1, [0, 1], {}, "Bitte zwei unterschiedliche Assets fuer den Vergleich auswaehlen."

        try:
            left_df = prepare_asset_dataframe(left_symbol)
            right_df = prepare_asset_dataframe(right_symbol)
            aligned_df, actual_price_column = _align_common_price_frame(left_df, right_df, price_column)
        except Exception as exc:
            return 0, 1, [0, 1], {}, f"Vergleichsdaten konnten nicht vorbereitet werden: {exc}"

        max_index = len(aligned_df) - 1
        marks = _build_slider_marks(aligned_df["Date"])
        status = (
            f"{left_symbol} vs. {right_symbol}: {len(aligned_df)} gemeinsame Datenpunkte von "
            f"{aligned_df['Date'].iloc[0].strftime('%Y-%m-%d')} bis {aligned_df['Date'].iloc[-1].strftime('%Y-%m-%d')} "
            f"mit {actual_price_column}."
        )
        return 0, max_index, [0, max_index], marks, status

    @dash_app.callback(
        Output("compare-graph", "figure"),
        Output("compare-summary", "children"),
        Input("compare-left-symbol", "value"),
        Input("compare-right-symbol", "value"),
        Input("compare-price-column", "value"),
        Input("compare-y-scale", "value"),
        Input("compare-date-range-slider", "value"),
    )
    def update_compare_graph(
        left_symbol: str | None,
        right_symbol: str | None,
        price_column: str | None,
        y_scale: str,
        date_range: list[int] | None,
    ):
        if not left_symbol or not right_symbol or not price_column:
            return _build_empty_figure("Vergleich: Auswahl unvollstaendig"), "Bitte beide Assets und eine Preisspalte auswaehlen."
        if left_symbol == right_symbol:
            return _build_empty_figure("Vergleich: zwei unterschiedliche Assets waehlen"), "Bitte zwei unterschiedliche Assets fuer den Vergleich auswaehlen."

        try:
            left_df = prepare_asset_dataframe(left_symbol)
            right_df = prepare_asset_dataframe(right_symbol)
            aligned_df, _ = _align_common_price_frame(left_df, right_df, price_column)
            slider_value = date_range or [0, max(len(aligned_df) - 1, 0)]
            figure, metrics = build_compare_figure(
                left_df,
                right_df,
                left_symbol=left_symbol,
                right_symbol=right_symbol,
                price_column=price_column,
                y_scale=y_scale,
                start_idx=int(slider_value[0]),
                end_idx=int(slider_value[1]),
            )
        except Exception as exc:
            return _build_empty_figure("Vergleich nicht verfuegbar"), html.Div(str(exc), className="summary-card")

        summary = html.Div(
            [
                html.Div([html.H4("Zeitraum"), html.P(f"{metrics['visible_start_date']} bis {metrics['visible_end_date']}")], className="metric-card"),
                html.Div([html.H4(metrics["left_symbol"]), html.P(f"{metrics['left_growth_percent']:.2f}%")], className="metric-card"),
                html.Div([html.H4(metrics["right_symbol"]), html.P(f"{metrics['right_growth_percent']:.2f}%")], className="metric-card"),
                html.Div([html.H4("Staerker gewachsen"), html.P(metrics["winner"])], className="metric-card"),
                html.Div([html.H4("Preisspalte"), html.P(metrics["price_column"])], className="metric-card"),
            ],
            className="metric-grid",
        )
        return figure, summary

    server.extensions["main_dash_app"] = dash_app
    server.extensions["main_dash_registered"] = True

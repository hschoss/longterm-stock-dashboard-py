"""Kurschart-Baustein: Linear/Log-Umschalter mit Gueltigkeitspruefung, native
Plotly-Zeitbereichssteuerung (Range Slider + Schnellwahl), sowie gleichzeitig
aktivierbare Regressions- und SMA-Overlays und ein optionaler Drawdown-Layer.
Referenzimplementierung fuer das AIO-Muster mit Pattern-Matching-Callback
(CLAUDE.md: 'Callbacks nutzen Pattern-Matching'): der Callback wird einmal auf
Klassenebene registriert und bedient alle Instanzen ueber MATCH. Die
Regressions-/SMA-/Drawdown-Berechnung laeuft in analytics/, dieser Baustein
orchestriert nur und ruft die reine Figure-Funktion auf (Trennung von
Berechnungslogik und Render-Komponente)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import MATCH, Input, Output, callback, ctx, dcc, html
from dash.development.base_component import Component

from findash.analytics.drawdown import drawdown_series
from findash.analytics.moving_average import simple_moving_average
from findash.analytics.regression import TrendResult, fit_trend
from findash.app.figures.price import build_price_figure
from findash.core.domain import TrendType

PriceProvider = Callable[[], pd.Series]

_REGRESSION_TYPES: dict[str, TrendType] = {
    "Lineare Regression": TrendType.LINEAR,
    "Exponentielle Regression": TrendType.EXPONENTIAL,
}
_DRAWDOWN_VALUE = "drawdown"
_LOG_DISABLED_HINT = "Logarithmische Darstellung nicht moeglich: Kurswerte <= 0 im Datensatz."


class KurschartAIO(dbc.Card):
    class ids:
        graph = staticmethod(lambda aio_id: {"component": "KurschartAIO", "subcomponent": "graph", "aio_id": aio_id})
        y_scale = staticmethod(
            lambda aio_id: {"component": "KurschartAIO", "subcomponent": "y_scale", "aio_id": aio_id}
        )
        regressions = staticmethod(
            lambda aio_id: {"component": "KurschartAIO", "subcomponent": "regressions", "aio_id": aio_id}
        )
        moving_averages = staticmethod(
            lambda aio_id: {"component": "KurschartAIO", "subcomponent": "moving_averages", "aio_id": aio_id}
        )
        drawdown_toggle = staticmethod(
            lambda aio_id: {"component": "KurschartAIO", "subcomponent": "drawdown_toggle", "aio_id": aio_id}
        )
        log_hint = staticmethod(
            lambda aio_id: {"component": "KurschartAIO", "subcomponent": "log_hint", "aio_id": aio_id}
        )
        analysis_info = staticmethod(
            lambda aio_id: {"component": "KurschartAIO", "subcomponent": "analysis_info", "aio_id": aio_id}
        )

    _providers: dict[str, PriceProvider] = {}

    def __init__(
        self,
        price_provider: PriceProvider,
        title: str = "Kursverlauf",
        moving_average_windows: tuple[int, ...] = (20, 50, 200),
        aio_id: str | None = None,
    ) -> None:
        aio_id = aio_id or str(uuid.uuid4())
        KurschartAIO._providers[aio_id] = price_provider
        prices = price_provider()
        log_allowed = _is_log_allowed(prices)

        super().__init__(
            className="mb-3",
            children=dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Div("Achse", className="text-body-secondary small"),
                                    dbc.RadioItems(
                                        id=self.ids.y_scale(aio_id),
                                        options=_y_scale_options(log_allowed),
                                        value="linear",
                                        inline=True,
                                    ),
                                    html.Div(
                                        "" if log_allowed else _LOG_DISABLED_HINT,
                                        id=self.ids.log_hint(aio_id),
                                        className="small text-warning",
                                    ),
                                ],
                                xs=12,
                                md=3,
                                className="mb-2",
                            ),
                            dbc.Col(
                                [
                                    html.Div("Trendmodelle", className="text-body-secondary small"),
                                    dbc.Checklist(
                                        id=self.ids.regressions(aio_id),
                                        options=[{"label": label, "value": label} for label in _REGRESSION_TYPES],
                                        value=[],
                                        inline=True,
                                    ),
                                ],
                                xs=12,
                                md=4,
                                className="mb-2",
                            ),
                            dbc.Col(
                                [
                                    html.Div("Gleitende Durchschnitte", className="text-body-secondary small"),
                                    dbc.Checklist(
                                        id=self.ids.moving_averages(aio_id),
                                        options=[
                                            {"label": f"SMA {window}", "value": window}
                                            for window in moving_average_windows
                                        ],
                                        value=[],
                                        inline=True,
                                    ),
                                ],
                                xs=12,
                                md=3,
                                className="mb-2",
                            ),
                            dbc.Col(
                                [
                                    html.Div("Risiko", className="text-body-secondary small"),
                                    dbc.Checklist(
                                        id=self.ids.drawdown_toggle(aio_id),
                                        options=[{"label": "Drawdown-Layer", "value": _DRAWDOWN_VALUE}],
                                        value=[],
                                    ),
                                ],
                                xs=12,
                                md=2,
                                className="mb-2",
                            ),
                        ],
                        className="g-2 mb-2",
                    ),
                    dcc.Graph(
                        id=self.ids.graph(aio_id),
                        figure=build_price_figure(prices, y_scale="linear", title=title),
                        config={"displayModeBar": False, "responsive": True},
                    ),
                    html.Div(id=self.ids.analysis_info(aio_id), className="small mt-2"),
                ]
            ),
        )

    @callback(
        Output(ids.graph(MATCH), "figure"),
        Output(ids.analysis_info(MATCH), "children"),
        Output(ids.y_scale(MATCH), "options"),
        Output(ids.log_hint(MATCH), "children"),
        Input(ids.y_scale(MATCH), "value"),
        Input(ids.regressions(MATCH), "value"),
        Input(ids.moving_averages(MATCH), "value"),
        Input(ids.drawdown_toggle(MATCH), "value"),
        Input(ids.graph(MATCH), "relayoutData"),
    )
    def _update_figure(
        y_scale: str,
        regression_labels: list[str] | None,
        ma_windows: list[int] | None,
        drawdown_selected: list[str] | None,
        relayout_data: dict[str, object] | None,
    ) -> tuple[go.Figure, list[Component], list[dict[str, object]], str]:
        aio_id = ctx.triggered_id["aio_id"]
        provider = KurschartAIO._providers[aio_id]
        prices = provider()

        log_allowed = _is_log_allowed(prices)
        effective_y_scale = y_scale if (y_scale != "log" or log_allowed) else "linear"

        visible_prices = _filter_to_visible_range(prices, relayout_data)

        regression_traces: dict[str, pd.Series] = {}
        analysis_rows: list[Component] = []
        for label in regression_labels or []:
            trend_type = _REGRESSION_TYPES.get(label)
            if trend_type is None:
                continue
            try:
                result = fit_trend(visible_prices, trend_type)
            except ValueError:
                analysis_rows.append(
                    html.Div(f"{label}: zu wenige gueltige Kursdaten im gewaehlten Zeitraum.", className="mb-1")
                )
                continue
            regression_traces[label] = result.trend
            analysis_rows.append(_analysis_row(label, result, visible_prices))

        moving_average_traces = {f"SMA {window}": simple_moving_average(prices, window) for window in ma_windows or []}

        drawdown = drawdown_series(prices)["drawdown_pct"] if _DRAWDOWN_VALUE in (drawdown_selected or []) else None

        figure = build_price_figure(
            prices,
            y_scale=effective_y_scale,
            regression_traces=regression_traces,
            moving_average_traces=moving_average_traces,
            drawdown=drawdown,
        )

        hint = "" if log_allowed else _LOG_DISABLED_HINT
        return figure, analysis_rows, _y_scale_options(log_allowed), hint


def _is_log_allowed(prices: pd.Series) -> bool:
    clean = pd.to_numeric(prices, errors="coerce").dropna()
    return bool((clean > 0).all()) if not clean.empty else True


def _y_scale_options(log_allowed: bool) -> list[dict[str, object]]:
    return [
        {"label": "Linear", "value": "linear"},
        {"label": "Log", "value": "log", "disabled": not log_allowed},
    ]


def _filter_to_visible_range(prices: pd.Series, relayout_data: dict[str, object] | None) -> pd.Series:
    """Grenzt die Preisreihe auf den aktuell ueber Range Slider/Schnellwahl
    gewaehlten Ausschnitt ein, ausgelesen aus Plotlys relayoutData. Ohne
    Auswahl (Erststart, 'Max') bleibt die volle Reihe erhalten."""

    if not relayout_data:
        return prices

    start = relayout_data.get("xaxis.range[0]") or relayout_data.get("xaxis2.range[0]")
    end = relayout_data.get("xaxis.range[1]") or relayout_data.get("xaxis2.range[1]")
    if start is None or end is None:
        range_pair = relayout_data.get("xaxis.range") or relayout_data.get("xaxis2.range")
        if isinstance(range_pair, list) and len(range_pair) == 2:
            start, end = range_pair
    if start is None or end is None:
        return prices

    try:
        start_ts = pd.to_datetime(start, utc=True)
        end_ts = pd.to_datetime(end, utc=True)
    except (ValueError, TypeError):
        return prices
    return prices[(prices.index >= start_ts) & (prices.index <= end_ts)]


def _analysis_row(label: str, result: TrendResult, prices: pd.Series) -> Component:
    clean = prices.dropna()
    period = f"{clean.index.min():%Y-%m-%d} - {clean.index.max():%Y-%m-%d}" if not clean.empty else "n/v"
    params_text = ", ".join(f"{key}={value:.4g}" for key, value in result.params.items())
    return html.Div(
        f"{label}: R²={result.r_squared:.3f}, n={len(clean)}, Zeitraum {period}, Parameter ({params_text})",
        className="mb-1",
    )

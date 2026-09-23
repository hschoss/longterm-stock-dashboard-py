"""Kurschart-Baustein: Linear/Log-Umschalter mit Gueltigkeitspruefung, eigene
Zeitbereichs-Buttons (verankert am letzten tatsaechlich verfuegbaren Datenpunkt der
Reihe, nicht am heutigen Datum) plus synchronem Plotly-Range-Slider, sowie
gleichzeitig aktivierbare Regressions- und SMA-Overlays und ein optionaler
Drawdown-Layer. Referenzimplementierung fuer das AIO-Muster mit
Pattern-Matching-Callbacks (CLAUDE.md: 'Callbacks nutzen Pattern-Matching').

Zwei getrennte Callbacks statt einem grossen:
- `_update_range_state` ist die einzige Quelle der Wahrheit fuer den aktuell
  sichtbaren Zeitausschnitt (chartState). Er reagiert auf Klicks auf die
  Zeitbereichs-Buttons und auf manuelles Ziehen des Range-Sliders
  (`relayoutData`) und schreibt das Ergebnis in einen `dcc.Store`.
- `_update_figure` liest diesen Store zusammen mit Achsen-/Overlay-Auswahl und
  rendert die Figur neu. Er haengt NICHT an `relayoutData`, damit das Setzen
  einer neuen Figur nicht wieder einen Relayout-Callback ausloest (sonst
  Rueckkopplungsschleife zwischen Output(figure) und Input(relayoutData)).

Beide Callbacks haben `prevent_initial_call=True`: Pattern-Matching-Callbacks
feuern sonst automatisch einmal, sobald eine passende Komponente neu auf der
Seite erscheint (z. B. bei jedem Produktwechsel) -- dabei ist `ctx.triggered_id`
None, was ohne dieses Flag zu einem Serverfehler fuehrte und alle drei
Bedienelemente unzuverlaessig wirken liess. Die Startfigur kommt bereits fertig
aus `__init__`, ein Callback-Aufruf beim Mounten ist also nie noetig.

Die Regressions-/SMA-/Drawdown-Berechnung laeuft in analytics/, dieser Baustein
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
from dash.exceptions import PreventUpdate

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
_LOG_DISABLED_HINT = "Logarithmische Darstellung nicht moeglich: Kurswerte <= 0 im gewaehlten Zeitraum."

_RANGE_PRESET_ORDER = ("1M", "3M", "6M", "5J", "10J", "Max")
_RANGE_PRESET_OFFSETS: dict[str, pd.DateOffset | None] = {
    "1M": pd.DateOffset(months=1),
    "3M": pd.DateOffset(months=3),
    "6M": pd.DateOffset(months=6),
    "5J": pd.DateOffset(years=5),
    "10J": pd.DateOffset(years=10),
    "Max": None,
}
_DEFAULT_RANGE_STATE: dict[str, object] = {"start": None, "end": None, "active_preset": "Max"}


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
        range_state = staticmethod(
            lambda aio_id: {"component": "KurschartAIO", "subcomponent": "range_state", "aio_id": aio_id}
        )
        range_button = staticmethod(
            lambda aio_id, preset: {
                "component": "KurschartAIO",
                "subcomponent": "range_button",
                "aio_id": aio_id,
                "preset": preset,
            }
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
                    dcc.Store(id=self.ids.range_state(aio_id), data=dict(_DEFAULT_RANGE_STATE)),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Div("Zeitraum", className="text-body-secondary small mb-1"),
                                    dbc.ButtonGroup(
                                        [
                                            dbc.Button(
                                                preset,
                                                id=self.ids.range_button(aio_id, preset),
                                                size="sm",
                                                color="primary",
                                                outline=True,
                                                active=(preset == "Max"),
                                            )
                                            for preset in _RANGE_PRESET_ORDER
                                        ],
                                    ),
                                ],
                                xs=12,
                                className="mb-2",
                            ),
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
        Output(ids.range_state(MATCH), "data"),
        Output(ids.range_button(MATCH, "1M"), "active"),
        Output(ids.range_button(MATCH, "3M"), "active"),
        Output(ids.range_button(MATCH, "6M"), "active"),
        Output(ids.range_button(MATCH, "5J"), "active"),
        Output(ids.range_button(MATCH, "10J"), "active"),
        Output(ids.range_button(MATCH, "Max"), "active"),
        Input(ids.range_button(MATCH, "1M"), "n_clicks"),
        Input(ids.range_button(MATCH, "3M"), "n_clicks"),
        Input(ids.range_button(MATCH, "6M"), "n_clicks"),
        Input(ids.range_button(MATCH, "5J"), "n_clicks"),
        Input(ids.range_button(MATCH, "10J"), "n_clicks"),
        Input(ids.range_button(MATCH, "Max"), "n_clicks"),
        Input(ids.graph(MATCH), "relayoutData"),
        prevent_initial_call=True,
    )
    def _update_range_state(
        _click_1m: int | None,
        _click_3m: int | None,
        _click_6m: int | None,
        _click_5y: int | None,
        _click_10y: int | None,
        _click_max: int | None,
        relayout_data: dict[str, object] | None,
    ) -> tuple[object, ...]:
        if ctx.triggered_id is None:
            raise PreventUpdate

        aio_id = ctx.triggered_id["aio_id"]
        prices = KurschartAIO._providers[aio_id]()

        if ctx.triggered_id.get("subcomponent") == "range_button":
            preset = ctx.triggered_id["preset"]
            state = _range_state_for_preset(prices, preset)
        else:
            bounds = _parse_relayout_range(relayout_data)
            state = _range_state_payload(bounds, active_preset=None)

        active_flags = tuple(state["active_preset"] == preset for preset in _RANGE_PRESET_ORDER)
        return (state, *active_flags)

    @callback(
        Output(ids.graph(MATCH), "figure"),
        Output(ids.analysis_info(MATCH), "children"),
        Output(ids.y_scale(MATCH), "options"),
        Output(ids.log_hint(MATCH), "children"),
        Input(ids.y_scale(MATCH), "value"),
        Input(ids.regressions(MATCH), "value"),
        Input(ids.moving_averages(MATCH), "value"),
        Input(ids.drawdown_toggle(MATCH), "value"),
        Input(ids.range_state(MATCH), "data"),
        prevent_initial_call=True,
    )
    def _update_figure(
        y_scale_value: str,
        regression_labels: list[str] | None,
        ma_windows: list[int] | None,
        drawdown_selected: list[str] | None,
        range_state_data: dict[str, object] | None,
    ) -> tuple[go.Figure, list[Component], list[dict[str, object]], str]:
        if ctx.triggered_id is None:
            raise PreventUpdate

        aio_id = ctx.triggered_id["aio_id"]
        provider = KurschartAIO._providers[aio_id]
        prices = provider()

        visible_prices = _slice_to_range(prices, range_state_data)
        log_allowed = _is_log_allowed(visible_prices)
        effective_y_scale = y_scale_value if (y_scale_value != "log" or log_allowed) else "linear"

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
            visible_range=_range_bounds(range_state_data),
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


def _preset_range(prices: pd.Series, preset: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Berechnet den Zeitbereich fuer einen Schnellwahl-Button relativ zum letzten
    tatsaechlich verfuegbaren Datenpunkt der Reihe (nicht dem heutigen Datum),
    kalenderkorrekt ueber `pandas.DateOffset` (keine festen Tageszahlen). `None`
    bedeutet 'Max' (voller Bereich, kein expliziter Ausschnitt noetig)."""

    clean = pd.to_numeric(prices, errors="coerce").dropna().sort_index()
    if clean.empty:
        return None
    end = pd.Timestamp(clean.index.max())
    offset = _RANGE_PRESET_OFFSETS.get(preset)
    if offset is None:
        return None
    start = max(end - offset, pd.Timestamp(clean.index.min()))
    return start, end


def _range_state_for_preset(prices: pd.Series, preset: str) -> dict[str, object]:
    bounds = _preset_range(prices, preset)
    return _range_state_payload(bounds, active_preset=preset)


def _range_state_payload(
    bounds: tuple[pd.Timestamp, pd.Timestamp] | None, active_preset: str | None
) -> dict[str, object]:
    if bounds is None:
        return {"start": None, "end": None, "active_preset": active_preset}
    start, end = bounds
    return {"start": start.isoformat(), "end": end.isoformat(), "active_preset": active_preset}


def _parse_relayout_range(relayout_data: dict[str, object] | None) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Liest den vom Nutzer per Range-Slider-Drag gewaehlten Zeitausschnitt aus
    Plotlys relayoutData. `None`, wenn kein expliziter Ausschnitt enthalten ist
    (z. B. Autorange-Reset per Doppelklick)."""

    if not relayout_data:
        return None

    start = relayout_data.get("xaxis.range[0]") or relayout_data.get("xaxis2.range[0]")
    end = relayout_data.get("xaxis.range[1]") or relayout_data.get("xaxis2.range[1]")
    if start is None or end is None:
        range_pair = relayout_data.get("xaxis.range") or relayout_data.get("xaxis2.range")
        if isinstance(range_pair, list) and len(range_pair) == 2:
            start, end = range_pair
    if start is None or end is None:
        return None

    try:
        return pd.to_datetime(start, utc=True), pd.to_datetime(end, utc=True)
    except (ValueError, TypeError):
        return None


def _slice_to_range(prices: pd.Series, range_state_data: dict[str, object] | None) -> pd.Series:
    """Grenzt die (zuvor sortierte) Preisreihe auf den im chartState hinterlegten
    Zeitausschnitt ein. Die volle Reihe bleibt dabei unveraendert -- der
    Ausschnitt ist stets eine abgeleitete Ansicht."""

    sorted_prices = prices.sort_index()
    bounds = _range_bounds(range_state_data)
    if bounds is None:
        return sorted_prices
    start, end = bounds
    return sorted_prices[(sorted_prices.index >= start) & (sorted_prices.index <= end)]


def _range_bounds(range_state_data: dict[str, object] | None) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if not range_state_data:
        return None
    start, end = range_state_data.get("start"), range_state_data.get("end")
    if start is None or end is None:
        return None
    try:
        return pd.to_datetime(start, utc=True), pd.to_datetime(end, utc=True)
    except (ValueError, TypeError):
        return None


def _analysis_row(label: str, result: TrendResult, prices: pd.Series) -> Component:
    clean = prices.dropna()
    period = f"{clean.index.min():%Y-%m-%d} - {clean.index.max():%Y-%m-%d}" if not clean.empty else "n/v"
    params_text = ", ".join(f"{key}={value:.4g}" for key, value in result.params.items())
    return html.Div(
        f"{label}: R²={result.r_squared:.3f}, n={len(clean)}, Zeitraum {period}, Parameter ({params_text})",
        className="mb-1",
    )

"""Kennzahlen-Baustein: letzter Kurs, Renditen, Volatilitaet, Sharpe, Drawdown, VaR/ES.
Statisch pro Aufruf (keine Interaktion), aber mit AIO-Dict-IDs fuer Konsistenz und
kuenftige Erweiterung (siehe CLAUDE.md: 'UI-Bausteine folgen dem AIO-Muster')."""

from __future__ import annotations

import uuid

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html

from findash.analytics.drawdown import drawdown_series
from findash.analytics.returns import annualized_return, simple_returns
from findash.analytics.risk import annualized_volatility, expected_shortfall, sharpe_ratio, value_at_risk


class KennzahlenAIO(dbc.Card):
    class ids:
        card = staticmethod(lambda aio_id: {"component": "KennzahlenAIO", "subcomponent": "card", "aio_id": aio_id})

    def __init__(
        self,
        prices: pd.Series,
        periods_per_year: int = 252,
        risk_free_rate: float = 0.0,
        var_confidence: float = 0.95,
        aio_id: str | None = None,
    ) -> None:
        aio_id = aio_id or str(uuid.uuid4())
        rows = _build_rows(prices, periods_per_year, risk_free_rate, var_confidence)
        super().__init__(
            id=self.ids.card(aio_id),
            className="mb-3",
            children=dbc.CardBody(
                dbc.Row(
                    [
                        dbc.Col(
                            [html.Div(label, className="text-body-secondary small"), html.Div(value, className="fs-5")],
                            xs=6,
                            md=3,
                            className="mb-2",
                        )
                        for label, value in rows
                    ]
                )
            ),
        )


def _build_rows(
    prices: pd.Series, periods_per_year: int, risk_free_rate: float, var_confidence: float
) -> list[tuple[str, str]]:
    clean = pd.to_numeric(prices, errors="coerce").dropna()
    if clean.empty:
        return [("Letzter Kurs", "keine Daten")]

    last_price = float(clean.iloc[-1])
    last_date = clean.index[-1]
    change = float(clean.iloc[-1] / clean.iloc[-2] - 1.0) if len(clean) >= 2 else float("nan")

    simple = simple_returns(clean)
    high = float(clean.max())
    low = float(clean.min())
    dd = drawdown_series(clean)
    max_drawdown_pct = float(dd["drawdown_pct"].min()) if not dd.empty else float("nan")

    return [
        ("Letzter Kurs", f"{last_price:,.2f} ({last_date:%Y-%m-%d})"),
        ("Veraenderung zum Vorwert", _pct(change)),
        ("Rendite 1J", _pct(_trailing_return(clean, periods_per_year))),
        ("Annualisierte Rendite", _pct(annualized_return(simple, periods_per_year))),
        ("Annualisierte Volatilitaet", _pct(annualized_volatility(simple, periods_per_year))),
        ("Sharpe Ratio", _num(sharpe_ratio(simple, periods_per_year, risk_free_rate))),
        ("Max. Drawdown", _pct_from_percent(max_drawdown_pct)),
        ("Hoch/Tief im Zeitraum", f"{high:,.2f} / {low:,.2f}"),
        (f"VaR {int(var_confidence * 100)}%", _pct(value_at_risk(simple, var_confidence))),
        (f"Expected Shortfall {int(var_confidence * 100)}%", _pct(expected_shortfall(simple, var_confidence))),
    ]


def _trailing_return(prices: pd.Series, periods_per_year: int) -> float:
    if len(prices) <= periods_per_year:
        return float("nan")
    return float(prices.iloc[-1] / prices.iloc[-periods_per_year - 1] - 1.0)


def _pct(value: float) -> str:
    return "n/v" if value != value else f"{value * 100.0:.2f}%"


def _pct_from_percent(value: float) -> str:
    return "n/v" if value != value else f"{value:.2f}%"


def _num(value: float) -> str:
    return "n/v" if value != value else f"{value:.2f}"

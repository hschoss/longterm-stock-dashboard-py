"""Sparplan-Simulation ueber die Zeit: Einzahlungen vs. Depotwert. Anders als
triangle.savings_plan_return_triangle (eine Rendite je Kauf/Verkaufsjahr-Paar) liefert
das hier eine Zeitreihe fuer genau einen Start, eine Rate und eine Dauer."""

from __future__ import annotations

from typing import Literal

import pandas as pd

ContributionFrequency = Literal["monthly", "yearly"]

_RESAMPLE_RULE = {"monthly": "MS", "yearly": "YS"}


def simulate_savings_plan(
    prices: pd.Series,
    contribution: float,
    frequency: ContributionFrequency,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Kauft an jedem Beitragstermin zwischen start und end fuer `contribution` Einheiten
    zum naechsten verfuegbaren Kurs am oder nach dem Termin. Liefert je Beitragstermin
    cumulative_deposits und portfolio_value (zum Kurs am selben Termin)."""

    clean = pd.to_numeric(prices, errors="coerce").dropna().sort_index()
    if clean.empty:
        return pd.DataFrame(columns=["cumulative_deposits", "portfolio_value"])

    contribution_dates = pd.date_range(start=start, end=end, freq=_RESAMPLE_RULE[frequency], tz=clean.index.tz)

    units_held = 0.0
    deposits = 0.0
    records: list[dict[str, object]] = []
    for contribution_date in contribution_dates:
        eligible_prices = clean.loc[clean.index >= contribution_date]
        if eligible_prices.empty:
            break
        price_at_purchase = float(eligible_prices.iloc[0])
        if price_at_purchase <= 0:
            continue

        units_held += contribution / price_at_purchase
        deposits += contribution
        records.append(
            {
                "ts": eligible_prices.index[0],
                "cumulative_deposits": deposits,
                "portfolio_value": units_held * price_at_purchase,
            }
        )

    return (
        pd.DataFrame.from_records(records).set_index("ts")
        if records
        else pd.DataFrame(columns=["cumulative_deposits", "portfolio_value"])
    )

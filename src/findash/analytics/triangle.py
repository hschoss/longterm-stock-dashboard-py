"""Renditedreiecke: Kaufjahr x Verkaufsjahr -> annualisierte Rendite.

Rechenaufwand ist quadratisch in der Anzahl der Jahre; laut docs/auftrag.md ("Rechen-
aufwand") wird das im Nachtjob vorberechnet (findash jobs analytics, noch nicht
verdrahtet) und nicht bei jedem Seitenaufruf. Die Funktionen hier sind bewusst reine
Funktionen, damit sie sowohl vom Batch als auch in Tests ohne Datenbank aufrufbar
sind."""

from __future__ import annotations

import pandas as pd

from findash.analytics.irr import internal_rate_of_return


def _year_end_prices(prices: pd.Series) -> pd.Series:
    clean = pd.to_numeric(prices, errors="coerce").dropna()
    return clean.groupby(clean.index.year).last()


def lump_sum_return_triangle(prices: pd.Series) -> pd.DataFrame:
    """matrix.loc[buy_year, sell_year] = CAGR einer Einmalanlage. Nur die obere
    Dreieckshaelfte (sell_year > buy_year) ist befuellt, der Rest bleibt NaN."""

    year_end = _year_end_prices(prices)
    years = sorted(year_end.index)
    matrix = pd.DataFrame(index=years, columns=years, dtype=float)

    for buy_year in years:
        start_price = float(year_end.loc[buy_year])
        if start_price <= 0:
            continue
        for sell_year in years:
            if sell_year <= buy_year:
                continue
            end_price = float(year_end.loc[sell_year])
            matrix.loc[buy_year, sell_year] = (end_price / start_price) ** (1.0 / (sell_year - buy_year)) - 1.0

    return matrix


def savings_plan_return_triangle(prices: pd.Series, contribution: float = 1.0) -> pd.DataFrame:
    """matrix.loc[buy_year, sell_year] = interner Zinsfuss eines Sparplans mit einer
    Einzahlung von `contribution` zu Beginn jedes Jahres von buy_year bis
    sell_year - 1, verkauft am Jahresende von sell_year."""

    year_end = _year_end_prices(prices)
    years = sorted(year_end.index)
    matrix = pd.DataFrame(index=years, columns=years, dtype=float)

    for buy_year in years:
        for sell_year in years:
            if sell_year <= buy_year:
                continue
            contribution_years = list(range(buy_year, sell_year))
            contribution_prices = year_end.loc[contribution_years]
            if contribution_prices.isna().any() or (contribution_prices <= 0).any():
                continue

            units = float((contribution / contribution_prices).sum())
            final_value = units * float(year_end.loc[sell_year])

            amounts = [-contribution] * len(contribution_years) + [final_value]
            cashflow_years = [year - buy_year for year in contribution_years] + [sell_year - buy_year]
            matrix.loc[buy_year, sell_year] = internal_rate_of_return(amounts, cashflow_years)

    return matrix

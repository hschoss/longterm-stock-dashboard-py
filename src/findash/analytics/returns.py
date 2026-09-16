"""Einfache und logarithmische Renditen sowie Kennzahlen dazu. Reine Funktionen auf
pd.Series (Preise, indiziert nach Zeit) -- kein DB-, kein Dash-Bezug (siehe
docs/kennzahlen.md fuer die Formeln)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def simple_returns(prices: pd.Series) -> pd.Series:
    """r_t = P_t / P_(t-1) - 1"""

    return prices.pct_change().rename("simple_return")


def log_returns(prices: pd.Series) -> pd.Series:
    """r_t = ln(P_t / P_(t-1))"""

    numeric = pd.to_numeric(prices, errors="coerce")
    return np.log(numeric / numeric.shift(1)).rename("log_return")


def annualized_return(returns: pd.Series, periods_per_year: int) -> float:
    """Geometrische Annualisierung: (Produkt(1+r))^(Perioden/Jahr / n) - 1."""

    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    growth = float((1.0 + clean).prod())
    years = len(clean) / periods_per_year
    if years <= 0 or growth <= 0:
        return float("nan")
    return float(growth ** (1.0 / years) - 1.0)


def annual_returns(prices: pd.Series) -> pd.Series:
    """Ein Renditewert je Kalenderjahr: letzter Kurs des Jahres / letzter Kurs des
    Vorjahres - 1. Das erste Jahr der Reihe hat keinen Vorjahreswert und wird
    ausgelassen. Basis fuer Balkendiagramm, Histogramm und Renditedreieck."""

    clean = prices.dropna()
    if clean.empty:
        return pd.Series(dtype=float, name="annual_return")

    year_end = clean.groupby(clean.index.year).last()
    returns = year_end.pct_change().dropna()
    returns.index.name = "year"
    return returns.rename("annual_return")


def cagr_between(prices: pd.Series, start_year: int, end_year: int) -> float:
    """Annualisierte Rendite (CAGR) zwischen den Jahresendkursen von start_year und
    end_year (end_year > start_year). NaN, wenn einer der beiden Jahresendkurse fehlt."""

    if end_year <= start_year:
        raise ValueError("end_year muss groesser als start_year sein.")

    clean = prices.dropna()
    year_end = clean.groupby(clean.index.year).last()
    if start_year not in year_end.index or end_year not in year_end.index:
        return float("nan")

    start_price = float(year_end.loc[start_year])
    end_price = float(year_end.loc[end_year])
    if start_price <= 0:
        return float("nan")

    years = end_year - start_year
    return float((end_price / start_price) ** (1.0 / years) - 1.0)

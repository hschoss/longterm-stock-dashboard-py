"""Rollierende annualisierte Renditen ueber mehrjaehrige Fenster."""

from __future__ import annotations

import pandas as pd


def rolling_annualized_return(prices: pd.Series, window_years: int) -> pd.Series:
    """Fuer jeden Tag t: annualisierte Rendite von t - window_years bis t, basierend
    auf dem jeweils naechstgelegenen verfuegbaren Kurs vor window_years Jahren.
    Zeitpunkte ohne Vorgaenger im Fenster bleiben NaN."""

    clean = pd.to_numeric(prices, errors="coerce").dropna()
    if clean.empty:
        return pd.Series(dtype=float, name=f"rolling_return_{window_years}y")

    window_days = window_years * 365.25
    window = pd.Timedelta(round(window_days * 86_400), unit="s")
    minimum_gap = pd.Timedelta(round(window_days * 0.95 * 86_400), unit="s")
    shifted_index = clean.index.searchsorted(clean.index - window, side="left")
    values = clean.to_numpy(dtype=float)

    result = pd.Series(float("nan"), index=clean.index, name=f"rolling_return_{window_years}y")
    for position, start_position in enumerate(shifted_index):
        if start_position >= position or start_position >= len(values):
            continue
        start_date = clean.index[start_position]
        if (clean.index[position] - start_date) < minimum_gap:
            continue
        start_price = values[start_position]
        end_price = values[position]
        if start_price <= 0:
            continue
        result.iloc[position] = (end_price / start_price) ** (1.0 / window_years) - 1.0

    return result

"""Interner Zinsfuss (IRR) fuer Cashflow-Reihen, ohne Zusatzabhaengigkeit wie
numpy-financial. Wird fuer die Sparplan-Variante des Renditedreiecks gebraucht
(docs/plan.md Checkliste: 'Renditedreieck fuer Sparplaene')."""

from __future__ import annotations

import numpy as np


def _npv(rate: float, amounts: np.ndarray, years: np.ndarray) -> float:
    return float(np.sum(amounts / np.power(1.0 + rate, years)))


def internal_rate_of_return(amounts: list[float], years: list[float]) -> float:
    """amounts/years gleich lang; amounts[i] ist der Cashflow zum Zeitpunkt years[i]
    in Jahren seit dem ersten Cashflow (years[0] == 0). Einzahlungen negativ,
    Endwert positiv. Loest NPV(rate) = 0 per Bisektion im Bereich [-0.99, 10.0].
    Gibt NaN zurueck, wenn keine Nullstelle in diesem Bereich liegt."""

    if len(amounts) != len(years):
        raise ValueError("amounts und years muessen gleich lang sein.")
    if len(amounts) < 2:
        raise ValueError("Mindestens zwei Cashflows werden fuer eine IRR benoetigt.")

    amounts_arr = np.asarray(amounts, dtype=float)
    years_arr = np.asarray(years, dtype=float)

    low, high = -0.99, 10.0
    npv_low, npv_high = _npv(low, amounts_arr, years_arr), _npv(high, amounts_arr, years_arr)
    if np.sign(npv_low) == np.sign(npv_high):
        return float("nan")

    for _ in range(200):
        mid = (low + high) / 2.0
        npv_mid = _npv(mid, amounts_arr, years_arr)
        if abs(npv_mid) < 1e-9:
            return float(mid)
        if np.sign(npv_mid) == np.sign(npv_low):
            low, npv_low = mid, npv_mid
        else:
            high = mid

    return float((low + high) / 2.0)

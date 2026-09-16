"""Normalisierung und Ausrichtung mehrerer Preisreihen fuer die Vergleichsseite.
Verallgemeinert den alten Zwei-Asset-Vergleich (app/services/stats_service.py) auf
beliebig viele Assets (docs/auftrag.md Abschnitt 8.1: '/vergleich' -- beliebig viele
Assets, bisher nur zwei)."""

from __future__ import annotations

import pandas as pd


def normalize_to_100(prices: pd.Series) -> pd.Series:
    """Skaliert eine Preisreihe so, dass der erste gueltige, positive Wert 100 ist."""

    clean = pd.to_numeric(prices, errors="coerce")
    clean = clean[clean > 0].dropna()
    if len(clean) < 1:
        raise ValueError("Mindestens ein positiver Preispunkt wird benoetigt.")
    base = float(clean.iloc[0])
    return (prices / base * 100.0).rename("normalized")


def align_series(series_by_label: dict[str, pd.Series]) -> pd.DataFrame:
    """Schneidet mehrere zeitindizierte Reihen auf ihren gemeinsamen Zeitraum
    (inner join auf dem Index) und normalisiert jede auf den Startwert 100."""

    if len(series_by_label) < 2:
        raise ValueError("Mindestens zwei Reihen werden fuer einen Vergleich benoetigt.")

    frame = pd.DataFrame(series_by_label).dropna(how="any")
    if len(frame) < 2:
        raise ValueError("Es gibt keinen ausreichenden gemeinsamen Zeitraum fuer den Vergleich.")

    normalized = frame.apply(lambda column: normalize_to_100(column))
    return normalized

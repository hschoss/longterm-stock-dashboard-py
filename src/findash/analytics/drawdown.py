"""Drawdown und Erholungsdauer."""

from __future__ import annotations

import pandas as pd


def drawdown_series(prices: pd.Series) -> pd.DataFrame:
    """Liefert running_max und drawdown_pct (<= 0) je Zeitpunkt."""

    clean = pd.to_numeric(prices, errors="coerce").dropna()
    if clean.empty:
        return pd.DataFrame(columns=["running_max", "drawdown_pct"])

    running_max = clean.cummax()
    drawdown_pct = (clean / running_max - 1.0) * 100.0
    return pd.DataFrame({"running_max": running_max, "drawdown_pct": drawdown_pct})


def recovery_periods(prices: pd.Series) -> pd.DataFrame:
    """Findet je Tiefpunkt (lokales Minimum unterhalb des bisherigen Hochs) das Datum
    des Tiefs, den Drawdown in Prozent und -- falls die Reihe wieder ueber das alte
    Hoch steigt -- das Erholungsdatum und die Erholungsdauer in Tagen. Ist ein
    Tiefpunkt noch nicht erholt, bleiben recovery_date/recovery_days NaT/NaN (nicht
    erfunden)."""

    dd = drawdown_series(prices)
    if dd.empty:
        return pd.DataFrame(columns=["trough_date", "drawdown_pct", "recovery_date", "recovery_days"])

    is_new_high = dd["drawdown_pct"] >= -1e-9
    drawdown_episode = (is_new_high != is_new_high.shift(fill_value=True)).cumsum()
    episodes = dd[~is_new_high].groupby(drawdown_episode[~is_new_high])

    records: list[dict[str, object]] = []
    for _, episode in episodes:
        trough_date = episode["drawdown_pct"].idxmin()
        trough_value = float(episode["drawdown_pct"].loc[trough_date])
        after_trough = dd.loc[trough_date:]
        recovered = after_trough[after_trough["drawdown_pct"] >= -1e-9]
        recovery_date = recovered.index[0] if not recovered.empty else pd.NaT
        recovery_days = (recovery_date - trough_date).days if pd.notna(recovery_date) else float("nan")
        records.append(
            {
                "trough_date": trough_date,
                "drawdown_pct": trough_value,
                "recovery_date": recovery_date,
                "recovery_days": recovery_days,
            }
        )

    return pd.DataFrame.from_records(records)

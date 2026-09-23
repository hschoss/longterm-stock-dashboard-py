"""Risikokennzahlen: Volatilitaet, Sharpe Ratio, VaR, Expected Shortfall."""

from __future__ import annotations

import numpy as np
import pandas as pd


def annualized_volatility(returns: pd.Series, periods_per_year: int) -> float:
    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    return float(clean.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(returns: pd.Series, periods_per_year: int, risk_free_rate: float = 0.0) -> float:
    """Risikofreier Satz ist eine jaehrliche Rate, Standard 0 (config/analytics.yaml)."""

    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    excess = clean - risk_free_rate / periods_per_year
    volatility = excess.std(ddof=1)
    if not volatility:
        return float("nan")
    return float(excess.mean() / volatility * np.sqrt(periods_per_year))


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historische VaR als positive Verlustzahl (z. B. 0.03 = 3 % Verlust)."""

    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    return float(-np.percentile(clean.to_numpy(dtype=float), (1.0 - confidence) * 100.0))


def expected_shortfall(returns: pd.Series, confidence: float = 0.95) -> float:
    """Mittelwert der Verluste jenseits des VaR (CVaR), als positive Zahl."""

    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    threshold = np.percentile(clean.to_numpy(dtype=float), (1.0 - confidence) * 100.0)
    tail = clean[clean <= threshold]
    if tail.empty:
        return float("nan")
    return float(-tail.mean())


def rolling_annualized_volatility(returns: pd.Series, window: int, periods_per_year: int) -> pd.Series:
    """Annualisierte Volatilitaet ueber ein gleitendes Fenster von `window`
    Beobachtungen (docs/auftrag.md Abschnitt 8.2: 'Rollierende annualisierte
    Volatilitaet'). NaN, solange das Fenster noch nicht voll ist."""

    clean = returns.dropna()
    if clean.empty:
        return pd.Series(dtype=float, name="rolling_volatility")
    rolling_std = clean.rolling(window=window, min_periods=window).std(ddof=1)
    return (rolling_std * np.sqrt(periods_per_year)).rename("rolling_volatility")

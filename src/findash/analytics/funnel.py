"""Rendite-Spannweite nach Haltedauer (Min/Median/Max-'Trichter').

Baut auf analytics.rolling auf: fuer jede Haltedauer wird die Verteilung der
rollierenden annualisierten Renditen ausgewertet."""

from __future__ import annotations

import pandas as pd

from findash.analytics.rolling import rolling_annualized_return


def holding_period_return_stats(prices: pd.Series, holding_years: list[int]) -> pd.DataFrame:
    """Eine Zeile je Haltedauer mit min/median/max annualisierter Rendite und dem
    Anteil der Zeitraeume mit negativer Rendite (share_negative, 0..1)."""

    records: list[dict[str, float]] = []
    for years in sorted(set(holding_years)):
        rolling = rolling_annualized_return(prices, years).dropna()
        if rolling.empty:
            records.append(
                {
                    "holding_years": years,
                    "min_return": float("nan"),
                    "median_return": float("nan"),
                    "max_return": float("nan"),
                    "share_negative": float("nan"),
                }
            )
            continue

        records.append(
            {
                "holding_years": years,
                "min_return": float(rolling.min()),
                "median_return": float(rolling.median()),
                "max_return": float(rolling.max()),
                "share_negative": float((rolling < 0).mean()),
            }
        )

    return pd.DataFrame.from_records(records)

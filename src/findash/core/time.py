"""Zeitzonen-Helfer. Intern wird ausschliesslich UTC gespeichert, Anzeige erfolgt in
DISPLAY_TIMEZONE (siehe Settings.display_timezone)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd


def to_display_timezone(moment: datetime, timezone: str) -> datetime:
    """Wandelt einen zeitzonenbewussten Zeitpunkt in die Anzeige-Zeitzone um."""

    if moment.tzinfo is None:
        raise ValueError("moment muss zeitzonenbewusst sein (UTC erwartet).")
    return moment.astimezone(ZoneInfo(timezone))


def to_display_series(series: pd.Series, timezone: str) -> pd.Series:
    """Wandelt eine UTC-datetime64-Spalte in die Anzeige-Zeitzone um."""

    if series.dt.tz is None:
        raise ValueError("series muss zeitzonenbewusst sein (UTC erwartet).")
    return series.dt.tz_convert(ZoneInfo(timezone))

"""Laendergewichtung je Index fuer die Weltkarte.

Liest vorlaeufig noch aus den aufbereiteten CSV-Dateien unter
data/index_constituents/aggregated/, weil die Migration nach ref.index_country_exposure
(siehe storage.tables.IndexCountryExposure) noch aussteht (docs/plan.md, Abschnitt 6:
Indexbestandteile-CSVs werden einmalig migriert, dann geloescht). Der Aufrufer
(app/figures/world_map.py) kennt nur diese Funktion, nicht die CSV-Quelle -- die
Migration auf DB-Lesen aendert also nur diese Datei."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
AGGREGATED_DIR = PROJECT_ROOT / "data" / "index_constituents" / "aggregated"
ALL_INDICES_FILE = AGGREGATED_DIR / "all_indices_country_counts.csv"


def load_all_index_country_exposure() -> pd.DataFrame:
    if not ALL_INDICES_FILE.exists():
        raise FileNotFoundError(f"Laenderdaten fehlen: {ALL_INDICES_FILE}")
    return pd.read_csv(ALL_INDICES_FILE)

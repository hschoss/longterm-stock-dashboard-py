# Architektur des Findash-Dashboards

Dieses Dokument beschreibt den **aktuellen** Stand nach der Restrukturierung auf das
Bausteinsystem aus `docs/plan.md`. Der Vorgänger-Stand (Flask + eingebettete Dash-SPA,
`app/`-Paket) ist vollständig entfernt; siehe `docs/entscheidungen.md`,
Abschnitt „Restrukturierung", für die Begründung und den Zeitpunkt.

## 1. Überblick

```
Browser
  │
  ▼
Dash-App (src/findash/app/main.py) — Dash Pages + dash-bootstrap-components
  ├── app/pages/      Übersicht ('/'), Rückschau ('/rueckschau/<symbol>')
  ├── app/blocks/     AIO-Bausteine (Kennzahlen, Kurschart, Datenqualität, Drawdown)
  ├── app/figures/    reine DataFrame → go.Figure Funktionen
  └── app/data_access.py   einzige, nur lesende Verbindung zu storage/
        │
        ▼
  analytics/   reine Berechnungsfunktionen (kein DB-, kein Dash-Bezug)
        │
        ▼
  storage/     SQLAlchemy-Tabellen, Engine/Session, Repositories (einzige Stelle mit SQL)
        │
        ▼
  PostgreSQL (Schemas ref/staging/market/analytics/ops)
```

Daneben: `jobs/` (CLI-Jobs, aktuell nur `seed-demo`), `cli.py` (Typer-Einstiegspunkt
`findash`), sowie die noch leeren Platzhalterpakete `sync/` (Phase 2) und
`forecasting/` (Phase 5/6).

Import-Richtung ist über `import-linter`-Contracts in `pyproject.toml` erzwungen:
`core` importiert nichts Eigenes, `storage`/`analytics` importieren nur `core`,
`app` importiert `core`/`storage`/`analytics`, aber nie `jobs`/`sync`/`forecasting`.

## 2. Tech-Stack

- **Dash** mit `use_pages=True`, **dash-bootstrap-components** (Bootstrap 5.3-Theme
  über `dash-bootstrap-templates`) — die gesamte UI, keine Flask-Schicht mehr
- **SQLAlchemy 2.x** (ORM) + **psycopg 3** — einzige DB-Anbindung
- **Alembic** — Schema-Migrationen (`src/findash/storage/migrations/`)
- **pandas / numpy** — Analytics
- **Plotly** (`graph_objects`) — Chart-/Karten-Rendering
- **pydantic / pydantic-settings** — `.env`- und YAML-Validierung
- **Typer** — CLI (`findash`)
- **gunicorn** — WSGI-Server im Container
- **uv** — Abhängigkeits- und venv-Verwaltung, `pyproject.toml` mit `src`-Layout
- **pytest, ruff, mypy, import-linter, pre-commit** — Qualitätssicherung

## 3. Verzeichnisstruktur

```
config/
  assets.yaml        getrackte Instrumente (Gold + 6 ETFs), inkl. Farbe/Region/
                      optionalem index_constituent_key für die Weltkarte
  analytics.yaml      Fenster, Konfidenzniveaus, Perioden pro Jahr

src/findash/
  core/               Settings, Domänentypen (Frequency, TrendType, QualityStatus,
                      JobStatus, YScale), Zeitzonen-Helfer, JSON-Logging,
                      YAML-Konfigurationsmodelle
  storage/
    tables.py          SQLAlchemy-ORM-Tabellen (ref/market/analytics/ops)
    db.py               Engine/Session (kein Flask-Bezug)
    repositories/       assets.py, prices.py, index_constituents.py, job_runs.py
    migrations/         Alembic env.py + versions/
  analytics/          ein reines Modul je Diagrammtyp: returns, risk, regression,
                      resample, comparison, drawdown, rolling, funnel, irr,
                      triangle, savings_plan
  app/
    main.py             Dash-Instanz, `server` für gunicorn, /healthz
    data_access.py       einzige, nur lesende Schnittstelle app → storage
    pages/               home.py ('/'), rueckschau.py ('/rueckschau/<symbol>')
    blocks/              AIO-Bausteine: kennzahlen, kurschart, datenqualitaet, drawdown
    figures/             ein reiner Figure-Builder je Diagrammtyp (siehe Abschnitt 5)
  jobs/                seed_demo.py (deterministische Demo-Kurse)
  sync/                leer, Phase 2
  forecasting/         leer, Phase 5/6
  cli.py                Typer-App `findash`

data/
  index_constituents/  weiterhin CSV-Quelle für die Weltkarte (Migration nach
                       ref.index_country_exposure steht aus, siehe docs/plan.md §6)

scripts/
  clean_index_constituents.py   Offline-Aufbereitung der Rohdaten zu den obigen CSVs

tests/
  unit/                DB- und Dash-freie Tests (analytics/, figures/)
  integration/          berührt echte Dateien (Aufbereitungsskript, Weltkarte)

docker/Dockerfile, docker-compose.yml, alembic.ini, pyproject.toml, uv.lock
```

## 4. Kernkomponenten

### 4.1 `core/`

- `settings.py`: `pydantic-settings`, liest `.env` (`DATABASE_URL`,
  `SOURCE_DATABASE_URL`, `DISPLAY_TIMEZONE`, Pfade zu den YAML-Configs, …).
- `domain.py`: `StrEnum`-Typen, die schichtübergreifend verwendet werden
  (`Frequency`, `PriceField`, `YScale`, `TrendType`, `QualityStatus`, `JobStatus`).
- `config_models.py`: `AssetConfig`/`AssetsConfig` und `AnalyticsConfig` validieren
  `config/assets.yaml` bzw. `config/analytics.yaml`.
- `time.py`, `logging.py`: Zeitzonen-Konvertierung UTC → `DISPLAY_TIMEZONE`, JSON-Logging.

### 4.2 `storage/`

- `tables.py`: `Asset` (`ref.assets`), `IndexCountryExposure`
  (`ref.index_country_exposure`, noch ungenutzt, Zielschema für die CSV-Migration),
  `Price` (`market.prices`), `Metric` (`analytics.metrics`), `JobRun`/`JobRunItem`/
  `SyncState` (`ops.*`).
- `db.py`: `build_engine`/`build_session_factory`/`session_scope` — bewusst ohne
  Flask-`g`-Bindung, da die App keine Request-Session mehr braucht.
- `repositories/`: `assets.py` (Lesen + Upsert aus `config/assets.yaml`),
  `prices.py` (Lesen als DataFrame + idempotenter Upsert, genutzt von
  `seed-demo` und künftig vom Sync), `index_constituents.py` (liest aktuell noch
  die CSV unter `data/index_constituents/aggregated/`), `job_runs.py` (letzter
  erfolgreicher Lauf je `job_type`, für Statusleiste/Datenqualitäts-Baustein).
- Migration `0001_initial_schema.py` legt die Schemas `ref`/`staging`/`market`/
  `analytics`/`ops` sowie deren Tabellen an. `staging` bleibt vorerst ohne Tabellen
  (Struktur hängt vom noch unbekannten Quellschema ab, siehe `docs/plan.md` §8).

### 4.3 `analytics/`

Reine Funktionen auf `pd.Series`/`pd.DataFrame`, kein Dash-, kein DB-Import (per
import-linter-Contract erzwungen):

| Modul | Deckt ab |
|---|---|
| `returns.py` | einfache/log-Renditen, Annualisierung, Jahresrenditen, CAGR zwischen zwei Jahren |
| `risk.py` | Volatilität, Sharpe Ratio, VaR, Expected Shortfall |
| `regression.py` | **eine** Trendregression (linear/exponentiell/log2) mit Abweichung vom Trend — löst die alten drei Parallel-Implementierungen ab |
| `resample.py` | OHLCV-Resampling (W/ME/QE/YE) |
| `comparison.py` | Normalisierung auf 100, Ausrichtung beliebig vieler Reihen (verallgemeinert den alten Zwei-Asset-Vergleich) |
| `drawdown.py` | Drawdown-Serie, Tiefpunkte + Erholungsdauer |
| `rolling.py` | rollierende annualisierte Rendite über ein Fenster in Jahren |
| `funnel.py` | Min/Median/Max-Rendite-Spannweite nach Haltedauer |
| `irr.py` | interner Zinsfuß per Bisektion (ohne Zusatzabhängigkeit) |
| `triangle.py` | Renditedreieck Einmalanlage und Sparplan (Kauf-/Verkaufsjahr-Matrix) |
| `savings_plan.py` | Sparplan-Simulation über die Zeit (Einzahlungen vs. Depotwert) |

Rechenintensive Funktionen (`triangle.py`, `funnel.py`, `savings_plan.py` in der
Matrix-Form) sind bewusst als aufrufbare, reine Funktionen gebaut, aber noch **nicht**
in einen Nachtjob eingebunden — das ist für Phase 4 vorgesehen.

### 4.4 `app/`

- **`main.py`**: erstellt die `Dash`-Instanz (`use_pages=True`,
  `dash.bootstrap.themes.BOOTSTRAP`), registriert Navbar + Statusleiste
  (zeigt „kein Sync-Lauf vorhanden", solange Phase 2 fehlt) und stellt über
  `server` (Flask, von Dash verwaltet) `/healthz` bereit.
- **`data_access.py`**: die einzige Stelle, an der `app/` `storage/` berührt —
  kurzlebige Sessions, reine Rückgabe von DataFrames/Dicts, kein Schreiben.
- **`pages/home.py`** (`/`): Asset-Karten-Raster (Mini-Chart, letzter Kurs,
  Veränderung) plus Weltkarte der Länder-Exposure (Dropdown für Index/Metrik).
- **`pages/rueckschau.py`** (`/rueckschau/<asset_symbol>`): kombiniert
  `KennzahlenAIO`, `KurschartAIO`, `DrawdownAIO`, `DatenqualitaetAIO` für ein Asset.
- **`blocks/`**: AIO-Muster mit Dictionary-IDs
  (`{"component": ..., "subcomponent": ..., "aio_id": ...}`). `KurschartAIO` ist die
  Referenz für einen interaktiven Baustein mit einem einmal auf Klassenebene
  registrierten `MATCH`-Callback; `KennzahlenAIO`/`DatenqualitaetAIO`/`DrawdownAIO`
  sind statische Bausteine ohne eigenen Callback.
- **`figures/`**: pro Diagrammtyp aus der Checkliste eine reine Funktion
  `... -> go.Figure`, die bei leeren/fehlenden Daten eine Platzhalter-Figur statt
  eines Fehlers liefert (`_common.empty_figure`). `world_map.py` ist die migrierte
  Choroplethen-Karte, liest aber weiterhin über `storage.repositories
  .index_constituents` aus CSV.

### 4.5 `jobs/` und `cli.py`

- `findash seed-demo`: erzeugt für jedes Asset aus `config/assets.yaml`
  deterministische, synthetische Tageskurse (fester Seed je Asset-Index) und
  schreibt sie über `upsert_price_rows` nach `market.prices` — die App läuft damit
  ohne Quelldatenbank.
- `findash sync check|run|full`, `findash jobs nightly|analytics`: als
  Typer-Befehle angelegt, brechen aber mit einer klaren Meldung ab, solange die
  Zugangsdaten zur Quelldatenbank (`docs/plan.md` §8) fehlen bzw. Phase 4+ nicht
  umgesetzt ist.

## 5. Datenfluss: `findash seed-demo`

1. `config/assets.yaml` wird geladen und validiert (`AssetsConfig`).
2. Je Asset: `upsert_asset_from_config` legt die Zeile in `ref.assets` an/aktualisiert
   sie (natürlicher Schlüssel: `symbol`).
3. `_synthetic_daily_frame` erzeugt eine geometrische Brownsche Bewegung als
   Platzhalter-Kursreihe (kein Netzwerkzugriff, keine echten Marktdaten).
4. `upsert_price_rows` schreibt die Reihe idempotent nach `market.prices`
   (Schlüssel `asset_id, frequency, ts`).

Der künftige `findash sync run` (Phase 2) wird an derselben Stelle ansetzen
(`upsert_price_rows`), nur mit Daten aus der Quelldatenbank statt Zufallszahlen,
plus Validierung und Wasserzeichen (`docs/plan.md` §5.3).

## 6. Bekannte offene Punkte

- **Quelldatenbank-Zugangsdaten fehlen** (`docs/plan.md` §8) — blockiert `sync/`
  und damit den nächtlichen Batch vollständig.
- **Weltkarten-Daten kommen noch aus CSV**, nicht aus `ref.index_country_exposure`
  (Tabelle existiert bereits, Migrationsskript fehlt noch).
- **Vergleichsseite (`/vergleich`) und Vorschau-Seite (`/vorschau/<asset>`)
  existieren noch nicht** — `analytics/comparison.py` ist bereits auf beliebig
  viele Assets ausgelegt, es fehlt nur die Seite/der Baustein dafür.
- **Rechenintensive Analytics (Renditedreieck, Trichter, Sparplan-Matrix) laufen
  noch nicht im Nachtjob**, sondern müssten aktuell live berechnet werden, wenn man
  sie in eine Seite einbaut — das widerspricht dem Leitprinzip „Web-App rechnet
  nicht schwer" und ist für Phase 4 vorgesehen.

# Architektur des Longterm Stock Dashboards

Dieses Dokument beschreibt den **aktuellen, im Code vorgefundenen** Zustand der Anwendung
(Stand: dieser Commit). Es unterscheidet sich an mehreren Stellen bewusst von der
ursprünglichen Zielarchitektur in `architecture-goal.md` — die wichtigsten Abweichungen
sind am Ende dokumentiert.

## 1. Überblick

Die Anwendung ist eine **Flask-App**, deren eigentliche Oberfläche eine darin eingebettete
**Dash-Single-Page-App** ist. Flask übernimmt nur noch das App-Factory-Setup, die
Datenbank-Session-Verwaltung und einen schmalen Satz Routen (u. a. den
Kursdaten-Refresh-Endpunkt); die komplette interaktive Darstellung (Weltkarte,
Asset-Detailcharts, Vergleichsansicht) läuft als Dash-App unter `/dash/`.

```
Browser
  │
  ▼
Flask App (app/__init__.py: create_app)
  ├── Blueprint "main" (app/routes.py)      – dünne HTTP-Routen, Redirects, Refresh-POST
  └── Dash-App (app/dash_apps/main_dash.py) – SPA unter /dash/, eigene Callbacks/Routing
        │
        ├── app/services/data_service.py    – DB-Zugriff (SQLAlchemy) + CSV-Zugriff
        ├── app/services/stats_service.py   – Resampling, Regression, Normalisierung
        └── app/charts/plotly_charts.py     – Plotly-Figuren (Choropleth, Preis-Charts)
              │
              ▼
        PostgreSQL (Kursdaten)   +   CSV-Dateien unter data/ (Indexbestandteile, Länder)
```

## 2. Tech-Stack

- **Flask** – App-Factory, Routing, Session-Lifecycle
- **Dash** (auf demselben Flask-Server via `server=server`) – interaktive SPA-Oberfläche
- **SQLAlchemy 2.x** – ORM/Core für `stocks` / `stock_prices` in PostgreSQL
- **pandas / numpy** – Resampling, Regression, Normalisierung
- **Plotly** – Chart- und Karten-Rendering (`graph_objects`, `express`)
- **yfinance** – Nachladen von Kursdaten von Yahoo Finance
- **PostgreSQL 16** (Docker) – einzige Datenbank
- **pytest** – Tests

## 3. Verzeichnisstruktur (relevante Teile)

```
app/
  __init__.py          App-Factory (create_app)
  config.py             Env-basierte Konfiguration, lädt TRACKED_ASSETS
  extensions.py         SQLAlchemy Engine/Session, Flask g-Lifecycle
  models.py             ORM-Modelle: Stock, StockPrice
  routes.py             Flask-Blueprint "main"
  index_config.py       Statische Konfiguration: getrackte ETFs, Index-Farben
  services/
    data_service.py     DB-Reads/Writes, yfinance-Download, CSV-Loader für Indexdaten
    stats_service.py    Resampling, log2-/lineare/exponentielle Regression, Normalisierung
  charts/
    plotly_charts.py    Choropleth-Weltkarte + (teils ungenutzte) Jinja-Chart-Fragmente
  dash_apps/
    main_dash.py         Dash-App: Layouts, Callbacks, Figure-Builder
  templates/             Jinja-Templates (nur noch teilweise genutzt, s. u.)
  static/style.css       Von Flask-Templates UND Dash-App gemeinsam genutztes CSS

data/
  prices/*.csv                    CSV-Cache einzelner Kursreihen (Nebenpfad zur DB)
  index_constituents/
    raw/…, cleaned/…, aggregated/…  Aufbereitete Indexbestandteile & Länder-Aggregationen

scripts/
  init_db.py                      Legt Tabellen an (Base.metadata.create_all)
  seed_demo_data.py                Seedet einen Demo-Datensatz (AAPL)
  clean_index_constituents.py     Offline-Aufbereitung roher Indexbestandteile → CSVs

docker/Dockerfile      Flask-Image (python:3.12-slim, `flask run`)
docker-compose.yml     Services: postgres, web
```

## 4. Kernkomponenten

### 4.1 App-Factory (`app/__init__.py`)

`create_app()` erzeugt die Flask-App, lädt `Config`, initialisiert die DB-Engine
(`init_db`), registriert das Teardown für die DB-Session, registriert den Blueprint
`main` und hängt anschließend über `register_main_dash_app(app)` die Dash-App in
`app.extensions["main_dash_app"]` ein.

### 4.2 Konfiguration (`app/config.py`, `app/index_config.py`)

`Config` liest Umgebungsvariablen (`.env` via `python-dotenv`) für DB-URL, Debug-Flag,
Default-Ticker/-Periode/-Preisfeld etc. `TRACKED_ASSETS` wird nicht in `Config` gepflegt,
sondern zentral aus `index_config.py` bezogen — dort liegt die Liste der sieben
getrackten Assets (Gold + sechs ETFs: Emerging Markets, S&P 500, MSCI Japan, MSCI Pacific
ex-Japan, STOXX Europe 600, MSCI Canada) mit Symbol, WKN/ISIN, Region, Lat/Lon und
Farbschema pro Index (`INDEX_COLOR_CONFIG`). Diese Datei ist die Single Source of Truth
für Navigation, Karten-Einfärbung und Asset-Karten in der Übersicht.

### 4.3 Datenbank-Layer (`app/extensions.py`, `app/models.py`)

- Zwei Tabellen: `stocks` (Symbol, Name, Exchange, Currency) und `stock_prices`
  (OHLCV + `adjusted_close`, unique je `(stock_id, price_date)`).
- `extensions.py` verwaltet eine SQLAlchemy-`Engine` + `sessionmaker` in
  `app.extensions`; pro Request wird über Flask's `g` eine Session erzeugt und beim
  Teardown geschlossen. `session_scope()` bietet zusätzlich einen Context-Manager mit
  Commit/Rollback für Schreibpfade (z. B. Refresh, Seed-Skripte).
- Import von SQLAlchemy ist defensiv (`try/except ModuleNotFoundError`), damit Teile des
  Codes auch ohne installierte DB-Bibliothek importierbar bleiben (Tests).

### 4.4 Flask-Routen (`app/routes.py`)

Die Routen sind bewusst dünn und delegieren fast alles an die Dash-App:

| Route | Zweck |
|---|---|
| `GET /` | Redirect auf `/dash/` |
| `GET /stocks` | Rendert `stocks.html` (Jinja) mit der Asset-Liste |
| `GET /stocks/<symbol>` | Redirect auf `/dash/assets/<symbol>` |
| `GET /dash/assets/<symbol>` | Liefert `dash_app.index()` (Einstieg in die SPA) |
| `GET /dash/compare[/]` | Liefert ebenfalls `dash_app.index()` |
| `POST /stocks/<symbol>/refresh` | Lädt Kursdaten per yfinance nach, upserted sie in die DB, Redirect zurück zur Asset-Detailseite mit Status-Query-Parametern |

### 4.5 Dash-SPA (`app/dash_apps/main_dash.py`)

Die Dash-App wird unter `url_base_pathname="/dash/"` auf demselben Flask-Server
registriert (`Dash(__name__, server=server, ...)`) und bindet `/static/style.css` als
externes Stylesheet ein. Das clientseitige Routing läuft über `dcc.Location` +
einen zentralen Callback (`display_page`), der abhängig vom Pfad eines von vier Layouts
rendert:

- **Übersicht** (`/dash/`): Weltkarte (Choropleth) der Indexbestandteile nach Land,
  einfärbbar nach Company-Count / Security-Count / Gesamtgewicht, plus Kartenraster aller
  getrackten Assets.
- **Vergleich** (`/dash/compare`): zwei frei wählbare Assets, auf Basis=100 normalisiert,
  mit Datumsbereichs-Slider, linearer/log2-Y-Achse und Wachstums-Kennzahlen.
- **Asset-Detail** (`/dash/assets/<symbol>`): Kursverlauf mit wählbarer Preisspalte,
  linearer/log2 Y-Skala, optionaler linearer/exponentieller Regression,
  Datums- und Y-Achsen-Range-Sliders sowie einem Button, der den Flask-Refresh-Endpunkt
  per Formular-POST anstößt.
- **Not Found**: Fallback für unbekannte Symbole/Pfade.

Weitere Callbacks synchronisieren Dropdown/Slider-Zustände (z. B. Asset-Switcher in der
Navbar, Y-Achsen-Slider-Grenzen abhängig von Regressions- und Skalenwahl).

### 4.6 Service-Layer

**`app/services/data_service.py`**
- DB-Reads: `list_stocks`, `get_stock`, `get_price_frame` (liefert ein pandas-DataFrame
  direkt aus einer SQLAlchemy-`select`-Query).
- Statische Asset-Auflösung: `get_asset_by_symbol` sucht in `TRACKED_ASSETS`
  (`Config`), nicht in der DB.
- CSV-Loader für vorab aufbereitete Indexbestandteile (`load_index_companies`,
  `load_index_country_counts`, `load_all_index_country_counts`) aus
  `data/index_constituents/{cleaned,aggregated}`.
- yfinance-Integration: `download_price_data` lädt Rohdaten, `_normalize_price_frame`/
  `_flatten_download_columns` normalisieren Spalten (inkl. MultiIndex-Handling bei
  Einzelticker-Downloads), `upsert_price_frame` schreibt sie idempotent in die DB
  (Insert oder Update je `price_date`).
- Daneben existiert ein zweiter, CSV-basierter Pfad (`load_price_data`,
  `ensure_price_data`, `store_price_data_in_database`) über `data/prices/*.csv`, der
  parallel zum DB-Pfad existiert, aber vom aktuellen Dash-/Routen-Code nicht mehr
  aufgerufen wird — vermutlich ein Überbleibsel einer früheren Iteration.

**`app/services/stats_service.py`**
- Periodenbasierter Pfad (`resample_prices`, `add_log2_regression`, `analyze_prices`)
  mit den Dataclasses `RegressionResult`/`AnalysisResult` — für Weekly/Monthly/
  Quarterly/Yearly-Resampling plus log2-Trendregression.
- Dash-naher Pfad (`calculate_log2_regression`, `calculate_linear_regression`,
  `calculate_exponential_regression`, `normalize_price_series_to_100`,
  `align_two_normalized_series`) — arbeitet direkt auf den von Dash aufbereiteten
  DataFrames (Spalten `Date`, `Open/High/Low/Close/Adj Close`) und wird von
  `main_dash.py` für Detail- und Vergleichscharts verwendet.
- Beide Pfade sind funktional ähnlich, aber nicht deckungsgleich; es gibt keine
  gemeinsame Basis-Implementierung.

**`app/charts/plotly_charts.py`**
- `build_etf_country_exposure_map` (+ Hilfsfunktionen) baut die Choropleth-Weltkarte für
  einen einzelnen Index oder alle Indizes überlagert, eingefärbt nach einer der drei
  Metriken; nutzt `INDEX_COLOR_CONFIG` für Farbschemata pro Index.
- Eine zweite Funktionsgruppe (`price_chart`, `volume_chart`, `log2_price_chart`,
  `deviation_chart`, `create_price_chart_with_log2_regression`) erzeugt Plotly-HTML-
  Fragmente für die klassische Jinja-Darstellung. Diese Funktionen entsprechen dem
  ursprünglichen Zielbild aus `architecture-goal.md`, werden aber von den aktuellen
  Dash-Routen nicht mehr aufgerufen — die Detail- und Kursgraphen werden stattdessen
  direkt in `main_dash.py` (`build_asset_figure`, `build_compare_figure`) als
  `go.Figure`-Objekte für `dcc.Graph` gebaut.

### 4.7 Templates & Static

`app/templates/` (`base.html`, `index.html`, `stocks.html`, `stock_detail.html`) existiert
noch, wird aber kaum noch erreicht: `/` und `/stocks/<symbol>` leiten sofort auf die
Dash-Seiten um; nur `/stocks` rendert tatsächlich `stocks.html`. `app/static/style.css`
ist dagegen aktiv und wird von der Dash-App als externes Stylesheet eingebunden, sodass
Flask- und Dash-Oberfläche optisch konsistent bleiben.

## 5. Datenhaltung

Es gibt drei unabhängige Datenquellen:

1. **PostgreSQL** (`stocks`, `stock_prices`) — die "lebende" Quelle für Kursdaten, die von
   der Dash-App gelesen und über den Refresh-Button aktualisiert wird.
2. **`data/prices/*.csv`** — Kurs-Snapshots pro Symbol; werden von einem separaten,
   aktuell nicht mehr verdrahteten Code-Pfad in `data_service.py` genutzt sowie von
   Ad-hoc-Skripten (`data/loader.py`) befüllt.
3. **`data/index_constituents/{raw,cleaned,aggregated}`** — Indexbestandteile
   (Unternehmen je Index, Länderzuordnung inkl. Steuerdomizil-Heuristik) und daraus
   aggregierte Länder-Kennzahlen. Diese werden offline von
   `scripts/clean_index_constituents.py` aus Rohdaten erzeugt und zur Laufzeit nur
   gelesen (Basis für die Weltkarte).

## 6. Datenfluss: Kursdaten-Refresh

1. Nutzer klickt in der Dash-Asset-Detailseite auf "Kursdaten aktualisieren" (HTML-`Form`
   mit `action=/stocks/<symbol>/refresh`, `method=post` — bewusst ein normaler
   Formular-POST, kein Dash-Callback, damit ein voller Redirect inkl. Status-Query
   möglich ist).
2. Flask-Route `refresh_stock` löst `download_price_data` (yfinance) aus, normalisiert
   das Ergebnis und ruft `upsert_price_frame` innerhalb eines `session_scope()` auf.
3. Redirect zurück zu `/dash/assets/<symbol>?refresh=success&inserted=…&updated=…`
   (oder `refresh=error&message=…`).
4. Der Dash-Callback `display_page`/`get_refresh_status` liest die Query-Parameter aus
   `dcc.Location.search` und zeigt eine Erfolgs-/Fehlermeldung an.

## 7. Deployment

- **`docker-compose.yml`**: zwei Services, `postgres` (offizielles Image, Healthcheck,
  persistentes Volume) und `web` (gebaut aus `docker/Dockerfile`), verbunden über
  `depends_on: condition: service_healthy`.
- **`docker/Dockerfile`**: einfaches `python:3.12-slim`-Image, installiert
  `requirements.txt`, startet mit `flask --app app:create_app run --host 0.0.0.0`
  (kein WSGI-Server wie gunicorn — passend zum MVP-Charakter).
- Schema-Erstellung und Demo-Daten sind bewusst nicht Teil des Container-Starts, sondern
  separate Einmal-Kommandos (`scripts/init_db.py`, `scripts/seed_demo_data.py`) via
  `docker compose run --rm web …`.

## 8. Tests (`tests/`)

- `test_app.py` — Flask-Routen/Smoke-Tests
- `test_main_dash.py` — Dash-Layout-/Callback-Funktionen
- `test_stats_service.py` — Resampling/Regression
- `test_index_constituents.py` — Aufbereitung/Validierung der Indexbestandteile-CSVs
- `conftest.py` — gemeinsame Fixtures (u. a. Flask-App-Kontext)

## 9. Abweichungen von `architecture-goal.md`

Das ursprüngliche Zieldokument sah explizit **kein Dash** vor ("Avoid for MVP: … Dash")
und eine reine Single-Stock-Ansicht ohne Mehrfach-Asset-Vergleich
("multi-stock comparison" war ausdrücklich ausgeschlossen). Der tatsächliche Code hat
sich davon in mehreren Punkten entfernt:

- Die komplette interaktive UI läuft heute als **Dash-App**, nicht als Jinja-Templates
  mit eingebetteten Plotly-HTML-Fragmenten. Die für das ursprüngliche Konzept gebauten
  Chart-Funktionen in `plotly_charts.py` sind größtenteils totes/ungenutztes Bindeglied.
- Es gibt eine **Zwei-Asset-Vergleichsansicht** (`/dash/compare`) inkl. Normalisierung
  auf einen gemeinsamen Basiswert — im Zieldokument nicht vorgesehen.
- Die Anwendung ist von "ein Ticker" auf **mehrere fest konfigurierte Assets** (ETFs +
  Gold) mit Weltkarten-/Länderexposure-Feature erweitert worden (`index_config.py`,
  `data/index_constituents/*`) — im Zieldokument nicht vorgesehen.
- Es existieren **zwei parallele Datenpfade** für Kursdaten (DB via SQLAlchemy und CSV
  via `data/prices/`) sowie **zwei parallele Statistik-Implementierungen**
  (`stats_service.py`), von denen jeweils nur ein Teil aktiv genutzt wird — das
  Zieldokument sah einen einzigen, klar geschichteten Pfad vor.

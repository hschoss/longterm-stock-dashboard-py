# Umsetzungsplan — Phase 0

> Ergebnis der Bestandsaufnahme aus `docs/auftrag.md`, Phase 0. Ändert keinen Code.
> Bezieht sich auf den Ist-Zustand in `docs/ARCHITEKTUR.md`.

## 1. Status dieses Plans

Phase 0 hat zwei Teile: (a) Analyse des bestehenden Repos, (b) lesende Inspektion der
Quelldatenbank. Teil (a) ist vollständig. Teil (b) ist **blockiert**: Abschnitt 5.1 des
Auftrags listet Eckdaten, die von dir auszufüllen sind (Typ/Version, Erreichbarkeit,
Zugangsdaten, relevante Tabellen, Zeitpunkt des Tagesabschlusses). Diese fehlen noch.
Die Abschnitte 5–7 dieses Plans (Sync-Empfehlung, Quell-Mapping, Frequenzmodell) sind
deshalb vorläufig und mit dem Standard-Vorgehen aus dem Auftrag (Option 3) vorbelegt.
Siehe Abschnitt 8 „Offene Fragen" für die konkreten Rückfragen.

## 2. Architektur und Datenfluss

Zielarchitektur wie in `docs/auftrag.md` Abschnitt 4 festgelegt: Schichten `core` →
`storage` → `sync`/`analytics` → `forecasting`/`jobs` → `app`, Importrichtung nur nach
„oben rechts", erzwungen über import-linter.

```
Quelldatenbank (read-only, Netzwerk)
   │  findash sync run (täglich, nach Tagesabschluss der Quelle)
   ▼
staging.*  →  Validierung (Pflichtwerte, Duplikate, Monotonie, OHLC, Kurssprünge)  →  market.*
   │                                                                                    │
   │  findash jobs nightly: analytics → forecasting → backtests → model_selection      │
   ▼                                                                                    │
analytics.*, forecast.*, ops.job_run_items (Protokoll je Schritt/Asset)  ◄──────────────┘
   │
   ▼
Dash-App (app/) — liest ref/market/analytics/forecast, rechnet nur Renditen für den
gewählten Zeitraum, kein Zugriff auf staging, keine Schreibzugriffe außer Sessions/UI-State
```

Wichtiger Unterschied zum Ist-Zustand (`docs/ARCHITEKTUR.md`): Die Web-App verliert jeden
Kontakt zu yfinance und zu den CSV-Kurspfaden. Sie liest ausschließlich aus `market.*`
und den vorberechneten `analytics.*`/`forecast.*`-Tabellen. Die Weltkarten-/Länder-Daten
wandern von CSV nach `ref.*` (einmalige Migration, danach nur noch DB-Lesen).

Flask entfällt vollständig; Dash läuft mit `use_pages=True` als eigene Flask-App
(`app.server` für gunicorn/`/healthz`).

## 3. Datenmodell (Mindestumfang mit Typen und Schlüsseln)

Alle Zeitstempel `timestamptz`, intern UTC. Schemaänderungen ausschließlich über Alembic.

### `ref`

**`ref.assets`**
| Spalte | Typ | Schlüssel/Constraint |
|---|---|---|
| `asset_id` | `bigserial` | PK |
| `symbol` | `text` | `unique not null` — natürlicher Schlüssel, aus `config/assets.yaml` |
| `name` | `text` | `not null` |
| `asset_type` | `text` (check: `index_etf`, `commodity`, `equity`, …) | `not null` |
| `currency` | `text` (ISO 4217) | `not null` |
| `exchange_timezone` | `text` (IANA, z. B. `Europe/Berlin`) | `not null` |
| `source_key` | `text` | Schlüssel in der Quelldatenbank, aus `sync_mapping.yaml` |
| `is_active` | `boolean` | `not null default true` |
| `color` | `text` (hex) | für Karten/Choropleth-Einfärbung |
| `region`, `map_label`, `lat`, `lon` | `text`/`double precision` | optional, für Übersichtskarte |
| `created_at`, `updated_at` | `timestamptz` | `not null default now()` |

**`ref.index_constituents`** (Ablösung der CSV-Dateien unter `data/index_constituents/`)
| Spalte | Typ | Schlüssel/Constraint |
|---|---|---|
| `id` | `bigserial` | PK |
| `index_asset_id` | `bigint` | FK → `ref.assets.asset_id` |
| `as_of_date` | `date` | `not null` — Bestandsdatum der Zusammensetzung |
| `security_id`, `ticker`, `company_name`, `security_name` | `text` | |
| `sector`, `industry`, `asset_class`, `currency`, `isin` | `text` | |
| `weight_pct`, `market_value_usd`, `shares` | `numeric` | |
| `country`, `iso_alpha3` | `text` | |
| `tax_residence_country`, `tax_residence_iso_alpha3` | `text` | |
| `tax_country_basis`, `tax_country_confidence` | `text` | dokumentiert Heuristik-Herkunft |
| `is_company`, `is_duplicate_security` | `boolean` | |
| `source_file`, `source_row_number` | `text`/`int` | Nachvollziehbarkeit zur Ursprungs-CSV |
| Unique | | `(index_asset_id, as_of_date, security_id)` |

**`ref.index_country_exposure`** (Ablösung der `aggregated/*_country_counts.csv`)
| Spalte | Typ |
|---|---|
| `index_asset_id` | FK → `ref.assets.asset_id` |
| `as_of_date` | `date` |
| `country`, `iso_alpha3` | `text` |
| `company_count`, `security_count` | `integer` |
| `total_weight_pct` | `numeric` |
| `tax_residence_country`, `tax_residence_iso_alpha3` | `text` |
| Primärschlüssel | `(index_asset_id, as_of_date, iso_alpha3)` |

### `staging`

Struktur hängt vom Quellschema ab (offen, siehe Abschnitt 8). Muster:

**`staging.prices_raw`**
| Spalte | Typ |
|---|---|
| `id` | `bigserial` PK |
| `_sync_run_id` | FK → `ops.job_runs.id` |
| `_loaded_at` | `timestamptz not null default now()` |
| `source_key` | `text` (unaufgelöster Quellschlüssel, Mapping erfolgt erst beim Übergang nach `market`) |
| restliche Spalten | unverändertes Abbild der Quellzeile (Typen je nach Quelle, konservativ `text`/`numeric`, keine verlustbehaftete Konvertierung) |

### `market`

**`market.prices`**
| Spalte | Typ | Schlüssel |
|---|---|---|
| `asset_id` | `bigint` | PK-Teil, FK → `ref.assets` |
| `frequency` | `text` (`daily`, `snapshot_am`, `snapshot_pm`) | PK-Teil |
| `ts` | `timestamptz` (UTC) | PK-Teil |
| `open`, `high`, `low`, `close`, `adj_close` | `numeric(18,6)` nullable | fehlende Werte bleiben `NULL`, nie erfunden |
| `volume` | `bigint` nullable | |
| `quality_status` | `text` (`ok`, `flagged`, `missing`) | `not null default 'ok'` |
| `sync_run_id` | `bigint` | FK → `ops.job_runs.id` |
| Primärschlüssel | | `(asset_id, frequency, ts)` |

### `analytics`

**`analytics.metrics`** (Long-Format, vorberechnet im Batch)
| Spalte | Typ |
|---|---|
| `asset_id` | FK → `ref.assets` |
| `frequency` | `text` |
| `metric` | `text` (z. B. `return_1d`, `volatility_ann`, `max_drawdown`, `var_95`, `expected_shortfall_95`, `sharpe`) |
| `window` | `text` (z. B. `20`, `1Y`, `max`) |
| `as_of` | `timestamptz` |
| `value` | `double precision` nullable |
| `job_run_id` | FK → `ops.job_runs` |
| Primärschlüssel | `(asset_id, frequency, metric, window, as_of)` |

### `forecast`

**`forecast.model_versions`**: `id` PK, `model_name`, `version`, `config jsonb`,
`git_commit`, `created_at`.

**`forecast.forecasts`**: `id` PK, `job_run_id` FK, `asset_id` FK, `model_version_id` FK,
`horizon` (`text`, z. B. `next`, `1d`, `5d`, `20d`), `data_as_of timestamptz`,
`expected_log_return double precision`, `quantiles jsonb`
(Schlüssel `p02_5..p97_5`), `prob_positive double precision`,
`expected_volatility double precision`, `derived_index_level double precision` nullable.
Unique `(asset_id, model_version_id, horizon, data_as_of)`.

**`forecast.mcmc_diagnostics`**: `forecast_id` FK, `chains`, `draws`, `tuning_steps`,
`seed` (`integer`), `r_hat_max`, `ess_bulk_min`, `ess_tail_min` (`double precision`),
`divergences` (`integer`), `runtime_seconds` (`double precision`),
`status` (`ok`/`eingeschränkt`/`fehlgeschlagen`).

**`forecast.backtest_results`**: `asset_id`, `model_version_id`, `horizon`,
`origin_ts timestamptz`, `mae`, `rmse`, `directional_accuracy`, `coverage_50`,
`coverage_80`, `coverage_95`, `crps`, `runtime_seconds`.

**`forecast.model_selection`**: `asset_id`, `horizon`, `selected_model_version_id` FK,
`selection_rule text`, `as_of timestamptz`, `job_run_id` FK.

### `ops`

**`ops.job_runs`**: `id` PK, `job_type` (`sync`, `analytics`, `forecast`, `nightly`, …),
`status` (`pending|running|success|partial_success|failed`), `started_at`, `finished_at`,
`parameters jsonb`, `error text` nullable.

**`ops.job_run_items`**: `id` PK, `job_run_id` FK, `asset_id` FK nullable, `step text`,
`status`, `started_at`, `finished_at`, `error text` nullable.

**`ops.sync_state`**: `source_table text` PK-Teil, `asset_id` FK nullable (falls
Wasserzeichen je Asset statt je Tabelle geführt wird — Entscheidung in Phase 2),
`watermark_ts timestamptz`, `last_run_id` FK → `ops.job_runs`, `updated_at`.

ArviZ-`InferenceData` als NetCDF in einem Docker-Volume; `forecast.mcmc_diagnostics`
bekommt zusätzlich `artifact_path text` und `artifact_sha256 text`.

## 4. Baustein-Katalog und Seiten

| Seite | Pfad | Bausteine (AIO) |
|---|---|---|
| Übersicht | `/` | Asset-Karten-Raster (letzter Kurs, Δ, Mini-Chart, Qualitätsstatus), Weltkarte Länder-Exposure, Statusleiste |
| Rückschau | `/rueckschau/<asset>` | Kennzahlen, Kurschart (Linie/Candlestick + Volumen + gleitende Durchschnitte), Trend-Regression (linear/exponentiell/log2, **eine** Implementierung), Drawdown-Chart, Rollierende Volatilität, Renditeverteilung (Histogramm/Boxplot), Snapshot-Zeitreihe (nur falls Snapshots existieren), Tabelle neueste Beobachtungen |
| Vergleich | `/vergleich` | Normalisierter Vergleich (Start=100) für ≥2 Assets, kumulierte Rendite, Korrelations-Heatmap |
| Vorschau | `/vorschau/<asset>` | Prognose-Fächer, Prognosetabelle je Horizont, Modellkarte, Modellvergleich (Backtest-Kennzahlen), Tabelle „Prognose vs. realisiert" |
| System | `/system` | Job-Läufe (`ops.job_runs`/`job_run_items`), Sync-Status, Datenqualität je Asset, MCMC-Diagnostik-Übersicht |

Jeder Baustein: Repository-Query (`storage/`) → Berechnung (`analytics/` oder
vorberechnet) → reiner Figure-Builder (`app/figures/`, `DataFrame → go.Figure`) →
Layout-Klasse (`dbc.Card`, Pattern-Matching-IDs). Kontext (Assets, Frequenz, Zeitraum,
Preisfeld) kommt einheitlich aus URL-Query-Parametern/`dcc.Store`.

Phase-3-Minimalumfang: Kennzahlen, Kurschart, Datenqualität (siehe Auftrag Abschnitt 12).

## 5. Modellierungsstrategie

Gemeinsame Schnittstelle für alle Modelle: `fit(train) -> FittedModel`,
`predict(horizons) -> ForecastDistribution` (Samples oder Quantile), Zielgrößen sind
log-Renditen und Volatilität; Indexstände/Pfade werden daraus abgeleitet.

1. **Baseline** — Random Walk mit historischer Mittelwertrendite. Dient als
   Untergrenze für Backtest-Vergleiche.
2. **ARIMA** (statsmodels) — auf log-Renditen, Ordnung konfigurierbar/automatisch.
3. **GARCH(1,1)** mit Student-t (arch) — für die Volatilitätskomponente.
4. **Bayes Stochastic-Volatility** (PyMC) — Student-t-Innovationen, dokumentierte Priors,
   fester Seed, konfigurierbares Trainingsfenster.

Diagnostik (R̂, ESS bulk/tail, Divergences, Laufzeit) wird für jeden MCMC-Lauf
gespeichert; Status `ok`/`eingeschränkt`/`fehlgeschlagen` nach den Standardschwellen aus
Abschnitt 8.3 des Auftrags (R̂ ≤ 1,01, ESS ≥ 400, 0 Divergences ⇒ `ok`).

Backtesting per Rolling-Origin je Asset/Horizont/Modell; alle Modellergebnisse bleiben
persistiert, Modellauswahl je Asset/Horizont folgt einer konfigurierbaren Regel
(Vorschlag: geringster CRPS über das Backtest-Fenster, Tie-Break über RMSE — final in
Phase 5 festzulegen).

Ist ein Prognoselauf älter als die konfigurierbare Schwelle (Standard 36 h) oder
fehlgeschlagen, zeigt die Vorschau-Seite die letzte erfolgreiche Prognose mit deutlicher
„nicht aktuell"-Markierung statt eines Fehlers.

## 6. Bestandsaufnahme: übernehmen / zusammenführen / löschen

| Element | Fundort (Ist) | Entscheidung | Begründung / Zielort |
|---|---|---|---|
| Flask-Blueprint, App-Factory | `app/__init__.py`, `app/routes.py` | **löschen** | Dash ersetzt Flask vollständig (Auftrag §3); `/healthz` künftig direkt auf `app.server` |
| Jinja-Templates | `app/templates/*.html` | **löschen** | ungenutzt/redundant zur Dash-SPA; kein Jinja im Zielbild |
| Eigenes CSS | `app/static/style.css` | **löschen** | nur `dash-bootstrap-components` + Bootstrap-Utilities; Ausnahmen nur mit Rückfrage |
| Refresh-Route (manueller Kursdaten-Nachlader) | `app/routes.py: refresh_stock` | **löschen** | Web-App schreibt nie in die DB; Nachladen läuft ausschließlich über `findash sync` |
| yfinance-Integration | `app/services/data_service.py` (`download_price_data`, `_normalize_price_frame`, `_flatten_download_columns`, `_is_placeholder_symbol`) | **löschen** | Leitprinzip 4: keine Web-Datenbeschaffung; Kursdaten nur aus Quelldatenbank |
| CSV-Kurspfad | `data/prices/*.csv`, `data_service.load_price_data`/`ensure_price_data`/`store_price_data_in_database`, `data/loader.py` | **löschen** | zweiter Datenpfad entfällt vollständig zugunsten `market.prices` |
| DB-Kurspfad (Modelle, Upsert, Lesefunktionen) | `app/models.py` (`Stock`, `StockPrice`), `data_service.upsert_price_frame`/`get_price_frame` | **zusammenführen** | Konzept (Upsert auf natürlichem Schlüssel, DataFrame-Reads) wandert nach `storage/tables.py` (`market.prices`) + `storage/repositories/`; Schema und Herkunft (Sync statt manuellem Insert) ändern sich |
| Zwei Statistik-Implementierungen | `app/services/stats_service.py` (perioden-basiert **und** Dash-naher Pfad) | **zusammenführen** | eine Regression-Implementierung (linear/exponentiell/log2) in `analytics/regression.py`; `normalize_price_series_to_100`/`align_two_normalized_series` wandern nach `analytics/returns.py` bzw. einem Vergleichs-Modul, erweitert auf ≥2 Assets |
| Resampling | `stats_service.resample_prices` | **übernehmen** | Logik in `analytics/` wiederverwendbar, Tests migrieren |
| Ungenutzte Chart-Fragmente | `app/charts/plotly_charts.py` (`price_chart`, `volume_chart`, `log2_price_chart`, `deviation_chart`, `create_price_chart_with_log2_regression`, `_to_html`, `_empty_chart`, `_fallback_html`) | **löschen** | bereits laut `docs/ARCHITEKTUR.md` toter Code, kein Aufrufer mehr |
| Weltkarten-Choropleth | `app/charts/plotly_charts.py: build_etf_country_exposure_map` | **übernehmen** | wandert nach `app/figures/`, liest künftig aus `ref.index_country_exposure` statt CSV |
| Indexbestandteile-CSVs | `data/index_constituents/{raw,cleaned,aggregated}` | **übernehmen (einmalig), dann löschen** | Basis für eine einmalige Migration nach `ref.index_constituents`/`ref.index_country_exposure`; danach kein Laufzeit-Lesezugriff mehr auf CSV |
| Aufbereitungsskript | `scripts/clean_index_constituents.py` | **zusammenführen** | Logik als einmaliges Migrationsskript (`findash`-Unterbefehl oder `jobs/migrate_index_constituents.py`), danach nicht mehr Teil des Laufzeitpfads |
| Schema-Erstellung | `scripts/init_db.py` (`Base.metadata.create_all`) | **löschen** | ersetzt durch Alembic-Migrationen |
| Demo-Seed (AAPL) | `scripts/seed_demo_data.py` | **löschen, ersetzen** | ersetzt durch `findash seed-demo` mit deterministischen Beispieldaten für mehrere Assets (Auftrag §10) |
| Konfiguration (getrackte Assets, Farben) | `app/config.py`, `app/index_config.py` | **zusammenführen** | Inhalte wandern nach `config/assets.yaml` (validiert über `core`-Pydantic-Modelle) + `ref.assets`; `pydantic-settings` ersetzt `os.getenv`-Handling |
| DB-Session-Lifecycle | `app/extensions.py` | **zusammenführen** | Grundmuster (Engine + Session) bleibt, Flask-`g`-Bindung entfällt; wandert nach `storage/` ohne Flask-Abhängigkeit |
| Dash-App/Callbacks | `app/dash_apps/main_dash.py` | **zusammenführen** | fachliche Callback-Logik (Parsing, Slider-Zustände, Figure-Aufrufe) wird auf das AIO-Muster mit Dash Pages umgebaut, kein Freihand-Routing über `dcc.Location` mehr nötig |
| Tests | `tests/*` | **zusammenführen** | Testfälle (Resampling/Regression/Callback-Logik) migrieren auf neue Modulpfade; DB-Tests erweitern um Integrationstests gegen echtes PostgreSQL |
| Docker-Setup | `docker-compose.yml`, `docker/Dockerfile` | **zusammenführen** | Struktur bleibt, ergänzt um `worker`-Service, gunicorn, Healthcheck |
| Abhängigkeitsverwaltung | `requirements.txt` | **löschen** | ersetzt durch `pyproject.toml` mit `uv`, `src`-Layout |

## 7. Sync-Option (vorläufige Empfehlung)

**Empfehlung: Option 3 — Python-Sync-Job mit SQLAlchemy**, wie im Auftrag als
Voreinstellung vorgesehen. Begründung, solange der Quelldatenbanktyp nicht bestätigt ist:

- funktioniert unabhängig davon, ob die Quelle PostgreSQL oder etwas anderes ist,
- lässt sich sauber in `ops.job_runs`/`job_run_items` protokollieren,
- erlaubt Validierung **vor** dem Schreiben (Pflichtwerte, Duplikate, OHLC-Konsistenz,
  Kurssprünge) — bei Logical Replication oder `postgres_fdw` müsste diese Validierung
  nachgelagert auf bereits gespiegelten/verknüpften Daten laufen, was der Anforderung
  „Auffällige Zeilen werden mit Qualitätsstatus gespeichert, nicht verworfen" schwerer
  gerecht wird.

Diese Empfehlung ist mit den in Abschnitt 8 genannten offenen Fragen zu bestätigen.
Stellt sich heraus, dass die Quelle PostgreSQL ist und die benötigten Tabellen 1:1 in
`staging` gespiegelt werden können, ist `postgres_fdw` mit SQL-Upsert (Option 2) als
schlankere Alternative zu prüfen — sie würde aber keine Vorab-Validierung in Python
ermöglichen und passt schlechter zur geforderten Fehlerisolation je Asset.

## 8. Annahmen, Risiken und offene Fragen

### Offene Fragen (blockieren Teile von Phase 0 / Phase 2)

Aus Auftrag §5.1, bisher nicht ausgefüllt:

1. Typ und Version der Quelldatenbank (PostgreSQL? Version? Oder anderes System?)
2. Erreichbarkeit: Host/Netzwerksegment, gibt es bereits einen rein lesenden Nutzer,
   soll `SOURCE_DATABASE_URL` in `.env` gesetzt werden?
3. Relevante Tabellen/Views (Namen, grober Spaltenüberblick reicht für den Anfang)
4. Zu welcher Uhrzeit ist der Tagesstand in der Quelle üblicherweise vollständig
   (bestimmt den frühesten sinnvollen Zeitpunkt für `findash jobs nightly`)?

Ohne diese Angaben kann die lesende Inspektion aus §5.2 (Schema, Zeitzonen, Frequenz,
Änderungszeitstempel, rückwirkende Korrekturen, adjustierte Kurse) nicht durchgeführt
und die Sync-Empfehlung aus Abschnitt 7 nicht endgültig bestätigt werden.

### Annahmen (pragmatisch getroffen, siehe `docs/entscheidungen.md`)

- Die bestehende lokale PostgreSQL-Instanz (aktuell `stock_tracker`, siehe
  `docker-compose.yml`) wird für `ref`/`staging`/`market`/`analytics`/`forecast`/`ops`
  weiterverwendet; es wird keine zusätzliche lokale Datenbank aufgesetzt.
- Die Liste der getrackten Assets bleibt zunächst unverändert (Gold + sechs ETFs aus
  `app/index_config.py`) und wird 1:1 nach `config/assets.yaml` übernommen; Erweiterung
  ist über die Konfiguration jederzeit möglich.
- Risikofreier Satz für Sharpe Ratio: Standard `0`, konfigurierbar in
  `config/analytics.yaml`.
- Modellauswahlregel (Phase 5 final): geringster CRPS je Asset/Horizont über das
  Backtest-Fenster, Tie-Break über RMSE.
- Snapshot-Frequenzen (`snapshot_am`/`snapshot_pm`) werden erst gebaut, sobald bestätigt
  ist, dass die Quelle Intraday-Daten liefert; andernfalls bleibt es bei `daily` und die
  Snapshot-Funktion wird nur als offene Option dokumentiert (Auftrag §5.4).

### Risiken

- **MCMC-Laufzeit** auf lokaler Hardware kann für den nächtlichen Batch zu lang sein;
  Gegenmaßnahme ist der bereits vorgesehene `--fast`-Modus mit reduzierten
  MCMC-Parametern sowie ein konfigurierbares Trainingsfenster.
- **`dash-ag-grid` auf mobilen Geräten**: Bundle-Größe/Touch-Bedienbarkeit bei 390 px
  ist zu prüfen; Fallback ist `dbc.Table` für die primären mobilen Tabellen, `ag-grid`
  nur dort, wo Sortieren/Filtern auf breiteren Bildschirmen nötig ist.
- **Unbekanntes Quellschema**: Bis Frage 1–3 oben geklärt sind, ist das
  `staging`-Schema (Abschnitt 3) nur ein Platzhaltermuster; es kann sich nach der
  Inspektion noch ändern, ohne dass sich `market`/`analytics`/`forecast` ändern müssen.

## 9. Vorschlag für Phase 1

Sobald freigegeben und sobald mindestens die offenen Fragen 1–2 aus Abschnitt 8 geklärt
sind (Frage 3–4 können notfalls parallel zu Phase 1 geklärt werden, da sie erst für
Phase 2 zwingend nötig sind): Projektgerüst (`pyproject.toml`, `src`-Layout), Alembic mit
den Schemas `ref`/`ops`/`staging`/`market`, Settings/Logging, Job-Protokoll, CLI-Skelett,
Tooling (ruff/mypy/import-linter/pre-commit) und `seed-demo` gemäß Auftrag §12 Phase 1.

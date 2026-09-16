# Auftrag für Claude Code: Modulares Finanz-Analyse-Dashboard

> Lies vor allem anderen `CLAUDE.md` und `docs/ARCHITEKTUR.md`. Dieses Dokument beschreibt Ziel, Technik und Vorgehen. Du arbeitest strikt in Phasen (Abschnitt 12) und beginnst mit Phase 0, **ohne Code zu ändern**.

---

## 1. Ausgangslage und Ziel

Es gibt ein bestehendes Repository („Longterm Stock Dashboard“). Es besteht aus einer Flask-App mit eingebetteter Dash-SPA und PostgreSQL. Kursdaten kommen über yfinance. Dazu gibt es eine Weltkarte der Indexbestandteile, eine Zwei-Asset-Vergleichsansicht und Trend-Regressionen (linear, exponentiell, log2). Der Code hat gewachsene Altlasten:

- zwei parallele Kursdatenpfade (Datenbank und CSV)
- zwei parallele Statistik-Implementierungen
- ungenutzte Jinja-Templates und Chart-Fragmente
- eigenes CSS

Ziel ist ein Umbau zu einem **Bausteinsystem**. Es entsteht eine Analyseplattform für eine konfigurierbare Liste von Finanzinstrumenten (Indizes, ETFs, Rohstoffe) mit:

- **Rückschau:** explorative Analyse historischer Zeitreihen
- **Vorschau:** probabilistische Prognosen aus nächtlichen Batch-Läufen
- Nutzung im Desktop-Browser **und auf dem iPhone**

Die Anwendung dient ausschließlich Analyse- und Forschungszwecken. Der Hinweis **„Keine Anlageberatung.“** ist auf jeder Seite sichtbar, auch mobil.

## 2. Leitprinzipien (verbindlich)

1. **Standard vor Eigenbau.** Für jedes Problem wird die etablierte Standardlösung des Ökosystems verwendet (Abschnitt 3). Nicht erlaubt sind eigene Frameworks, eigene CSS-Systeme und Abstraktionen „auf Vorrat“. Wer abweichen will, begründet das schriftlich und holt Freigabe ein.
2. **Bausteine mit klaren Grenzen.** Jede Schicht und jeder Baustein hat eine schmale, typisierte Schnittstelle, ist einzeln testbar und austauschbar. Abhängigkeiten zeigen nur in eine Richtung (Abschnitt 4).
3. **Die Web-App rechnet nicht schwer.** Das Dashboard liest aus PostgreSQL. Es führt höchstens leichte Berechnungen auf bereits gelesenen Daten aus, z. B. Renditen für einen frei gewählten Zeitraum. Modelle, MCMC, Backtests und aufwendige Kennzahlen entstehen ausschließlich im Batch.
4. **Keine Datenbeschaffung aus dem Internet.** Kursdaten kommen ausschließlich aus einer Quelldatenbank im lokalen Netzwerk. yfinance und alle Web-Abrufe werden entfernt.
5. **Keine erfundenen Werte.** Fehlende Daten bleiben fehlend und werden sichtbar markiert. Es gibt keine stille Interpolation und kein Auffüllen.
6. **Nachvollziehbarkeit.** Jede angezeigte Zahl lässt sich auf Datenstand und Job-Lauf zurückführen, bei Prognosen zusätzlich auf die Modellversion.
7. **Klein und lauffähig.** Jede Phase endet mit einem lauffähigen System und grünen Tests.

## 3. Technologie-Stack (festgelegt)

| Bereich | Standardlösung |
|---|---|
| Sprache | Python 3.12, vollständig typisiert, Docstrings für öffentliche Funktionen |
| Projekt & Abhängigkeiten | `pyproject.toml` mit uv, gepinnte Versionen, `src`-Layout |
| Web-UI | Dash (aktuelle stabile Version) mit Dash Pages (`use_pages=True`) |
| Layout & Styling | `dash-bootstrap-components` mit `dbc.themes.BOOTSTRAP` (Bootstrap 5.3) und `dbc.icons.BOOTSTRAP` |
| Charts | Plotly (`graph_objects`), Figure-Templates passend zum Theme über `dash-bootstrap-templates` |
| Tabellen | `dbc.Table` für einfache Tabellen, `dash-ag-grid` für sortier- und filterbare Tabellen |
| Datenverarbeitung | pandas, numpy |
| Datenbank | PostgreSQL 16 (bestehende Version) |
| DB-Zugriff | SQLAlchemy 2.x (Core) mit psycopg 3 |
| Migrationen | Alembic |
| Konfiguration | `pydantic-settings` für `.env`, YAML-Dateien validiert über Pydantic-Modelle |
| Klassische Modelle | statsmodels (ARIMA/SARIMAX), arch (GARCH) |
| Bayes / MCMC | PyMC, ArviZ |
| CLI | Typer, ein Einstiegspunkt `findash` mit Unterbefehlen |
| Web-Server | gunicorn |
| Scheduling | cron oder systemd-Timer auf dem Host, startet `docker compose run --rm worker …` |
| Logging | `logging` der Standardbibliothek, JSON-Format für Jobs |
| Qualität | pytest, ruff (Lint + Format), mypy, import-linter, pre-commit |
| Container | Docker, Docker Compose |

Die bestehende Flask-Schicht entfällt: Blueprint, Jinja-Templates und Refresh-Route. Dash ist selbst eine Flask-App. Zusätzliche HTTP-Routen wie `/healthz` werden direkt auf `app.server` registriert.

## 4. Architektur

### 4.1 Schichten und Import-Regeln

| Paket | Aufgabe | darf importieren |
|---|---|---|
| `core/` | Settings, Domänentypen (`Asset`, `Frequency`, `JobStatus`, `QualityStatus`), Zeit-/Zeitzonen-Helfer, Logging | Standardbibliothek, pydantic |
| `storage/` | Tabellendefinitionen, Repositories, Alembic-Migrationen — **einzige Stelle mit SQL** | `core` |
| `sync/` | Quelldatenbank lesen, Mapping, Validierung, Upsert | `core`, `storage` |
| `analytics/` | Renditen, Risiko, Indikatoren, Regression — **reine Funktionen** auf DataFrames | `core` |
| `forecasting/` | Modelldaten, Modelle, MCMC, Backtesting — ohne DB- und Dash-Bezug | `core`, `analytics` |
| `jobs/` | CLI, nächtlicher Ablauf, Job-Protokoll | alles außer `app` |
| `app/` | Dash Pages, UI-Bausteine, Figure-Builder — **nur lesender** DB-Zugriff | `core`, `storage`, `analytics` |

Diese Regeln werden als import-linter-Contracts hinterlegt und in der Testsuite geprüft.

Datenfluss:

```
Quelldatenbank (Netzwerk, read-only)
   │  findash sync run  (täglich)
   ▼
staging → Validierung → market      (PostgreSQL lokal)
   │
   │  findash jobs nightly
   ▼
analytics.* und forecast.*          (vorberechnete Ergebnisse, ops.* Protokoll)
   │
   ▼
Dash-App                            (liest, stellt dar, rechnet nur leicht)
```

### 4.2 Verzeichnisstruktur (Zielbild)

```
.
├── src/findash/
│   ├── core/
│   ├── storage/
│   │   ├── tables.py
│   │   ├── repositories/
│   │   └── migrations/
│   ├── sync/
│   ├── analytics/
│   ├── forecasting/
│   │   └── models/            # baseline.py, arima.py, garch.py, bayes_sv.py
│   ├── jobs/
│   └── app/
│       ├── main.py            # Dash-Instanz, `server` für gunicorn
│       ├── pages/             # overview, history, compare, forecast, system
│       ├── blocks/            # ein Modul je UI-Baustein
│       ├── figures/           # reine Plotly-Figure-Builder
│       └── assets/            # Favicon, apple-touch-icon; CSS nur im Ausnahmefall
├── config/
│   ├── assets.yaml            # getrackte Instrumente
│   ├── sync_mapping.yaml      # Quelle → Zielschema, Quellinstrument → Asset
│   ├── analytics.yaml         # Fenster, Konfidenzniveaus, Perioden pro Jahr
│   └── forecasting.yaml       # Horizonte, Modelle, MCMC-Parameter, Schwellen
├── tests/{unit,integration,fixtures}/
├── docs/
├── docker/Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
├── .env.example
├── CLAUDE.md
└── README.md
```

Diese Struktur ist ein Vorschlag. Abweichungen begründest du in Phase 0.

### 4.3 Der UI-Baustein

Ein UI-Baustein ist eine eigenständige Karte, z. B. „Kennzahlen“, „Drawdown“ oder „Prognose-Fächer“. Er folgt dem von Plotly dokumentierten **All-in-One-Component-Muster (AIO)** und besteht aus vier Teilen:

1. **Datenabruf** über ein Repository aus `storage/`
2. **Berechnung** über eine reine Funktion aus `analytics/` oder vorberechnete Batch-Ergebnisse
3. **Figure-Builder** in `app/figures/`: eine reine Funktion `DataFrame → go.Figure`, ohne Dash-Import, auch mit leeren Daten testbar
4. **Layout-Klasse**, die eine `dbc.Card` liefert
   - Die IDs sind Dictionaries (`{"component": "drawdown", "subcomponent": "graph", "aio_id": ...}`).
   - Die Callbacks nutzen Pattern-Matching.
   - Dadurch lässt sich derselbe Baustein mehrfach und auf verschiedenen Seiten verwenden.

Bausteine erhalten ihren Kontext (Assets, Frequenz, Zeitraum, Preisfeld) einheitlich über URL-Query-Parameter bzw. einen seitenweiten `dcc.Store`. So sind Ansichten als Link teilbar, und die Zurück-Navigation am iPhone funktioniert.

Seiten sind dünne Module, die Bausteine im Bootstrap-Grid anordnen. Es gibt **kein Plugin-System und keine YAML-Seitenkomposition**. Ein neuer Baustein ist ein neues Modul plus eine Zeile auf der Seite.

## 5. Datenversorgung aus der Quelldatenbank

### 5.1 Bekannte Eckdaten (von mir auszufüllen)

- Typ und Version der Quelldatenbank: `<<z. B. PostgreSQL 15 / MariaDB / MS SQL>>`
- Erreichbarkeit: `<<Host / Netz>>`
  - Zugang über einen **nur lesenden** Nutzer
  - Verbindung über `SOURCE_DATABASE_URL` in `.env`
- Relevante Tabellen / Views: `<<…>>`
- Wann ist der Tagesstand in der Quelle vollständig: `<<Uhrzeit>>`

### 5.2 Vorgehen

In Phase 0 inspizierst du die Quelldatenbank **ausschließlich lesend**. Zu klären sind:

- Schema, Datentypen und Primärschlüssel
- Zeitzone der Zeitstempel
- Frequenz und Historienlänge
- ob es Änderungszeitstempel gibt
- ob rückwirkende Korrekturen oder Löschungen vorkommen
- ob adjustierte Kurse vorhanden sind

**Schreibe niemals in die Quelldatenbank.**

Bewerte anschließend die Standardoptionen und empfiehl eine mit Begründung:

1. **PostgreSQL Logical Replication.** Nur möglich, wenn die Quelle PostgreSQL ist und Tabellen 1:1 gespiegelt werden können.
2. **`postgres_fdw` mit SQL-Upsert.** Ebenfalls nur bei PostgreSQL als Quelle.
3. **Python-Sync-Job mit SQLAlchemy.** Unabhängig vom Quellsystem.

Voreinstellung ist Option 3. Sie ist quellunabhängig, integriert sich in das Job-Protokoll und erlaubt Validierung vor dem Schreiben. Option 1 oder 2 nur, wenn sie nachweislich einfacher sind.

### 5.3 Anforderungen an den Sync

- **Drei Stufen:** `staging` (unverändertes Abbild der gelesenen Zeilen plus Lademetadaten) → Validierung → `market` (kanonisches Schema).
- **Inkrementell:** Je Quelltabelle gibt es ein Wasserzeichen in `ops.sync_state`. Ein konfigurierbares Überlappungsfenster (Standard: 10 Tage) wird bei jedem Lauf erneut gelesen, damit rückwirkende Korrekturen ankommen.
- **Idempotent:** `INSERT … ON CONFLICT … DO UPDATE` auf natürlichen Schlüsseln. Wiederholte Läufe erzeugen keine Duplikate. Größere Mengen gehen per `COPY` ins Staging.
- **Mapping:** Quelle → Zielschema und Quellinstrument → Asset stehen ausschließlich in `config/sync_mapping.yaml`.
- **Befehle:**
  - `findash sync check`: Verbindung und Schema-Abgleich, ohne zu schreiben
  - `findash sync run`: inkrementeller Lauf
  - `findash sync full`: vollständiger Neuaufbau
- **Validierung:** Geprüft werden
  - fehlende Pflichtwerte und Duplikate
  - nicht-monotone Reihen
  - Zeitstempel in der Zukunft
  - OHLC-Inkonsistenzen (z. B. `high < low`)
  - Kurssprünge über einer konfigurierbaren Schwelle

  Auffällige Zeilen werden mit Qualitätsstatus gespeichert, **nicht verworfen oder korrigiert**.
- **Fehlerisolation:** Ein fehlerhaftes Asset bricht den Sync der anderen nicht ab.
- **Sichtbarkeit:** Der Zeitpunkt des letzten erfolgreichen Syncs erscheint im Dashboard.

### 5.4 Datenfrequenz

Das Datenmodell unterstützt mehrere Frequenzen je Asset:

- `daily`: Tagesschlusswerte
- optional `snapshot_am` und `snapshot_pm`: zwei tägliche Beobachtungen mit konfigurierbaren Uhrzeiten

Liefert die Quelle Intraday-Daten, wird ein Snapshot aus der letzten Beobachtung **vor oder zum** Zielzeitpunkt innerhalb eines konfigurierbaren Toleranzfensters gebildet. Liegt keine Beobachtung im Fenster, wird der Snapshot als fehlend markiert.

Liefert die Quelle nur Tagesdaten, werden die Snapshot-Funktionen nicht gebaut, sondern als offene Option dokumentiert.

## 6. Datenmodell (Mindestumfang, Details in Phase 0)

Die Datenbank ist in folgende Schemas gegliedert:

- **`ref`**
  - `assets`: aus `config/assets.yaml` synchronisiert; Schlüssel, Name, Typ, Währung, Börsen-Zeitzone, Quellschlüssel, aktiv, Farbe
  - Indexbestandteile und Länderzuordnung (bisher CSV-Dateien)
- **`staging`**
  - Rohabbild der Quelle inklusive `_sync_run_id` und `_loaded_at`
- **`market`**
  - `prices`: `asset_id`, `frequency`, `ts` (`timestamptz`, UTC), `open`, `high`, `low`, `close`, `adj_close`, `volume`, `quality_status`, `sync_run_id`
  - Primärschlüssel `(asset_id, frequency, ts)`
- **`analytics`**
  - vorberechnete Kennzahlen im Long-Format: `asset_id`, `frequency`, `metric`, `window`, `as_of`, `value`, `job_run_id`
- **`forecast`**
  - `model_versions`: Name, Version, Konfiguration (JSONB), Git-Commit
  - `forecasts`: Lauf, Asset, Modellversion, Horizont, Datenstand bis, erwartete Log-Rendite, Quantile (2,5 / 10 / 25 / 50 / 75 / 90 / 97,5 %), P(Rendite > 0), prognostizierte Volatilität, abgeleitete Indexstände
  - `mcmc_diagnostics`, `backtest_results`, `model_selection`
- **`ops`**
  - `job_runs`: Status `pending | running | success | partial_success | failed`, Start, Ende, Parameter, Fehler
  - `job_run_items`: je Schritt und Asset
  - `sync_state`

Vollständige ArviZ-`InferenceData` werden als NetCDF-Dateien in einem Docker-Volume abgelegt. Die Datenbank speichert dazu Pfad, Hash und Posterior-Zusammenfassung.

Schemaänderungen erfolgen **ausschließlich über Alembic**.

## 7. Frontend: Dash + Bootstrap für Browser und iPhone

- **Nur Standard-Bootstrap:** Verwendet werden ausschließlich Komponenten aus `dash-bootstrap-components` und Bootstrap-Utility-Klassen (`g-3`, `mb-3`, `text-body-secondary`, `d-none d-md-block` …).
  - Es gibt keine eigene CSS-Datei.
  - Ist ein Detail ohne CSS nachweislich nicht lösbar, sind wenige kommentierte Zeilen in `app/assets/` erlaubt, mit Rückfrage.
- **Mobile first:**
  - Grid mit `dbc.Row` / `dbc.Col(xs=12, md=6, xl=4)`; auf dem iPhone stehen die Karten untereinander.
  - Navigation über `dbc.Navbar` mit einklappbarem Menü.
  - Filter auf kleinen Bildschirmen in `dbc.Offcanvas` oder `dbc.Collapse`.
- **Homescreen-tauglich:** Viewport-Meta-Tag sicherstellen, `apple-touch-icon` und sprechende Seitentitel bereitstellen.
- **Plotly auf Touch-Geräten:**
  - `responsive=True`, horizontale Legende unter dem Chart, kompakte Ränder, Modebar reduziert.
  - Das Scrollen der Seite über einem Chart darf am iPhone **nicht blockiert** werden. Dafür z. B. `dragmode=False` in Übersichtscharts; Zeitraumwahl über Buttons statt Zoom.
- **Hell/Dunkel:** Bootstrap-5.3-Farbmodus (`data-bs-theme`) mit passendem Plotly-Template aus `dash-bootstrap-templates`.
- **Zustände:** Laden mit `dcc.Loading`; leere Zustände und Fehler als `dbc.Alert`.
- **Statusleiste auf jeder Seite:**
  - letzter erfolgreicher Sync und letzter erfolgreicher Prognoselauf
  - Pipeline-Status als `dbc.Badge`
  - „Keine Anlageberatung.“ und Datenquelle
- **Zeitstempel:** intern UTC, Anzeige in `DISPLAY_TIMEZONE` (Standard `Europe/Berlin`).
- **Export:** CSV der angezeigten Daten über `dcc.Download`; Bilder über die Plotly-Standardfunktion.

Jede Seite muss bei **390 px Breite** vollständig benutzbar sein.

## 8. Fachliche Inhalte

### 8.1 Seiten

| Pfad | Inhalt |
|---|---|
| `/` | Übersicht: Karte je aktivem Asset (letzter Kurs, Veränderung, Mini-Chart, Qualitätsstatus); Weltkarte der Länder-Exposures (bestehendes Feature) |
| `/rueckschau/<asset>` | Detailanalyse eines Assets |
| `/vergleich` | Vergleich beliebig vieler Assets (bisher nur zwei) |
| `/vorschau/<asset>` | Prognosen und Modellgüte |
| `/system` | Job-Läufe, Sync-Status, Datenqualität je Asset, MCMC-Diagnostik-Übersicht |

### 8.2 Rückschau

**Filter:**
- Asset(s)
- Zeitraum: 1W, 1M, 3M, 6M, 1J, 3J, 5J, Max, benutzerdefiniert
- Frequenz, soweit vorhanden
- Preisfeld: Close oder Adj Close
- lineare oder log-Skala
- Indikatoren

**Bausteine:**
- **Kennzahlen:** letzter Kurs und Zeitpunkt, Veränderung zum Vorwert, Renditen 1T/1W/1M/1J, annualisierte Rendite und Volatilität, Sharpe Ratio (risikofreier Satz konfigurierbar, Standard 0), Maximum Drawdown, Hoch/Tief im Zeitraum, VaR und Expected Shortfall (Niveau konfigurierbar), Datenqualitätsstatus
- **Kurschart:** Linie oder Candlestick mit Volumen; gleitende Durchschnitte mit konfigurierbaren Fenstern (Standard 20/50/200 Beobachtungen)
- **Trend-Regression:** linear, exponentiell, log2; die bestehenden Implementierungen werden zu **einer** zusammengeführt
- **Normalisierter Vergleich** (Start = 100) und kumulierte Rendite
- **Drawdown-Chart**
- **Rollierende annualisierte Volatilität**
- **Renditeverteilung:** Histogramm und Boxplot
- **Korrelations-Heatmap** der ausgewählten Assets
- **Snapshot-Zeitreihe** mit sichtbar markierten fehlenden Beobachtungen (nur wenn die Quelle Snapshots ermöglicht)
- **Tabelle der neuesten Beobachtungen** mit Renditen und Qualitätsstatus

**Berechnungen:**
- einfache und logarithmische Renditen
- alle Formeln in `docs/kennzahlen.md` dokumentiert
- Perioden pro Jahr je Frequenz konfigurierbar in `config/analytics.yaml`: 252 für Tagesdaten, bei Snapshots entsprechend angepasst; die ungleichen Abstände zwischen den Snapshots werden als Einschränkung dokumentiert

### 8.3 Vorschau

**Zielgrößen:** logarithmische Renditen und Volatilität. Indexstände und simulierte Pfade werden daraus abgeleitet.

**Horizonte:** konfigurierbar in `config/forecasting.yaml`; Standard sind nächster Datenpunkt, 1, 5 und 20 Handelstage.

**Modelle** mit gemeinsamer Schnittstelle, z. B. `fit(train) -> FittedModel` und `predict(horizons) -> ForecastDistribution` (Samples oder Quantile):

1. **Baseline:** Random Walk mit historischer Mittelwertrendite
2. **ARIMA** (statsmodels)
3. **GARCH(1,1)** mit Student-t-Verteilung (arch)
4. **Bayesianisches Modell** mit PyMC
   - z. B. ein Stochastic-Volatility-Modell mit Student-t-Innovationen nach dem Beispiel der PyMC-Dokumentation
   - auf einem konfigurierbaren Trainingsfenster
   - dokumentierte Priors, fester Seed

**MCMC-Diagnostik je Lauf speichern:**
- Chains, Draws, Tuning-Schritte, Seed
- max. R̂, min. ESS (bulk/tail)
- Divergences, Laufzeit, Status

Standardschwellen (konfigurierbar): R̂ ≤ 1,01, ESS ≥ 400 und 0 Divergences ergeben `ok`. Leichte Verletzungen ergeben `eingeschränkt`, alles andere `fehlgeschlagen`. Ergebnisse ohne Status `ok` werden im Dashboard sichtbar markiert und **nie kommentarlos als valide dargestellt**.

**Backtesting:**
- rollierender Out-of-sample-Backtest (Rolling Origin) je Asset, Horizont und Modell
- Kennzahlen: MAE, RMSE, Trefferquote der Richtung, Abdeckung der 50/80/95-%-Intervalle, CRPS, Laufzeit
- Modellauswahl je Asset und Horizont nach konfigurierbarer Regel; die Ergebnisse **aller** Modelle bleiben gespeichert

**Bausteine der Vorschau-Seite:**
- **Prognose-Fächer:** Historie, Median, 50/80/95-%-Bänder, optional simulierte Pfade
- **Prognosetabelle** je Horizont: erwartete Rendite, erwarteter Stand, P(positiv), Volatilität, Intervalle
- **Modellkarte:** Modell, Version, Laufzeitpunkt, Datenstand, Diagnostik-Badge
- **Modellvergleich** mit Backtest-Kennzahlen
- **Tabelle „Prognose vs. realisiert“**

Ist ein Lauf fehlgeschlagen, zeigt das Dashboard weiter die letzte erfolgreiche Prognose. Sie wird **deutlich als nicht aktuell** markiert (Schwelle konfigurierbar, Standard 36 h).

Texte bleiben beschreibend, z. B. „Das Modell schätzt …“. Es gibt keine Handlungsempfehlungen und keine Kauf- oder Verkaufssignale.

## 9. Nächtlicher Batch

`findash jobs nightly` führt nacheinander aus:

1. Sync
2. Validierung
3. Kennzahlen
4. Modelldaten
5. Modelle und MCMC
6. Prognosen
7. Backtests
8. Modellauswahl
9. Statusabschluss

Anforderungen:

- **Protokoll:** Jeder Schritt wird je Asset in `ops.job_run_items` protokolliert.
- **Fehlerisolation:** Ein fehlerhaftes Asset führt zu `partial_success`, nicht zum Abbruch.
- **Keine Überlappung:** Ein PostgreSQL-Advisory-Lock (`pg_try_advisory_lock`) verhindert gleichzeitige Läufe.
- **Einzelschritte:** Jeder Schritt ist separat aufrufbar, z. B. `findash jobs analytics` oder `findash jobs forecast --asset … --model …`.
- **Test-Optionen:** `--dry-run` sowie `--fast` mit stark reduzierten MCMC-Parametern für lokale Tests.
- **Parallelisierung:** nur über die Standardbibliothek (`concurrent.futures`), konfigurierbar, standardmäßig sequenziell.
- **Zeitplan:** cron oder systemd-Timer auf dem Host, beides dokumentiert in `docs/betrieb.md`. Die Startzeit liegt nach dem Zeitpunkt, an dem die Quelldatenbank ihren Tagesstand vollständig hat.

## 10. Qualität und Tests

- **Unit-Tests:**
  - Renditen, Annualisierung, Drawdown, VaR/ES, Regression
  - Validierungsregeln, Duplikaterkennung
  - Zeitzonen- und Snapshot-Logik
  - Figure-Builder, auch mit leeren Daten
  - Modellschnittstellen mit synthetischen Daten
  - MCMC-Statuslogik
- **Integrationstests gegen echtes PostgreSQL** (testcontainers-python oder Compose-Testprofil):
  - Migrationen
  - Sync inklusive idempotenter Wiederholung und rückwirkender Korrektur
  - Repositories
  - Die Quelldatenbank wird im Test durch eine zweite Datenbank mit Fixture-Daten ersetzt.
- **Callbacks:** Die Callback-Logik steckt in reinen Funktionen und wird dort getestet. Dash-Browsertests nur, wo es praktikabel ist.
- **Demo-Daten:** `findash seed-demo` erzeugt deterministische Beispieldaten, damit die App ohne Quelldatenbank startbar ist.
- **Tooling:** ruff, mypy und import-linter laufen fehlerfrei; pre-commit ist eingerichtet.

## 11. Betrieb und Deployment

- **docker-compose** mit drei Services:
  - `db`: PostgreSQL mit Healthcheck und Volume
  - `app`: gunicorn, Healthcheck auf `/healthz`
  - `worker`: gleiches Image, nur für Jobs per `docker compose run`
- **Ein Image** für `app` und `worker`; Konfiguration nur über `.env` und `config/`.
- **Backups:** nächtliches `pg_dump`, dokumentiert.
- **Zugriff:** Die App ist für LAN oder VPN gedacht. HTTPS-Zugriff vom iPhone von unterwegs läuft über einen Standard-Reverse-Proxy (z. B. Caddy) oder VPN; nur dokumentieren. **Keine eigene Benutzerverwaltung.**
- **README** mit:
  - Überblick und Architektur
  - Installation
  - Konfiguration (Assets, Sync-Mapping, Frequenzen)
  - Sync und Nachtjob
  - Start mit Docker Compose und lokal
  - Modelle und MCMC-Diagnostik
  - Einschränkungen und Datenqualität
  - Haftungsausschluss

## 12. Arbeitsweise in Phasen

Arbeite immer nur an **einer** Phase. Am Ende jeder Phase:

- Tests und Linter sind grün.
- Du committest in kleinen, thematischen Commits.
- Du schreibst eine kurze Zusammenfassung: erledigt, getroffene Entscheidungen, offene Punkte, Vorschlag für die nächste Phase.
- Dann **wartest du auf meine Freigabe**.

**Phase 0 – Bestandsaufnahme und Plan (keine Codeänderungen)**
- Bestehendes Repository analysieren und eine Liste erstellen: *übernehmen / zusammenführen / löschen*. Zu prüfen sind u. a. CSV-Kurspfad, Jinja-Templates, ungenutzte Chart-Fragmente, doppelte Statistik, yfinance, Refresh-Route und AAPL-Seed.
- Quelldatenbank lesend inspizieren (Abschnitt 5.2) und eine Sync-Option empfehlen.
- `docs/plan.md` erstellen mit:
  - Architektur und Datenfluss
  - Datenmodell (Tabellen mit Spalten, Typen, Schlüsseln)
  - Baustein-Katalog und Seiten
  - Modellierungsstrategie
  - Annahmen, Risiken und offenen Fragen

**Phase 1 – Fundament**
- Projektstruktur, `pyproject.toml`, Docker Compose
- Settings und YAML-Validierung, Logging
- Alembic mit den Schemas `ref`, `ops`, `staging`, `market`
- Job-Protokoll, CLI-Skelett
- Tooling (ruff, mypy, import-linter, pre-commit), `seed-demo`

**Phase 2 – Sync**
- Anbindung der Quelldatenbank, Mapping, Staging
- Validierung, Upsert, Wasserzeichen
- `sync check/run/full`
- Integrationstests

**Phase 3 – App-Gerüst**
- Dash Pages mit Bootstrap, Navbar, Statusleiste
- AIO-Baustein-Muster mit den ersten drei Bausteinen: Kennzahlen, Kurschart, Datenqualität
- Übersichtsseite, `/healthz`, gunicorn
- Prüfung bei 390 px Breite

**Phase 4 – Rückschau vollständig**
- Alle Analytics-Funktionen und Bausteine, Vergleichsseite
- Weltkarte und Indexbestandteile migriert (CSV → `ref`)
- Vorberechnete Kennzahlen im Batch
- Altcode entfernt

**Phase 5 – Prognose-Grundlagen**
- Schema `forecast`, Modellschnittstelle
- Baseline, ARIMA, GARCH
- Backtesting und Persistenz

**Phase 6 – Bayes und Vorschau**
- PyMC-Modell, Diagnostik, Artefakt-Speicherung
- Vorschau-Seite und System-Seite

**Phase 7 – Betrieb**
- `jobs nightly` vollständig mit Advisory-Lock
- Zeitplan-Doku, Backups, Reverse-Proxy-Hinweise
- README und Dokumentation final

## 13. Nicht im Umfang

Nicht gebaut werden:

- Benutzerverwaltung und Login
- Handels- oder Orderfunktionen
- Echtzeit-Streaming
- native iOS-App
- Web-Abrufe von Kursdaten
- eigenes Designsystem oder eigene React-Komponenten
- Kauf- oder Verkaufssignale

## 14. Start

Beginne jetzt mit **Phase 0**. Ändere keinen Code und schreibe nicht in die Quelldatenbank. Wenn dir für die Inspektion Zugangsdaten oder Informationen fehlen, frage gezielt danach.

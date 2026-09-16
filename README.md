# Findash

Modulares Finanz-Analyse-Dashboard fuer eine konfigurierbare Liste von Finanz-
instrumenten (Indizes, ETFs, Rohstoffe): Rueckschau (explorative Analyse historischer
Zeitreihen) und Vorschau (probabilistische Prognosen aus nächtlichen Batch-Laeufen).
Nur zu Analyse- und Forschungszwecken -- **keine Anlageberatung**.

Architektur, Datenmodell und Phasenplan: siehe `docs/plan.md`, `docs/auftrag.md` und
`CLAUDE.md`.

## Architektur in Kuerze

- **Dash** (mit `dash-bootstrap-components`) ist die gesamte Web-Oberflaeche, es gibt
  keine separate Flask-Schicht mehr.
- **PostgreSQL** ist die einzige Datenbank, Zugriff ausschliesslich ueber SQLAlchemy in
  `src/findash/storage/`.
- **Kursdaten kommen aus einer Quelldatenbank im lokalen Netzwerk**, nicht aus dem
  Internet (kein yfinance, keine Web-Abrufe). Der Sync (`findash sync`) ist noch nicht
  implementiert, weil die Zugangsdaten zur Quelldatenbank noch fehlen (siehe
  `docs/plan.md`, Abschnitt 8).
- `findash seed-demo` erzeugt deterministische synthetische Kursdaten fuer alle in
  `config/assets.yaml` konfigurierten Assets, damit die App auch ohne Quelldatenbank
  laeuft.

## Installation

```bash
uv sync --extra dev
cp .env.example .env
```

## Datenbank

```bash
docker compose up -d db
uv run alembic upgrade head      # legt ref/ops/staging/market/analytics an
uv run findash seed-demo         # synthetische Demo-Kurse fuer alle Assets
```

## App lokal starten

```bash
uv run python -m findash.app.main
```

Oeffnet unter `http://127.0.0.1:5000`. `/healthz` liefert `{"status": "ok"}`.

## Mit Docker Compose

```bash
docker compose up --build -d db app
docker compose run --rm worker uv run alembic upgrade head
docker compose run --rm worker findash seed-demo
```

Der `worker`-Service nutzt dasselbe Image wie `app`, aber fuer Einzelbefehle statt
Dauerbetrieb (`findash sync ...`, `findash jobs ...`).

## Tests und Qualitaet

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run pre-commit install   # einmalig, danach laufen die Hooks bei jedem Commit
```

`tests/unit/` sind reine, DB-freie Tests (Analytics-Funktionen, Figure-Builder).
`tests/integration/` beruehrt echte Dateien/Dienste (z. B. die Aufbereitung der
Indexbestandteile-CSVs).

## Baukasten: einen neuen Chart-Baustein hinzufuegen

1. Reine Berechnung in `src/findash/analytics/<name>.py` (DataFrame/Series rein, kein
   Dash-, kein DB-Bezug), plus Test in `tests/unit/analytics/`.
2. Reiner Figure-Builder in `src/findash/app/figures/<name>.py`
   (`... -> plotly.graph_objects.Figure`, muss mit leeren Daten funktionieren), plus
   Test in `tests/unit/figures/`.
3. Optional: ein AIO-Baustein in `src/findash/app/blocks/<name>.py`, wenn der Chart
   eigene interaktive Steuerelemente braucht (siehe `KurschartAIO` als Referenz fuer
   Pattern-Matching-Callbacks; `DrawdownAIO` als Referenz fuer einen statischen
   Baustein ohne Callback).
4. Eine Zeile auf der passenden Seite unter `src/findash/app/pages/`.

Rechenintensive Bausteine (Renditedreieck, Rendite-Trichter, Sparplan-Varianten)
gehoeren in den Nachtjob (`findash jobs analytics`, noch nicht verdrahtet) statt in den
Seitenaufruf -- die Analytics-Funktionen dafuer existieren bereits
(`analytics/triangle.py`, `analytics/funnel.py`, `analytics/savings_plan.py`).

## Einschraenkungen

- Sync mit der Quelldatenbank und der naechtliche Batch (Analytics-Vorberechnung,
  Prognosemodelle) sind noch nicht implementiert (Phasen 2, 4-7 in `docs/auftrag.md`).
- Die Weltkarten-Laenderdaten kommen noch aus CSV-Dateien unter
  `data/index_constituents/`, nicht aus der Datenbank (Migration nach
  `ref.index_country_exposure` steht aus).

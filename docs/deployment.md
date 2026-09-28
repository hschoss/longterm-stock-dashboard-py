# Deployment: Anbindung an `dataserver` und Kubernetes-Serving

Dieses Dokument ist gleichzeitig **Plan**, **Fortschrittsprotokoll** und **Anleitung** für die
Aufgabe: „Dashboard an den `dataserver` anschließen und in Kubernetes ausrollen“.

Wird während der Umsetzung fortgeschrieben, damit bei einem Abbruch (z. B. wegen Ratenlimit)
der nächste Durchlauf nahtlos weitermachen kann.

Quelle der Wahrheit für die Zielumgebung: `hallo.md` im Repo-Wurzelverzeichnis
(Briefing des `dataserver`-Betreibers).

## Zielbild

```
  ┌──────────────────────────────┐          ┌──────────────────────────────┐
  │  Kubernetes-Cluster           │          │  Mac mini (192.168.179.x)    │
  │  Namespace: dashboard         │          │                              │
  │                               │          │  PostgreSQL :5432             │
  │  ┌────────────────────────┐   │  SQL     │  DB: dataserver               │
  │  │ findash Dash-App        │──┼─────────▶│  User: readonly_user          │
  │  │ (gunicorn, :5000)       │   │          │  Schemas: derived, core, …   │
  │  └────────────────────────┘   │          └──────────────────────────────┘
  │        ▲                      │
  │   Service (ClusterIP) +       │
  │   Ingress / NodePort          │
  └───────────────────────────────┘
```

Das Projekt behält seine bisherige interne Metadaten-DB (Schemas `ref/ops/…`, verwaltet mit
Alembic) für Konfiguration, Job-Runs und Analyseergebnisse (Phasen 3+). Die ETF-Marktdaten
kommen ab jetzt nicht mehr aus einer lokalen Sync-Kopie, sondern **live per SELECT** aus dem
`dataserver`-Schema `derived`.

## Kernentscheidungen

| # | Entscheidung | Begründung |
|---|--------------|-----------|
| E1 | Bestehende Dash-App verwenden, **kein** React/FastAPI-Splitting wie in `hallo.md` §4 | Vorhandener Code, `dash-bootstrap-components`, AIO-Muster, Deutsche UI-Texte laut CLAUDE.md; pragmatischer und deutlich weniger Angriffsfläche |
| E2 | Zwei getrennte DB-Verbindungen: `database_url` (lokal, RW) für Metadaten/Jobs bleibt; **neue** `dataserver_url` (extern, RO) für Marktdaten | Sauberer Schichtenschnitt; Netzwerk-Constraint (LAN-Only) betrifft nur die externe Verbindung |
| E3 | `dataserver_url` optional. Fehlt sie → App startet, ETF-Seiten zeigen sichtbaren Hinweis „keine Verbindung“ (kein Interpolieren erfundener Daten, siehe CLAUDE.md „Daten“) | Robust gegenüber Fehlkonfiguration, kein stiller Ausfall |
| E4 | SQL-Zugriff auf `derived.*` über eigene Repositories in `storage/repositories/dataserver_*.py`, nur `SELECT`, parametrisiert | Import-Linter-Schicht bleibt heil (SQL nur in `storage/`) |
| E5 | Kubernetes-Manifests unter `k8s/` (plain YAML, kein Helm/Kustomize) | Genügt für einen einzelnen Cluster; keine Overlay-Komplexität nötig |
| E6 | Secret `dataserver-credentials` liefert die vollständige DSN als `DATASERVER_URL`; Passwort landet **nicht** im Repo | Vorgabe aus `hallo.md` §1 und §6 |
| E7 | Frontend-Ausspielung über `Service` + optional `Ingress`; interner Zugriff genügt für die Zielumgebung (LAN) | Kein öffentliches Hosting geplant |

## Umsetzungsplan (Checkliste)

Legende: `[x]` erledigt, `[~]` in Arbeit, `[ ]` offen.

### Phase 1 — DB-Anbindung
- [x] `hallo.md` gelesen, Zielarchitektur verstanden
- [x] Deployment-Doku angelegt (diese Datei)
- [x] `Settings.dataserver_url` (optional, `SecretStr`) in `core/settings.py`
- [x] `storage/dataserver.py`: eigene SQLAlchemy-Engine, `pool_pre_ping`, `default_transaction_read_only`-Guard
- [x] `storage/repositories/dataserver_market.py` mit Funktionen:
  - [x] `list_instruments()` → `derived.v_instrument`
  - [x] `latest_prices()` → letzter Kurs je Index/Listing
  - [x] `price_history(target_index_id, listing_variant, since)` → `derived.v_etf_daily_price_current`
  - [x] `corporate_actions(target_index_id, listing_variant, limit)` → `derived.v_corporate_action_current`
  - [x] `pipeline_status()` → `derived.v_pipeline_status`
  - [x] `data_freshness()` → `derived.v_data_freshness`
- [x] Kleines Health-Probing (`/healthz` bleibt hart; `/readyz` prüft Dataserver-Verbindung)

### Phase 2 — UI-Seiten
- [x] Neue Page `pages/uebersicht.py`: Kartenraster mit letzten Kursen + 1W/1M/YTD/1Y (aus SQL, kein UI-seitiges Interpolieren)
- [x] Neue Page `pages/kurse.py`: Detailansicht je Index mit Zeitraum-Toggle (1M/3M/6M/YTD/1Y/5Y/Max) und Listing-Toggle (US/EU)
- [x] Neue Page `pages/dividenden.py`: Corporate-Actions-Tabelle
- [x] Neue Page `pages/system.py`: Pipeline-Status, `v_data_freshness`
- [x] Bestehende `home.py`/`rueckschau.py` bleiben unverändert (Phase 3+ des Auftrags)
- [x] Fehlende Daten sichtbar markieren (Text „keine Daten“), Alerts bei fehlender `dataserver_url`

### Phase 3 — Container & Kubernetes
- [x] `docker/Dockerfile`: unverändert (setzt `gunicorn` auf `findash.app.main:server`)
- [x] `k8s/namespace.yaml`
- [x] `k8s/secret.example.yaml` (Template, nicht committen mit echten Werten)
- [x] `k8s/deployment.yaml` (Replica=1, resources, liveness `/healthz`, readiness `/readyz`)
- [x] `k8s/service.yaml` (ClusterIP + NodePort-Variante als Kommentar)
- [x] `k8s/ingress.yaml` (optional, gated)
- [x] `k8s/README.md` Kurz-Anleitung: Build, Push, Apply

### Phase 4 — Tests & Qualität
- [x] `ruff check .` grün
- [x] `ruff format --check .` grün
- [x] `mypy` grün (69 Dateien, keine Fehler)
- [x] `lint-imports` grün (6 Contracts KEPT, 0 broken)
- [x] `pytest -q` grün (77 passed)
- [x] Smoke-Test: App importiert, `/healthz` 200, `/readyz` 503 ohne Dataserver, `/etf`, `/kurse`, `/dividenden`, `/system` liefern jeweils 200
- [ ] Unit-Tests für die neuen Repositories gegen echten `dataserver` (offen — braucht Netzwerkzugang zum LAN)
- [ ] Manuelle Prüfung mit `uv run python -m findash.app.main` gegen echten `dataserver` (offen — braucht LAN-Verbindung)

## Fortschrittsprotokoll

Jeder Eintrag: Datum, was getan, offene Punkte. Absteigend, neu oben.

### 2026-09-28
- `hallo.md` gelesen, Doku und Plan erstellt.
- `Settings` um `dataserver_url` (optional) und `dataserver_statement_timeout_ms` erweitert.
- Neue Storage-Engine `storage/dataserver.py` mit `pool_pre_ping`, `default_transaction_read_only = on` und Statement-Timeout beim Connect.
- Neues Repository `storage/repositories/dataserver_market.py` (Instrument, PricePoint, LatestPrice, CorporateAction, PipelineStatus, DataFreshness — je NamedTuple-artige `frozen dataclass`).
- Neue Pages `/etf`, `/kurse`, `/dividenden`, `/system`; `/kurse` mit Zeitraum- und Listing-Auswahl, `/system` mit farbcodierten Pipeline-Badges.
- `/readyz`-Endpoint (503, solange Dataserver nicht erreichbar) in `app/main.py`.
- Kubernetes-Manifeste unter `k8s/`: namespace, secret.example, deployment (SecurityContext, Probes, Ressourcen), service, optional ingress, plus `k8s/README.md`.
- Bekannter Stolperstein Python 3.14 + Dash-Pages: Dash lädt Page-Module ohne `sys.modules`-Eintrag, `@dataclass(frozen=True)` bricht dann in `dataclasses._is_type`. Behoben, indem in Page-Modulen `typing.NamedTuple` statt `@dataclass` genutzt wird (Repository-Datenklassen bleiben `@dataclass`, da regulär importiert). Notiz für später: falls das Team weitere Page-Level-Datenklassen anlegt, dieselbe Regel beachten.
- Alle Qualitätsschranken grün (siehe Phase 4).
- Offen: Deployment gegen echten `dataserver` durchführen — dazu Cluster ins LAN `192.168.179.0/24` bringen bzw. pg_hba-Whitelist erweitern und Secret mit echtem Passwort anlegen.

## Deployment-Anleitung (final)

Sobald Phase 3 grün ist, gilt:

1. Image bauen und pushen:
   ```bash
   docker build -f docker/Dockerfile -t <registry>/findash:<tag> .
   docker push <registry>/findash:<tag>
   ```
2. Secret anlegen (einmalig, echte Werte nicht committen):
   ```bash
   kubectl -n dashboard create secret generic dataserver-credentials \
     --from-literal=DATASERVER_URL='postgresql+psycopg://readonly_user:<PW>@<IP>:5432/dataserver'
   ```
3. Manifeste anwenden:
   ```bash
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/deployment.yaml
   kubectl apply -f k8s/service.yaml
   # Optional:
   kubectl apply -f k8s/ingress.yaml
   ```
4. Erreichbarkeit prüfen:
   ```bash
   kubectl -n dashboard port-forward svc/findash 5000:5000
   curl http://localhost:5000/healthz
   curl http://localhost:5000/readyz
   ```

### Netzwerk-Voraussetzung
Die pg_hba.conf des `dataserver` erlaubt `readonly_user` nur aus `192.168.179.0/24`. Das Cluster
muss entweder im selben Subnetz laufen oder das Cluster-Netz muss dort ergänzt werden.
Alternativ: `Egress`-Regel im Cluster + entsprechende pg_hba-Erweiterung.

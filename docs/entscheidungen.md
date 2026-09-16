# Entscheidungen

Pragmatische Annahmen, die bei Unklarheiten getroffen wurden (siehe `CLAUDE.md`,
Abschnitt „Arbeitsweise"). Jede Zeile nennt die Annahme, den Grund und ab wann sie
überprüft werden sollte.

## Phase 0

- **Bestehende PostgreSQL-Instanz weiterverwenden.** Die lokale `stock_tracker`-DB aus
  `docker-compose.yml` wird für die neuen Schemas `ref`/`staging`/`market`/`analytics`/
  `forecast`/`ops` weiterverwendet statt einer zusätzlichen Datenbank. Grund: keine
  Angabe im Auftrag, dass eine neue Instanz nötig ist; geringerer Betriebsaufwand.
  Überprüfen: falls die Quelldatenbank (Abschnitt 5 im Auftrag) selbst schon PostgreSQL
  ist und Namenskonflikte entstehen könnten.

- **Getrackte Assets unverändert übernommen.** Gold + sechs ETFs aus
  `app/index_config.py` werden 1:1 nach `config/assets.yaml` migriert. Grund: Auftrag
  nennt keine neue Asset-Liste, nur eine „konfigurierbare Liste" als Zielbild.
  Überprüfen: sobald eine aktualisierte Asset-Liste vorliegt.

- **Modellauswahlregel vorgeschlagen: geringster CRPS, Tie-Break RMSE.** Grund: Auftrag
  verlangt „konfigurierbare Regel", nennt aber keinen Standardwert. Endgültig zu
  entscheiden in Phase 5.

- **Sharpe-Risikofreisatz Standard 0.** Deckt sich mit expliziter Angabe im Auftrag
  (§8.2), hier nur als Konfigurationsstandard übernommen, keine eigene Annahme.

- **Sync-Option 3 (Python-Sync-Job) vorläufig empfohlen, ohne Kenntnis des
  Quelldatenbanktyps.** Grund: ist die im Auftrag genannte Voreinstellung und
  funktioniert unabhängig vom Quellsystem. Muss nach Klärung der offenen Fragen in
  `docs/plan.md` Abschnitt 8 bestätigt werden.

## Restrukturierung (nach Phase 0, vor Freigabe von Phase 1)

- **Fundament (Phase 1) und Grundgerüst der App (Phase 3) vorgezogen und
  zusammengelegt, Sync (Phase 2) ausgeklammert.** Grund: expliziter Wunsch des
  Nutzers, zuerst eine erweiterbare Softwarestruktur samt Baukasten für neue
  Charts/Indizes zu bekommen, statt auf die Quelldatenbank-Zugangsdaten zu warten.
  Die offenen Fragen aus `docs/plan.md` Abschnitt 8 bleiben unverändert offen.
  Überprüfen: beim nächsten Phasenwechsel, ob die Phasennummerierung aus
  `docs/auftrag.md` neu zugeordnet werden soll.

- **Altcode (`app/`, CSV-Kurspfad, yfinance, alte Skripte, `requirements.txt`,
  `STATUS.md`/`SETUP.md`/`local.db`) sofort gelöscht statt parallel bestehen zu
  lassen.** Grund: die im vorherigen Turn vorgelegte übernehmen/zusammenführen/
  löschen-Liste (`docs/plan.md` Abschnitt 6) wurde als hinreichende Freigabe
  gewertet, nachdem der Nutzer explizit „Restrukturiere das Projekt" sagte.
  Zwei unbedeutende unversionierte Änderungen (Whitespace/doppelter Import in
  `app/dash_apps/main_dash.py` und `app/services/stats_service.py`) wurden dabei
  verworfen; ihre fachliche Logik ist bereits in `analytics/regression.py` und
  `analytics/comparison.py` aufgegangen.

- **`ref.assets` bekommt (noch) keine Spalte für die Weltkarten-Zuordnung.** Der
  Zusammenhang zwischen einem Asset und seinem Eintrag in den
  Indexbestandteile-CSVs läuft über das neue Feld `index_constituent_key` in
  `config/assets.yaml`/`AssetConfig`, gelesen direkt aus der YAML-Datei, nicht aus
  der DB. Grund: vermeidet eine Schemaänderung, bevor die CSV-Daten überhaupt nach
  `ref.index_country_exposure` migriert sind. Überprüfen: bei dieser Migration
  (`docs/plan.md` Abschnitt 6) draufschauen, ob das Feld dann in die DB wandert.

- **Weltkarten-Hover vereinfacht.** Der alte Hover zeigte zusätzlich
  Steuerdomizil-Basis/-Konfidenz an; der neue `app/figures/world_map.py` zeigt nur
  noch Land, ISO-3 und die gewählte Metrik. Grund: Zeitaufwand für die
  Wiederherstellung des vollen Hover-Customdata stand nicht im Verhältnis zum
  Nutzen in diesem Umbauschritt. Überprüfen: falls die Detailinformation vermisst
  wird, ist sie über `customdata` in `_trace()` leicht nachrüstbar.

- **Docker-Compose-Services umbenannt (`postgres`→`db`, `web`→`app`, neu `worker`).**
  Grund: passend zu den bereits in `CLAUDE.md` vorformulierten Befehlsbeispielen
  und zu `docs/auftrag.md` Abschnitt 11.

- **Ruff-Zeilenlänge auf 120 gesetzt** (statt zunächst 110). Grund: mehrere
  SQLAlchemy-Spaltendefinitionen und Dash-Layout-Aufrufe wurden bei 110 unnötig
  zerrissen; 120 ist noch lesbar und spart Umbrüche ohne Aussagekraft.

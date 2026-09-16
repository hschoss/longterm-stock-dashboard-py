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

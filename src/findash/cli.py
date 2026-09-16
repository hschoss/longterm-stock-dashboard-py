"""findash CLI (Typer), ein Einstiegspunkt mit Unterbefehlen (CLAUDE.md/docs/auftrag.md
Abschnitt 3). sync und jobs nightly sind Platzhalter, bis die Quelldatenbank-
Zugangsdaten aus docs/plan.md Abschnitt 8 geklaert sind."""

from __future__ import annotations

import typer

from findash.core.logging import configure_logging

app = typer.Typer(help="findash: Rueckschau- und Vorschau-Dashboard, CLI fuer Sync und Batch-Jobs.")
sync_app = typer.Typer(help="Sync mit der Quelldatenbank (Phase 2).")
jobs_app = typer.Typer(help="Naechtlicher Batch: Analytics, Modelle, Prognosen (Phase 4+).")
app.add_typer(sync_app, name="sync")
app.add_typer(jobs_app, name="jobs")

_SOURCE_DB_NOT_CONFIGURED = (
    "Noch nicht implementiert: die Zugangsdaten zur Quelldatenbank aus docs/plan.md "
    "Abschnitt 8 (Typ, Host, lesender Nutzer, relevante Tabellen) sind noch offen."
)


@app.command("seed-demo")
def seed_demo_command() -> None:
    """Erzeugt deterministische Demo-Kursdaten, damit die App ohne Quelldatenbank startet."""

    from findash.jobs.seed_demo import seed_demo

    configure_logging()
    summary = seed_demo()
    for symbol, rows in summary.items():
        typer.echo(f"{symbol}: {rows} Kurszeilen")


@sync_app.command("check")
def sync_check() -> None:
    """Prueft Verbindung und Schema-Abgleich mit der Quelldatenbank, ohne zu schreiben."""

    typer.echo(_SOURCE_DB_NOT_CONFIGURED)
    raise typer.Exit(code=1)


@sync_app.command("run")
def sync_run() -> None:
    """Inkrementeller Sync-Lauf."""

    typer.echo(_SOURCE_DB_NOT_CONFIGURED)
    raise typer.Exit(code=1)


@sync_app.command("full")
def sync_full() -> None:
    """Vollstaendiger Neuaufbau aus der Quelldatenbank."""

    typer.echo(_SOURCE_DB_NOT_CONFIGURED)
    raise typer.Exit(code=1)


@jobs_app.command("nightly")
def jobs_nightly(
    fast: bool = typer.Option(False, help="Stark reduzierte MCMC-Parameter fuer lokale Tests."),
    dry_run: bool = typer.Option(False, help="Nur protokollieren, nichts schreiben."),
) -> None:
    """Sync, Validierung, Kennzahlen, Modelle, Prognosen, Backtests, Modellauswahl."""

    typer.echo("Noch nicht implementiert: folgt in Phase 4+ (siehe docs/auftrag.md Abschnitt 9).")
    raise typer.Exit(code=1)


@jobs_app.command("analytics")
def jobs_analytics() -> None:
    """Vorberechnung der Rueckschau-Kennzahlen (Renditedreieck, Trichter, Sparplan, ...)."""

    typer.echo("Noch nicht implementiert: folgt in Phase 4 (siehe docs/plan.md Abschnitt 4).")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

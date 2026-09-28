"""Readonly-Engine fuer den externen `dataserver` (Mac mini im LAN, siehe hallo.md).

Diese Verbindung liest ausschliesslich aus den `derived.*`-Views und darf nichts schreiben.
Der Datenbank-User `readonly_user` erzwingt das serverseitig
(`default_transaction_read_only = on`); zusaetzlich setzt diese Engine ein
Statement-Timeout, damit langsame Ad-hoc-Queries die App nicht blockieren.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from findash.core.settings import Settings, get_settings


class DataserverNotConfigured(RuntimeError):
    """Wird ausgeloest, wenn ETF-Repositories ohne konfigurierten `dataserver_url` genutzt werden."""


def build_dataserver_engine(settings: Settings | None = None) -> Engine:
    """Erzeugt eine Engine fuer den externen Dataserver.

    Wirft `DataserverNotConfigured`, wenn `dataserver_url` nicht gesetzt ist.
    """

    from sqlalchemy import create_engine

    settings = settings or get_settings()
    url = settings.dataserver_url
    if not url:
        raise DataserverNotConfigured(
            "dataserver_url ist nicht gesetzt. Bitte DATASERVER_URL als Umgebungsvariable oder in .env konfigurieren."
        )

    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1_800,
    )

    timeout_ms = int(settings.dataserver_statement_timeout_ms)

    @event.listens_for(engine, "connect")
    def _apply_session_defaults(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        # Zusaetzlicher Schutz: auch clientseitig nur Read-Only-Transaktionen.
        # Der `readonly_user` erzwingt das bereits serverseitig; wir wollen aber
        # auch bei versehentlicher Fehlkonfiguration nichts schreiben.
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {timeout_ms}")
            cursor.execute("SET default_transaction_read_only = on")

    return engine


@lru_cache(maxsize=1)
def get_dataserver_engine() -> Engine | None:
    """Cached-Zugriff auf die Dataserver-Engine, `None` wenn nicht konfiguriert.

    Der Cache verhindert, dass jede HTTP-Anfrage eine neue Engine baut.
    """

    try:
        return build_dataserver_engine()
    except DataserverNotConfigured:
        return None


def dataserver_healthy() -> bool:
    """`True`, wenn eine simple `SELECT 1`-Query gegen den Dataserver funktioniert."""

    engine = get_dataserver_engine()
    if engine is None:
        return False
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from flask import Flask, current_app, g

try:
    from sqlalchemy import create_engine
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker
except ModuleNotFoundError:  # pragma: no cover - optional in bare test environments
    Engine = Any
    Session = Any
    create_engine = None
    sessionmaker = None


def init_db(app: Flask) -> None:
    if create_engine is None or sessionmaker is None:
        app.extensions["db_engine"] = None
        app.extensions["db_session_factory"] = None
        return

    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URL"], pool_pre_ping=True)
    app.extensions["db_engine"] = engine
    app.extensions["db_session_factory"] = sessionmaker(bind=engine, autoflush=False)


def get_engine() -> Engine:
    if current_app.extensions.get("db_engine") is None:
        raise RuntimeError("SQLAlchemy is not installed in the current environment.")
    return current_app.extensions["db_engine"]


def get_session() -> Session:
    if current_app.extensions.get("db_session_factory") is None:
        raise RuntimeError("SQLAlchemy is not installed in the current environment.")
    if "db_session" not in g:
        session_factory = current_app.extensions["db_session_factory"]
        g.db_session = session_factory()
    return g.db_session


def close_db(error: object | None = None) -> None:
    session = g.pop("db_session", None)
    if session is not None:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    if current_app.extensions.get("db_session_factory") is None:
        raise RuntimeError("SQLAlchemy is not installed in the current environment.")
    session_factory = current_app.extensions["db_session_factory"]
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

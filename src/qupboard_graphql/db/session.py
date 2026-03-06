"""
SQLAlchemy engine and session management for qupboard_graphql.

Provides a shared module-level :class:`~sqlalchemy.engine.Engine` and a
FastAPI-compatible generator dependency that yields a per-request
:class:`~sqlalchemy.orm.Session`.
"""

from typing import Any, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from qupboard_graphql.config import settings


def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enable SQLite foreign key enforcement for each DB-API connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine with backend-specific connect args.

    Args:
        database_url: Optional SQLAlchemy URL. Defaults to ``settings.DATABASE_URL``.

    Returns:
        Engine: Configured SQLAlchemy engine.
    """
    resolved_url = database_url or settings.DATABASE_URL
    url = make_url(resolved_url)
    connect_args: dict[str, Any] = {}

    # SQLite needs thread-check disabling for our app/test usage with FastAPI.
    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False

    engine = create_engine(resolved_url, connect_args=connect_args)

    # Enforce FK constraints in SQLite (off by default unless pragma is set per connection).
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _set_sqlite_pragma)

    return engine


engine = get_engine()
session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session.

    Opens a new session before each request and ensures it is closed
    afterwards, even if an exception is raised.

    Yields:
        An active :class:`~sqlalchemy.orm.Session` bound to the module engine.
    """
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()

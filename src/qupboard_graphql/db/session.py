"""
SQLAlchemy async engine and session management for qupboard_graphql.

Provides a shared module-level :class:`~sqlalchemy.ext.asyncio.AsyncEngine` and a
FastAPI-compatible async generator dependency that yields a per-request
:class:`~sqlalchemy.ext.asyncio.AsyncSession`.
"""

from typing import Any, AsyncGenerator

from sqlalchemy import event
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from qupboard_graphql.config import settings


def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enable SQLite foreign key enforcement for each DB-API connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(database_url: str | None = None) -> AsyncEngine:
    """Create a SQLAlchemy async engine with backend-specific connect args.

    Args:
        database_url: Optional SQLAlchemy URL. Defaults to ``settings.DATABASE_URL``.

    Returns:
        AsyncEngine: Configured SQLAlchemy async engine.
    """
    resolved_url = database_url or settings.DATABASE_URL
    url = make_url(resolved_url)
    connect_args: dict[str, Any] = {}

    # SQLite needs thread-check disabling for our app/test usage with FastAPI.
    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False

    engine = create_async_engine(resolved_url, connect_args=connect_args)

    # Enforce FK constraints in SQLite (off by default unless pragma is set per connection).
    if url.get_backend_name() == "sqlite":
        event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)

    return engine


engine = get_engine()
session_factory = async_sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a SQLAlchemy async session.

    Opens a new session before each request and ensures it is closed
    afterwards, even if an exception is raised.

    Yields:
        An active :class:`~sqlalchemy.ext.asyncio.AsyncSession` bound to the module engine.
    """
    async with session_factory() as db:
        yield db

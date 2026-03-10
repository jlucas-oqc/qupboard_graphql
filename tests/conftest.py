"""Pytest fixtures for API tests.

This module provides two fixture groups:
- engine/session fixtures that create and wire an isolated per-test database
- object/data fixtures that load calibration payloads and create test records
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import event
from sqlalchemy.pool import StaticPool

from qupboard_graphql.api.app import get_app
from qupboard_graphql.db.database import Base
from qupboard_graphql.db import session as session_module
from qupboard_graphql.db.models import HardwareModelORM
from qupboard_graphql.schemas.hardware_model import HardwareModel

data_path: Path = Path(__file__).parent / "data"

_JSON_HEADERS: dict[str, str] = {"Content-Type": "application/json"}


def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enable SQLite foreign key enforcement for each DB-API connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------------------------------------------------------------------------
# Engine/session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine() -> Iterator[AsyncEngine]:
    """Create and tear down an isolated in-memory SQLAlchemy async engine.

    Yields:
        AsyncEngine: A per-test SQLite in-memory async engine with all ORM tables created.
    """
    import asyncio

    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())

    original_engine: AsyncEngine = session_module.engine
    session_module.engine = engine
    try:
        yield engine
    finally:
        session_module.engine = original_engine

        async def _teardown():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            await engine.dispose()

        asyncio.run(_teardown())


@pytest.fixture()
def db_session_factory(db_engine: AsyncEngine) -> Iterator[async_sessionmaker[AsyncSession]]:
    """Build an async session factory bound to the test engine and patch app globals.

    Args:
        db_engine: Per-test SQLAlchemy async engine fixture.

    Yields:
        async_sessionmaker[AsyncSession]: Factory that creates sessions bound to ``db_engine``.
    """
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=db_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    original_session_factory = session_module.session_factory
    session_module.session_factory = factory
    try:
        yield factory
    finally:
        session_module.session_factory = original_session_factory


@pytest.fixture()
def db_session(db_session_factory: async_sessionmaker[AsyncSession]) -> Iterator[AsyncSession]:
    """Provide a SQLAlchemy async session bound to the current test engine.

    Args:
        db_session_factory: Async session factory fixture bound to the test DB.

    Yields:
        AsyncSession: Open SQLAlchemy async session for the current test.
    """
    import asyncio

    session: AsyncSession = db_session_factory()
    try:
        yield session
    finally:
        asyncio.run(session.close())


@pytest.fixture()
def app_client(db_session_factory: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    """Create a ``TestClient`` backed by the in-memory test database.

    Args:
        db_session_factory: Async session factory fixture used to ensure DB wiring is patched.

    Yields:
        TestClient: FastAPI test client with server exceptions enabled.
    """
    app = get_app()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# ---------------------------------------------------------------------------
# Object/data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def raw_calibration() -> str:
    """Load the calibration JSON payload used in tests.

    Returns:
        str: Raw JSON string loaded from ``tests/data/calibration_pydantic.json``.
    """
    with open(data_path / "calibration_pydantic.json") as f:
        return f.read()


@pytest.fixture(scope="session")
def hardware_model(raw_calibration: str) -> HardwareModel:
    """Parse and validate a shared ``HardwareModel`` instance.

    Args:
        raw_calibration: Raw calibration payload fixture.

    Returns:
        HardwareModel: Parsed model reused across the test session.
    """
    return HardwareModel.model_validate_json(raw_calibration)


@pytest.fixture()
def hardware_model_uuid(app_client: TestClient, raw_calibration: str, db_session: AsyncSession) -> str:
    """Create a hardware model via REST and return its UUID.

    Args:
        app_client: FastAPI test client fixture.
        raw_calibration: Raw calibration payload fixture.
        db_session: SQLAlchemy async session fixture.

    Returns:
        str: UUID of the created hardware model.
    """
    import asyncio

    # Create the model and capture its UUID
    post_response = app_client.post("/rest/logical-hardware", content=raw_calibration, headers=_JSON_HEADERS)
    assert post_response.status_code == 201
    model_uuid = post_response.json()

    # Verify the POST wrote the row to the current test database.
    orm_obj = asyncio.run(HardwareModelORM.get_by_uuid(db_session, uuid.UUID(model_uuid)))
    assert orm_obj is not None
    return model_uuid

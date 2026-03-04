import os
from pathlib import Path

# Set before any app modules are imported so session.py never creates a file-based DB
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from qupboard_graphql.api.app import get_app
from qupboard_graphql.db.database import Base
from qupboard_graphql.db.session import get_db
from qupboard_graphql.schemas.hardware_model import HardwareModel

data_path = Path(__file__).parent / "data"

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
_JSON_HEADERS = {"Content-Type": "application/json"}


@pytest.fixture(scope="session")
def raw_calibration() -> str:
    """Load the raw calibration JSON once for the entire test session."""
    with open(data_path / "calibration_pydantic.json") as f:
        return f.read()


@pytest.fixture(scope="session")
def hardware_model(raw_calibration: str) -> HardwareModel:
    """Parsed and validated HardwareModel, shared across the session."""
    return HardwareModel.model_validate_json(raw_calibration)


@pytest.fixture()
def hardware_model_uuid(test_client, raw_calibration):
    # Create the model and capture its UUID
    post_response = test_client.post("/rest/logical-hardware", content=raw_calibration, headers=_JSON_HEADERS)
    assert post_response.status_code == 201
    model_uuid = post_response.json()
    return model_uuid


@pytest.fixture(scope="session")
def db_engine():
    """
    Create a single in-memory SQLite engine for the whole test session and
    build all tables once.  Dropped when the session ends.
    """
    engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Session:
    """
    Yield a transactional SQLAlchemy session that is rolled back after each
    test, keeping tests fully isolated without recreating the schema.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestingSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def test_client(db_session: Session):
    """
    FastAPI TestClient with ``get_db`` overridden to use the per-test
    transactional session, so every request and the test itself share the
    same transaction (which is rolled back when the test finishes).
    """
    app = get_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    app.dependency_overrides.clear()

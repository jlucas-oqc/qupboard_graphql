from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from qupboard_graphql.config import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the shared engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_db():
    """FastAPI dependency that yields a SQLAlchemy session."""
    SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

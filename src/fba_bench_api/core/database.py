import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Centralized database URL resolution via centralized settings with sensible default for development
from fba_bench_core.config import get_settings

_settings = get_settings()
DATABASE_URL = _settings.preferred_db_url or "sqlite:///./fba_bench.db"

# Base metadata used across the backend and Alembic autogenerate
from fba_bench_api.models.base import Base

# Create engine with SQLite-specific connect args only when needed
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# Session factory bound to the engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Note: Old ExperimentConfigDB, SimulationConfigDB, and TemplateDB models have been removed
# as they were legacy/orphan code not used by the persistence layer.
# See fba_bench_api/models/ for active ORM models.


def create_db_tables():
    """DEPRECATED: Prefer create_db_tables_async in database_async.py"""
    Base.metadata.create_all(bind=engine)


# FastAPI dependency: one-session-per-request with explicit transaction boundary
def get_db_session():
    """
    Yields a SQLAlchemy Session per-request.
    Commits on success, rolls back on exception, always closes.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

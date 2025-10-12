import os
import sys
import types
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel, ConfigDict, Field

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


if "fba_bench_core" not in sys.modules:
    core_module = types.ModuleType("fba_bench_core")
    benchmarking_module = types.ModuleType("fba_bench_core.benchmarking")
    engine_module = types.ModuleType("fba_bench_core.benchmarking.engine")

    class EngineConfig(BaseModel):
        """Lightweight test double for the core EngineConfig model."""

        model_config = ConfigDict(extra="allow")

    class EngineReport(BaseModel):
        """Lightweight test double for the core EngineReport model."""

        status: str = "completed"
        details: dict[str, object] = Field(default_factory=dict)
        model_config = ConfigDict(extra="allow")

    async def run_benchmark(config: EngineConfig) -> EngineReport:  # pragma: no cover - simple stub
        """Fallback async benchmark stub for tests when the core package is unavailable."""

        return EngineReport(details={"config": config.model_dump()})

    engine_module.EngineConfig = EngineConfig
    engine_module.EngineReport = EngineReport
    engine_module.run_benchmark = run_benchmark

    benchmarking_module.engine = engine_module
    core_module.benchmarking = benchmarking_module
    sys.modules["fba_bench_core"] = core_module
    sys.modules["fba_bench_core.benchmarking"] = benchmarking_module
    sys.modules["fba_bench_core.benchmarking.engine"] = engine_module

from api.db import Base, get_db
from api.models import User
from api.security.passwords import hash_password
from fastapi.testclient import TestClient
from api.server import app

# Shared test DB file
TEST_DB = "test_shared.db"
db_path = Path(TEST_DB)
if db_path.exists():
    db_path.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///./{TEST_DB}"
engine = create_engine(
    os.environ["DATABASE_URL"], poolclass=StaticPool, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_shared_db():
    """Create tables once for all tests."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass  # Windows lock

@pytest.fixture(autouse=True)
def clean_db():
    """Clean users table before each test."""
    db = TestingSessionLocal()
    try:
        db.execute(text("DELETE FROM users"))
        db.commit()
    except Exception:
        pass  # Table may not exist
    finally:
        db.close()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def test_user():
    """Create a test user."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="test-uuid-123",
            email="test@example.com",
            password_hash=hash_password("Password123!"),
            is_active=True,
            subscription_status=None,
            created_at=datetime.now(ZoneInfo("UTC")),
            updated_at=datetime.now(ZoneInfo("UTC")),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()

@pytest.fixture
def auth_token(test_user):
    from api.security.jwt import create_access_token
    claims = {"sub": test_user.id, "email": test_user.email}
    return create_access_token(claims)
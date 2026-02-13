import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Add src to sys.path immediately to ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from fba_bench_api.api.security import create_access_token, hash_password
from fba_bench_api.core.database import engine, get_db_session as app_get_db
from fba_bench_api.models.base import Base
from fba_bench_api.models.user import User


def pytest_configure(config):
    """Pytest hook to add src to sys.path early in test session."""
    # sys.path is already updated at module level, but we set env var here
    os.environ["TESTING"] = "true"


TEST_DB = "test_shared.db"
DB_PATH = Path(TEST_DB)

if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///./{TEST_DB}"


@pytest.fixture(scope="session")
def app():
    """Create the FastAPI app for tests."""
    from fba_bench_api.server.app_factory import create_app

    app = create_app()

    def override_get_db():
        yield from app_get_db()

    app.dependency_overrides[app_get_db] = override_get_db

    return app


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables once for the test session (consolidated)."""
    # Ensure all ORM models are imported so Base.metadata contains every table.
    from fba_bench_api.models import agent, contact_message, experiment, simulation, user  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except PermissionError:
            pass  # Windows lock


@pytest.fixture(scope="function")
def db_session():
    generator = app_get_db()
    db = next(generator)
    try:
        yield db
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


@pytest.fixture(autouse=True)
def clean_db(db_session):
    """Clean users table before each test."""
    try:
        db_session.execute(text("DELETE FROM users"))
        db_session.commit()
    except Exception:
        pass  # Table may not exist yet


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        id="test-uuid-123",
        email="test@example.com",
        password_hash=hash_password("Password123!"),
        is_active=True,
        subscription_status=None,
        created_at=datetime.now(ZoneInfo("UTC")),
        updated_at=datetime.now(ZoneInfo("UTC")),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user):
    claims = {"sub": test_user.id, "email": test_user.email}
    return create_access_token(claims)


@pytest.fixture(scope="session")
def validation_test_data():
    """Shared validation test data for all validation tests."""
    return {
        "valid_user": {"email": "valid@example.com", "password": "ValidPass123!"},
        "invalid_email": {"email": "invalid-email", "password": "ValidPass123!"},
        "valid_scenario": {
            "name": "valid_scenario",
            "description": "Valid test scenario",
        },
        "invalid_scenario": {"name": "", "description": "Invalid empty name"},
        "valid_config": {"model": "gpt-4", "temperature": 0.7},
        "invalid_config": {"model": "", "temperature": -1.0},
    }


@pytest.fixture(scope="session")
def performance_test_config():
    """Configuration fixture for performance tests."""
    return {
        "load_factor": int(os.getenv("PERF_LOAD_FACTOR", "10")),
        "duration_seconds": int(os.getenv("PERF_DURATION", "60")),
        "concurrency": int(os.getenv("PERF_CONCURRENCY", "5")),
        "warmup_seconds": int(os.getenv("PERF_WARMUP", "10")),
        "metrics_thresholds": {
            "response_time_ms": 500,
            "throughput_rps": 10,
            "error_rate_percent": 1.0,
        },
    }


@pytest.fixture(scope="module")
def api_client_with_auth(app, test_user):
    """API client with authentication for integration tests."""
    client = TestClient(app)
    token = create_access_token({"sub": test_user.id, "email": test_user.email})
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture(scope="function", autouse=True)
def reset_state():
    """Reset global state between tests to ensure isolation."""
    yield
    # Add per-test cleanup for shared singletons or caches here as needed.

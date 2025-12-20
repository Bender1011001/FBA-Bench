from __future__ import annotations

"""
Async SQLAlchemy session/engine for non-blocking DB I/O.

- Uses async drivers (aiosqlite for SQLite, asyncpg for Postgres)
- Provides FastAPI dependency get_async_db_session() (one session per-request)
- create_db_tables_async() helper to initialize schema at startup if needed
"""

import importlib
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from fba_bench_api.models.base import Base
from fba_bench_core.config import get_settings

# Internal flag to ensure schema initialization occurs at least once
_schema_initialized: bool = False


def _resolve_async_url() -> str:
    """
    Convert synchronous SQLAlchemy URL to async-driver URL when possible.
    - sqlite:///path -> sqlite+aiosqlite:///path
    - postgresql://... -> postgresql+asyncpg://...
    Otherwise, return as-is (user must ensure correct async dialect).
    """
    settings = get_settings()
    raw = settings.preferred_db_url or "sqlite:///./fba_bench.db"
    if raw.startswith("sqlite:///"):
        return f"sqlite+aiosqlite:///{raw.split('sqlite:///', 1)[1]}"
    if raw.startswith("postgresql://"):
        return f"postgresql+asyncpg://{raw.split('postgresql://', 1)[1]}"
    return raw


# Create async engine + sessionmaker
ASYNC_DATABASE_URL: str = _resolve_async_url()

_engine_kwargs: dict = {
    "future": True,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

if ASYNC_DATABASE_URL.startswith("sqlite"):
    # SQLite does not support pool_size/max_overflow with standard NullPool/StaticPool
    if ASYNC_DATABASE_URL.endswith(":memory:") or "mode=memory" in ASYNC_DATABASE_URL:
        _engine_kwargs["poolclass"] = StaticPool
        _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Postgres and others
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10

async_engine: AsyncEngine = create_async_engine(ASYNC_DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
)


async def create_db_tables_async() -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    """
    Initialize DB schema using async engine.

    Safe to call at startup; no-ops if tables already exist.
    Ensures ORM model modules are imported so their tables are registered
    on Base.metadata before calling create_all.
    """
    # Import ORM models to register tables
    for mod in (
        "fba_bench_api.models.agent",
        "fba_bench_api.models.experiment",
        "fba_bench_api.models.simulation",
    ):
        try:
            importlib.import_module(mod)
        except Exception:
            # Best-effort import; avoid failing startup if optional modules error
            pass

    async with async_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(bind=sync_conn, checkfirst=True)
        )
    _schema_initialized = True


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI async dependency.
    Yields an AsyncSession per request; commits on success and rolls back on errors.
    Ensures DB schema is initialized at least once (defensive for tests that bypass lifespan).
    """
    # Defensive: initialize schema (lifespan may be bypassed in some tests)
    try:
        await create_db_tables_async()
    except Exception:
        # Don't block request if init races; subsequent operations may still succeed
        pass

    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

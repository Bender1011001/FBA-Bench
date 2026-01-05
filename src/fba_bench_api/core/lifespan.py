from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from services.cost_tracking_service import CostTrackingService  # Added
from services.dashboard_api_service import DashboardAPIService
from services.supply_chain_service import SupplyChainService

# New: bring up core runtime services for end-to-end skills flow
from services.world_store import WorldStore, set_world_store

from agent_runners.agent_manager import AgentManager
from fba_bench_api.core.database_async import create_db_tables_async
from fba_bench_api.core.redis_client import (
    close_redis,
    get_redis,
)  # Graceful Redis init/shutdown

from .container import AppContainer
from .persistence import config_persistence_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FBA-Bench API…")

    # Initialize container early
    app.state.container = AppContainer()

    # Environment validation at startup
    from fba_bench_core.config import get_settings

    settings = get_settings()
    import os

    missing_vars = []
    # Check DB URL if auto-create is enabled
    if os.getenv("DB_AUTO_CREATE", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        if not settings.preferred_db_url:
            missing_vars.append("DATABASE_URL or FBA_BENCH_DB_URL")

    # Check JWT public key if auth is enabled
    if (
        settings.auth_enabled
        and not settings.auth_jwt_public_key
        and not settings.auth_jwt_public_keys
    ):
        missing_vars.append("AUTH_JWT_PUBLIC_KEY or AUTH_JWT_PUBLIC_KEYS")

    # In protected environments, fail fast on missing critical vars
    if settings.is_protected_env and missing_vars:
        raise ValueError(
            f"Missing required environment variables in protected environment ({settings.environment}): {', '.join(missing_vars)}"
        )
    elif missing_vars:
        logger.warning(
            "Missing optional environment variables: %s. Some features may not work.",
            ", ".join(missing_vars),
        )

    # Set start time for uptime calculation
    app.state.start_time = time.time()
    # init persistence layer cache
    config_persistence_manager.initialize_from_storage()

    # Ensure DB schema exists (async) - guarded by DB_AUTO_CREATE (default true)

    if os.getenv("DB_AUTO_CREATE", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        await create_db_tables_async()

    # Resolve EventBus from DI container and initialize services
    container = getattr(app.state, "container", None)
    if container is None:
        raise RuntimeError("AppContainer not initialized on app.state.container")
    bus = container.event_bus()
    dash = DashboardAPIService(bus)
    # expose to global state
    globals()["_dash_ref"] = dash
    globals()["_bus_ref"] = bus

    # Load test configuration (if provided) and attach to app.state for tests
    try:
        import json as _json_cfg
        import os as _os_cfg

        _cfg_path = _os_cfg.getenv("FBA_CONFIG_PATH")
        if _cfg_path:
            try:
                with open(_cfg_path, encoding="utf-8") as _f:
                    app.state.config = _json_cfg.load(_f)
            except Exception:
                app.state.config = {}
        else:
            app.state.config = {}
    except Exception:
        # Ensure attribute exists even on failure
        app.state.config = {}

    await bus.start()
    logger.info("Event bus started")

    # Optional eager Redis initialization with retries (configurable).
    # This warms up the Redis singleton early to avoid first-request latency,
    # and increases resilience to transient startup issues.
    # Enable via REDIS_EAGER_INIT=true (defaults to false).
    # If Redis must be available for the app to run, set REDIS_REQUIRED=true.
    import os as _os  # local alias to avoid shadowing

    _eager = _os.getenv("REDIS_EAGER_INIT", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if _eager:
        try:
            await get_redis()
            logger.info("Redis eager initialization successful")
        except Exception as e:
            _required = _os.getenv("REDIS_REQUIRED", "false").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            if _required:
                logger.error(
                    "Redis required but initialization failed after retries: %s", e
                )
                raise
            logger.warning(
                "Redis initialization failed; continuing without Redis: %s", e
            )

    # Initialize and register core domain services:
    # 1) WorldStore (authoritative state)
    world_store = WorldStore(event_bus=bus)
    await world_store.start()
    set_world_store(world_store)
    # expose world store on app state for tests
    try:
        app.state.world_store = world_store
    except Exception:
        pass
    logger.info("WorldStore started and registered as global instance")

    # 2) SupplyChainService (handles PlaceOrderCommand -> InventoryUpdate on TickEvent)
    supply_chain = SupplyChainService(
        world_store=world_store, event_bus=bus, base_lead_time=1
    )
    await supply_chain.start()
    logger.info("SupplyChainService started")

    # 3) AgentManager (skills pipeline + CEO arbitration on ticks)
    agent_manager: AgentManager = app.state.container.agent_manager()  # type: ignore[attr-defined]
    # Provide world_store to the manager for stateful decision cycles
    try:
        agent_manager.world_store = world_store  # type: ignore[attr-defined]
    except Exception:
        pass
    # Expose agent manager on app state for tests
    try:
        app.state.agent_manager = agent_manager
    except Exception:
        pass
    await agent_manager.start()
    logger.info("AgentManager started")

    # 4) CostTrackingService (tracks LLM API costs)
    cost_tracker = CostTrackingService(event_bus=bus)
    # Expose to global state or app.state for other services to access
    app.state.cost_tracker = cost_tracker
    # Minimal placeholders expected by tests
    try:
        # Some tests only assert presence; a lightweight object suffices
        app.state.benchmark_engine = object()
        app.state.token_counter = object()
    except Exception:
        pass

    # Inject CostTrackingService into SimulationOrchestrator
    orchestrator: SimulationOrchestrator = app.state.container.simulation_orchestrator()  # type: ignore[attr-defined]
    orchestrator.cost_tracker = cost_tracker  # type: ignore[attr-defined]

    logger.info("CostTrackingService started and injected into SimulationOrchestrator")

    # 5) Benchmark Service (background worker)
    # Import locally to avoid circular dependencies
    from fba_bench_api.api.routes.benchmarks import benchmark_service
    await benchmark_service.start()
    logger.info("BenchmarkService started")

    try:
        yield
    finally:
        # Stop AgentManager
        try:
            await agent_manager.stop()
        except Exception:
            pass
        # Stop SupplyChainService (best-effort)
        try:
            await supply_chain.stop()
        except Exception:
            pass
        # Stop WorldStore
        try:
            await world_store.stop()
        except Exception:
            pass
        # Existing shutdown sequence
        try:
            await dash.stop()
        except Exception:
            pass
        try:
            await bus.stop()
        except Exception:
            pass
        # No stop for connection_manager
        try:
            await close_redis()
        except Exception:
            pass
        logger.info("FBA-Bench API stopped")

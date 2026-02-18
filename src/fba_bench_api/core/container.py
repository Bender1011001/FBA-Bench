from __future__ import annotations

"""
Dependency Injection Container for FBA-Bench

This container centralizes construction and lifecycle for core services:
- EventBus (singleton)
- SimulationOrchestrator (factory with env-driven defaults)
- AgentManager (factory, wired to EventBus)

Environment variables for SimulationOrchestrator defaults:
- SIM_TICK_INTERVAL (float, default "1.0")
- SIM_MAX_TICKS (int, optional, default unset)
- SIM_TIME_ACCELERATION (float, default "1.0")
- SIM_SEED (int, optional, default unset)

Usage (FastAPI):
- In app startup (create_app), instantiate AppContainer and attach to `app.state.container`
- In lifespan, resolve `event_bus = app.state.container.event_bus()` and start it
- Resolve factories on demand in routes/services to avoid upfront heavy init
"""

import os
from typing import Optional

from agent_runners.agent_manager import AgentManager
from dependency_injector import containers, providers
from fba_bench_core.simulation_orchestrator import SimulationOrchestrator
from fba_bench_api.core.database_async import AsyncSessionLocal
from fba_bench_api.core.persistence_async import AsyncPersistenceManager

# Core services
from fba_events.bus import InMemoryEventBus as EventBus  # singleton


def _build_sim_config_from_env() -> dict:
    """Build SimulationConfig from environment with safe defaults."""
    # tick interval
    try:
        tick_interval = float(os.getenv("SIM_TICK_INTERVAL", "1.0"))
    except Exception:
        tick_interval = 1.0

    # max ticks (optional)
    max_ticks: Optional[int]
    mt_env = os.getenv("SIM_MAX_TICKS")
    try:
        max_ticks = int(mt_env) if mt_env not in (None, "", "none", "null") else None
    except Exception:
        max_ticks = None

    # time acceleration
    try:
        time_accel = float(os.getenv("SIM_TIME_ACCELERATION", "1.0"))
    except Exception:
        time_accel = 1.0

    # seed (optional)
    seed: Optional[int]
    seed_env = os.getenv("SIM_SEED")
    try:
        seed = int(seed_env) if seed_env not in (None, "", "none", "null") else None
    except Exception:
        seed = None

    return {
        "tick_interval_seconds": tick_interval,
        "max_ticks": max_ticks,
        "time_acceleration": time_accel,
        "seed": seed,
        "auto_start": False,
    }


class AppContainer(containers.DeclarativeContainer):
    """Declarative DI container for backend core services."""

    # Optional nested configuration (not required for env-based defaults)
    config = providers.Configuration()

    # Singleton EventBus
    event_bus = providers.Singleton(EventBus)

    # Simulation config singleton (env-driven)
    simulation_config = providers.Singleton(_build_sim_config_from_env)

    # Orchestrator singleton (shared across requests)
    simulation_orchestrator = providers.Singleton(
        SimulationOrchestrator,
        config=simulation_config(),
        cost_tracker=None,  # Placeholder, will be set in lifespan
    )

    # AgentManager singleton (shared across requests)
    agent_manager = providers.Singleton(
        AgentManager,
        event_bus=event_bus,
        # Optional dependencies can be wired as needed in future iterations
        world_store=None,
        budget_enforcer=None,
        trust_metrics=None,
        agent_gateway=None,
        # Defaults for baseline bot dir and OpenRouter key (env may override elsewhere)
        bot_config_dir="baseline_bots/configs",
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    # Database & Persistence
    db_session = providers.Resource(AsyncSessionLocal)
    persistence = providers.Factory(
        AsyncPersistenceManager,
        db=db_session,
    )

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fba_bench_api.api.errors import SimulationNotFoundError, SimulationStateError
from fba_bench_api.core.database_async import get_async_db_session
from fba_bench_api.core.persistence_async import AsyncPersistenceManager
from fba_bench_api.core.redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/simulation", tags=["Simulation"])

# Existing orchestrator-based endpoints remain above replaced block are now removed.
# We will keep backward-compatible start/stop/pause/resume only if wired elsewhere.
# New minimal simulation run management (in-memory) per acceptance criteria.

SimStatus = Literal["pending", "running", "stopped", "completed", "failed"]


class SimulationCreate(BaseModel):
    experiment_id: Optional[str] = Field(
        None, description="Optional experiment id to associate"
    )
    metadata: Optional[dict] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"experiment_id": None, "metadata": {"note": "ad-hoc run"}}
        }
    )


class Simulation(BaseModel):
    id: str
    experiment_id: Optional[str] = None
    status: SimStatus
    websocket_topic: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[dict] = None


class SpeedUpdate(BaseModel):
    speed: float = Field(
        ..., gt=0, description="Time acceleration multiplier (>0). 1.0=real-time"
    )


def get_pm(db: AsyncSession = Depends(get_async_db_session)) -> AsyncPersistenceManager:
    return AsyncPersistenceManager(db)


# Utilities
import uuid as _uuid


def _uuid4() -> str:
    return str(_uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _topic(sim_id: str) -> str:
    return f"simulation-progress:{sim_id}"


async def _publish_status(sim_id: str, status_value: str) -> None:
    # Publish to Redis if available; swallow errors to avoid test flakiness
    try:
        redis = await get_redis()
        await redis.publish(_topic(sim_id), status_value)
    except Exception as exc:
        logger.info("Redis publish skipped/unavailable: %s", exc)


# Routes


@router.post(
    "",
    response_model=Simulation,
    status_code=status.HTTP_201_CREATED,
    description="Create a simulation record (pending). Returns websocket topic to subscribe for progress.",
)
async def create_simulation(
    payload: SimulationCreate, pm: AsyncPersistenceManager = Depends(get_pm)
):
    sim_id = _uuid4()
    item = {
        "id": sim_id,
        "experiment_id": payload.experiment_id,
        "status": "pending",
        "websocket_topic": _topic(sim_id),
        "created_at": _now(),
        "updated_at": _now(),
        "metadata": payload.metadata or {},
    }
    created = await pm.simulations().create(item)
    return Simulation(**created)


@router.post(
    "/{simulation_id}/start",
    response_model=Simulation,
    description="Start a pending simulation",
)
async def start_simulation(
    simulation_id: str, pm: AsyncPersistenceManager = Depends(get_pm)
):
    current = await pm.simulations().get(simulation_id)
    if not current:
        raise SimulationNotFoundError(simulation_id)
    if current["status"] != "pending":
        raise SimulationStateError(
            simulation_id, expected="pending", actual=current.get("status", "unknown")
        )
    updates = {"status": "running", "updated_at": _now()}
    updated = await pm.simulations().update(simulation_id, updates)
    await _publish_status(simulation_id, "running")
    return Simulation(**updated)  # type: ignore[arg-type]


@router.post(
    "/{simulation_id}/stop",
    response_model=Simulation,
    description="Stop a running simulation",
)
async def stop_simulation(
    simulation_id: str, pm: AsyncPersistenceManager = Depends(get_pm)
):
    current = await pm.simulations().get(simulation_id)
    if not current:
        raise SimulationNotFoundError(simulation_id)
    if current["status"] != "running":
        raise SimulationStateError(
            simulation_id, expected="running", actual=current.get("status", "unknown")
        )
    
    # Stop the real simulation runner if it exists
    # (imported after the function definitions below to avoid circular import)
    try:
        from fba_bench_api.core.simulation_runner import get_simulation as get_runner, cleanup_simulation
        runner = get_runner(simulation_id)
        if runner:
            await cleanup_simulation(simulation_id)
            logger.info(f"Stopped real simulation runner for {simulation_id}")
    except ImportError:
        pass  # Runner module not available
    except Exception as e:
        logger.warning(f"Error stopping simulation runner: {e}")
    
    updates = {"status": "stopped", "updated_at": _now()}
    updated = await pm.simulations().update(simulation_id, updates)
    await _publish_status(simulation_id, "stopped")
    return Simulation(**updated)  # type: ignore[arg-type]


import asyncio
from fastapi import BackgroundTasks

# Import the real simulation runner
from fba_bench_api.core.simulation_runner import (
    RealSimulationRunner,
    get_simulation,
    register_simulation,
    unregister_simulation,
    cleanup_simulation,
)

# Store for running background simulation tasks (legacy compatibility)
_running_simulations: dict = {}


async def _run_real_simulation(
    simulation_id: str,
    config: dict,
) -> None:
    """
    Background task that runs a REAL simulation using the production engine.
    
    This uses:
    - SimulationOrchestrator for tick generation
    - WorldStore for canonical state management
    - MarketSimulationService for demand calculation (elasticity + agent-based)
    - EventBus for typed event pub/sub
    
    All results are deterministic when seeded and based on actual economic models.
    """
    runner = None
    try:
        # Get Redis client for publishing updates
        redis = await get_redis()
        
        # Create and register the real simulation runner
        runner = RealSimulationRunner(
            simulation_id=simulation_id,
            config=config,
            redis_client=redis,
        )
        register_simulation(runner)
        _running_simulations[simulation_id] = runner
        
        # Start the simulation (runs until completion or stop)
        await runner.start()
        
        # Wait for completion
        while runner.get_state().status == "running":
            await asyncio.sleep(0.5)
        
        logger.info(
            f"Simulation {simulation_id} completed with status: {runner.get_state().status}"
        )
        
    except Exception as e:
        logger.error(f"Real simulation error for {simulation_id}: {e}", exc_info=True)
        
        # Publish error to Redis
        try:
            redis = await get_redis()
            topic = _topic(simulation_id)
            error_data = {
                "type": "simulation_error",
                "error": str(e),
                "simulation_id": simulation_id,
            }
            await redis.publish(topic, json.dumps(error_data))
        except Exception:
            pass
    finally:
        # Cleanup
        if simulation_id in _running_simulations:
            del _running_simulations[simulation_id]
        if runner:
            unregister_simulation(simulation_id)


@router.post(
    "/{simulation_id}/run",
    response_model=dict,
    description="Run simulation with real business logic",
)
async def run_simulation(
    simulation_id: str,
    background_tasks: BackgroundTasks,
    pm: AsyncPersistenceManager = Depends(get_pm),
):
    """
    Start a simulation run with REAL economic simulation.
    
    This endpoint integrates with the production simulation engine:
    - Uses MarketSimulationService with demand elasticity and customer agent pools
    - WorldStore handles canonical state management and command arbitration
    - SimulationOrchestrator generates deterministic tick events
    
    All results are reproducible when the same seed is used.
    Publishes real-time updates to Redis for GUI consumption.
    """
    current = await pm.simulations().get(simulation_id)
    if not current:
        raise SimulationNotFoundError(simulation_id)
    
    if current["status"] != "running":
        raise SimulationStateError(
            simulation_id, expected="running", actual=current.get("status", "unknown")
        )
    
    if simulation_id in _running_simulations:
        return {"ok": True, "message": "Simulation already running", "simulation_id": simulation_id}
    
    # Build simulation configuration from metadata
    metadata = current.get("metadata", {})
    config = {
        "max_ticks": metadata.get("max_ticks", 100),
        "seed": metadata.get("seed", 42),
        "tick_interval": metadata.get("tick_interval", 0.1),
        "base_demand": metadata.get("base_demand", 100),
        "elasticity": metadata.get("elasticity", 1.5),
        "use_agent_mode": metadata.get("use_agent_mode", True),
        "customers_per_tick": metadata.get("customers_per_tick", 200),
        "asins": metadata.get("asins", ["ASIN001", "ASIN002", "ASIN003"]),
        "initial_products": metadata.get("initial_products", None),
    }
    
    # Start the real simulation in background
    background_tasks.add_task(_run_real_simulation, simulation_id, config)
    
    return {
        "ok": True,
        "message": "Real simulation started",
        "simulation_id": simulation_id,
        "config": {
            "max_ticks": config["max_ticks"],
            "seed": config["seed"],
            "use_agent_mode": config["use_agent_mode"],
            "products": len(config["asins"]),
        },
    }


@router.get(
    "/{simulation_id}", response_model=Simulation, description="Get simulation status"
)
async def get_simulation(
    simulation_id: str, pm: AsyncPersistenceManager = Depends(get_pm)
):
    redis = await get_redis()
    cache_key = f"simulation:{simulation_id}"
    cached = await redis.get(cache_key)
    if cached:
        return Simulation(**json.loads(cached))
    current = await pm.simulations().get(simulation_id)
    if not current:
        raise SimulationNotFoundError(simulation_id)
    await redis.setex(cache_key, 3600, json.dumps(current))
    return Simulation(**current)


# ---------------------------------------------------------------------------
# Back-compat orchestrator controls (DI-backed), used by frontend UI
# These manage the SimulationOrchestrator lifecycle directly and return
# a minimal OK envelope. Database records are managed separately via CRUD.
#
# TEMPORARILY DISABLED: SimulationOrchestrator dependencies not available
# ---------------------------------------------------------------------------


# @router.post("/start", description="Start orchestrator (compat)")
# async def compat_start(
#     bus=Depends(get_event_bus),
#     orch=Depends(get_simulation_orchestrator),
# ):
#     await orch.start(bus)
#     return {"ok": True, "status": "starting"}


# @router.post("/stop", description="Stop orchestrator (compat)")
# async def compat_stop(
#     orch=Depends(get_simulation_orchestrator),
# ):
#     await orch.stop()
#     return {"ok": True, "status": "stopped"}


# @router.post("/pause", description="Pause orchestrator (compat)")
# async def compat_pause(
#     orch=Depends(get_simulation_orchestrator),
# ):
#     await orch.pause()
#     return {"ok": True, "status": "paused"}


# @router.post("/resume", description="Resume orchestrator (compat)")
# async def compat_resume(
#     orch=Depends(get_simulation_orchestrator),
# ):
#     await orch.resume()
#     return {"ok": True, "status": "running"}


# @router.post("/speed", description="Adjust orchestrator time acceleration (compat)")
# async def set_speed(
#     payload: SpeedUpdate,
#     orch=Depends(get_simulation_orchestrator),
# ):
#     """
#     Adjusts the orchestrator's time acceleration factor at runtime.
#     Example: {"speed": 2.0} -> 2x simulated time progression.
#     """
#     try:
#         orch.set_time_acceleration(payload.speed)
#     except ValueError as e:
#         # Field(gt=0) prevents non-positive input, but keep guardrails
#         logger.warning("Rejected speed update: %s", e)
#         return {"ok": False, "error": str(e)}
#     return {"ok": True, "speed": orch.config.time_acceleration}


# @router.post("/emergency-stop", description="Emergency stop orchestrator (compat)")
# async def compat_emergency_stop(
#     orch=Depends(get_simulation_orchestrator),
# ):
#     await orch.stop()
#     return {"ok": True, "status": "stopped"}

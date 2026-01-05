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
    updates = {"status": "stopped", "updated_at": _now()}
    updated = await pm.simulations().update(simulation_id, updates)
    await _publish_status(simulation_id, "stopped")
    return Simulation(**updated)  # type: ignore[arg-type]


import asyncio
from fastapi import BackgroundTasks

# Store for running background simulation tasks
_running_simulations: dict = {}


async def _run_simulation_loop(simulation_id: str, max_ticks: int = 100):
    """Background task that generates mock tick events and publishes to Redis."""
    try:
        redis = await get_redis()
        topic = _topic(simulation_id)
        
        for tick in range(1, max_ticks + 1):
            if simulation_id not in _running_simulations:
                break  # Simulation was stopped
            
            # Generate mock tick data
            import random
            tick_data = {
                "type": "tick",
                "tick": tick,
                "metrics": {
                    "total_revenue": 1000.0 + tick * random.uniform(50, 150),
                    "inventory_count": max(0, 500 - tick * random.randint(1, 5)),
                    "pending_orders": random.randint(0, 20),
                },
                "agents": [
                    {
                        "id": "Agent-GPT4",
                        "role": "Strategic Planner",
                        "x": 200 + tick * 2 + random.uniform(-10, 10),
                        "y": 300 + random.uniform(-20, 20),
                        "state": random.choice(["Active", "Idle", "Buying"]),
                    },
                    {
                        "id": "Agent-Claude",
                        "role": "Analyst",
                        "x": 400 + random.uniform(-30, 30),
                        "y": 250 + tick + random.uniform(-10, 10),
                        "state": random.choice(["Active", "Selling", "Waiting"]),
                    },
                ],
                "heatmap": [],
                "world": {},
            }
            
            await redis.publish(topic, json.dumps(tick_data))
            await asyncio.sleep(0.1)  # 10 ticks/second
        
        # Mark completed
        if simulation_id in _running_simulations:
            del _running_simulations[simulation_id]
            end_data = {"type": "simulation_end", "results": {"overall_score": 75.0}}
            await redis.publish(topic, json.dumps(end_data))
            
    except Exception as e:
        logger.error(f"Simulation loop error for {simulation_id}: {e}")
        if simulation_id in _running_simulations:
            del _running_simulations[simulation_id]


@router.post(
    "/{simulation_id}/run",
    response_model=dict,
    description="Run a simulation (background tick generation for demo)",
)
async def run_simulation(
    simulation_id: str,
    background_tasks: BackgroundTasks,
    pm: AsyncPersistenceManager = Depends(get_pm),
):
    """
    Start a simulation run with mock tick generation.
    This is a demo endpoint that publishes tick events to Redis for the GUI.
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
    
    # Get max_ticks from metadata if available
    metadata = current.get("metadata", {})
    max_ticks = metadata.get("max_ticks", 100)
    
    _running_simulations[simulation_id] = True
    background_tasks.add_task(_run_simulation_loop, simulation_id, max_ticks)
    
    return {"ok": True, "message": "Simulation run started", "simulation_id": simulation_id}


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

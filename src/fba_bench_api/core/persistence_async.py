from __future__ import annotations

"""
Async persistence layer using SQLAlchemy AsyncSession.

Provides:
- AsyncAgentRepository
- AsyncExperimentRepository
- AsyncSimulationRepository
- AsyncPersistenceManager

These mirror the sync repositories in fba_bench_api/core/persistence.py but use
awaitable DB operations for full non-blocking I/O.
"""

from typing import Optional  # noqa: E402

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from fba_bench_api.core.database_async import create_db_tables_async  # noqa: E402
from fba_bench_api.models import (  # noqa: E402
    AgentORM,
    ExperimentORM,
    ExperimentStatusEnum,
    ExperimentRunORM,
    ExperimentParticipantORM,
    SimulationORM,
)
from fba_bench_api.models.base import utcnow  # noqa: E402


class AsyncAgentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self) -> list[dict]:
        result = await self.db.execute(select(AgentORM))
        return [a.to_dict() for a in result.scalars().all()]

    async def create(self, data: dict) -> dict:
        # Ensure schema exists (defensive for tests bypassing lifespan)
        await create_db_tables_async()
        obj = AgentORM(
            id=data["id"],
            name=data["name"],
            framework=data["framework"],
            config=data.get("config") or {},
        )
        self.db.add(obj)
        try:
            await self.db.flush()
        except OperationalError:
            # Defensive: initialize schema and retry once (tests may bypass lifespan)
            await create_db_tables_async()
            await self.db.flush()
        return obj.to_dict()

    async def get(self, agent_id: str) -> Optional[dict]:
        obj = await self.db.get(AgentORM, agent_id)
        return obj.to_dict() if obj else None

    async def update(self, agent_id: str, data: dict) -> Optional[dict]:
        obj = await self.db.get(AgentORM, agent_id)
        if not obj:
            return None
        if "name" in data and data["name"] is not None:
            obj.name = data["name"]
        if "framework" in data and data["framework"] is not None:
            obj.framework = data["framework"]
        if "config" in data and data["config"] is not None:
            obj.config = data["config"]
        obj.updated_at = utcnow()
        await self.db.flush()
        return obj.to_dict()

    async def delete(self, agent_id: str) -> bool:
        obj = await self.db.get(AgentORM, agent_id)
        if not obj:
            return False
        # In AsyncSession, delete is an awaitable operation.
        await self.db.delete(obj)
        await self.db.flush()
        return True


class AsyncExperimentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self) -> list[dict]:
        result = await self.db.execute(select(ExperimentORM))
        return [e.to_dict() for e in result.scalars().all()]

    async def create(self, data: dict) -> dict:
        # Ensure schema exists (defensive for tests bypassing lifespan)
        await create_db_tables_async()
        obj = ExperimentORM(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            agent_id=data["agent_id"],
            scenario_id=data.get("scenario_id"),
            params=data.get("params") or {},
            status=ExperimentStatusEnum.draft,
        )
        self.db.add(obj)
        try:
            await self.db.flush()
        except OperationalError:
            await create_db_tables_async()
            await self.db.flush()
        return obj.to_dict()

    async def get(self, exp_id: str) -> Optional[dict]:
        obj = await self.db.get(ExperimentORM, exp_id)
        return obj.to_dict() if obj else None

    async def update(self, exp_id: str, data: dict) -> Optional[dict]:
        obj = await self.db.get(ExperimentORM, exp_id)
        if not obj:
            return None
        if "name" in data and data["name"] is not None:
            obj.name = data["name"]
        if "description" in data:
            obj.description = data["description"]
        if "params" in data and data["params"] is not None:
            obj.params = data["params"]
        if "status" in data and data["status"] is not None:
            obj.status = ExperimentStatusEnum(data["status"])
        obj.updated_at = utcnow()
        await self.db.flush()
        return obj.to_dict()

    async def delete(self, exp_id: str) -> bool:
        obj = await self.db.get(ExperimentORM, exp_id)
        if not obj:
            return False
        await self.db.delete(obj)
        try:
            await self.db.flush()
        except OperationalError:
            await create_db_tables_async()
            await self.db.flush()
        return True


class AsyncSimulationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> dict:
        # Ensure schema exists (defensive for tests bypassing lifespan)
        await create_db_tables_async()
        obj = SimulationORM(
            id=data["id"],
            experiment_id=data.get("experiment_id"),
            # status defaults to pending
            sim_metadata=data.get("metadata") or {},
        )
        self.db.add(obj)
        try:
            await self.db.flush()
        except OperationalError:
            await create_db_tables_async()
            await self.db.flush()
        return obj.to_dict_with_topic()

    async def get(self, sim_id: str) -> Optional[dict]:
        obj = await self.db.get(SimulationORM, sim_id)
        return obj.to_dict_with_topic() if obj else None

    async def update(self, sim_id: str, data: dict) -> Optional[dict]:
        obj = await self.db.get(SimulationORM, sim_id)
        if not obj:
            return None
        # Only allow status and metadata updates here; routes validate transitions
        if "status" in data and data["status"] is not None:
            obj.status = data["status"]
        if "metadata" in data and data["metadata"] is not None:
            obj.sim_metadata = data["metadata"]
        obj.updated_at = utcnow()
        await self.db.flush()
        return obj.to_dict_with_topic()


class AsyncExperimentRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> dict:
        import json
        await create_db_tables_async()
        obj = ExperimentRunORM(
            id=data["id"],
            experiment_id=data["experiment_id"],
            scenario_id=data["scenario_id"],
            params=json.dumps(data.get("params") or {}),
            status=data.get("status", "pending"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metrics=json.dumps(data.get("metrics") or {}) if data.get("metrics") else None,
            results=json.dumps(data.get("results") or {}) if data.get("results") else None,
        )
        print(f"DEBUG: Creating run {obj.id} in DB.")
        self.db.add(obj)
        
        # Add participants if provided
        participants = data.get("participants", [])
        for p in participants:
            p_obj = ExperimentParticipantORM(
                id=p["id"],
                run_id=obj.id,
                agent_id=p["agent_id"],
                role=p["role"],
                config_override=json.dumps(p.get("config_override") or {}),
            )
            self.db.add(p_obj)
            
        await self.db.flush()
        return obj.to_dict()

    async def get(self, run_id: str) -> Optional[dict]:
        obj = await self.db.get(ExperimentRunORM, run_id)
        if not obj:
            return None
        return obj.to_dict()

    async def update(self, run_id: str, data: dict) -> Optional[dict]:
        import json
        obj = await self.db.get(ExperimentRunORM, run_id)
        if not obj:
            return None
        
        if "status" in data:
            obj.status = data["status"]
        if "current_tick" in data:
            obj.current_tick = data["current_tick"]
        if "total_ticks" in data:
            obj.total_ticks = data["total_ticks"]
        if "progress_percent" in data:
            obj.progress_percent = data["progress_percent"]
        if "completed_at" in data:
            obj.completed_at = data["completed_at"]
        if "metrics" in data:
            obj.metrics = json.dumps(data["metrics"])
        if "results" in data:
            obj.results = json.dumps(data["results"])
        if "error_message" in data:
            obj.error_message = data["error_message"]
            
        obj.updated_at = utcnow()
        await self.db.flush()
        return obj.to_dict()

    async def list_by_experiment(self, experiment_id: str) -> list[dict]:
        from sqlalchemy import select
        stmt = select(ExperimentRunORM).where(ExperimentRunORM.experiment_id == experiment_id)
        result = await self.db.execute(stmt)
        return [r.to_dict() for r in result.scalars().all()]

    async def list_all(self, limit: int = 100) -> list[dict]:
        from sqlalchemy import select
        stmt = select(ExperimentRunORM).order_by(ExperimentRunORM.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return [r.to_dict() for r in result.scalars().all()]


class AsyncPersistenceManager:
    """
    Provides typed async repositories bound to an AsyncSession.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def agents(self) -> AsyncAgentRepository:
        return AsyncAgentRepository(self.db)

    def experiments(self) -> AsyncExperimentRepository:
        return AsyncExperimentRepository(self.db)

    def simulations(self) -> AsyncSimulationRepository:
        return AsyncSimulationRepository(self.db)

    def experiment_runs(self) -> AsyncExperimentRunRepository:
        return AsyncExperimentRunRepository(self.db)

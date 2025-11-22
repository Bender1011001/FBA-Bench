import asyncio
from typing import Dict, Any

# Import from your Core library
# Note: Adjusted imports to match actual core structure
from fba_bench_core.benchmarking.engine.core import Engine as SimulationOrchestrator
from fba_bench_core.benchmarking.engine.models import EngineConfig as SimulationConfig
# from fba_bench_core.events import EventBus as CoreBus # EventBus not found in core yet, commenting out

# Import from Enterprise
from fba_bench_api.core.redis_client import RedisClient
# from fba_bench_api.models.simulation import SimulationORM as SimulationState # SimulationORM not found yet

class EnterpriseSimulationAdapter:
    """
    Bridges the gap between the FBA-Bench-Core engine and the Enterprise API.
    Manages the lifecycle of a simulation run.
    """
    
    def __init__(self, run_id: str, config: Dict[str, Any], redis: RedisClient):
        self.run_id = run_id
        self.redis = redis
        
        # Initialize the Core Engine
        core_config = SimulationConfig(**config)
        self.orchestrator = SimulationOrchestrator(config=core_config)
        
        # Hook into the Core Event Bus to stream updates to Enterprise Redis
        # self.orchestrator.event_bus.subscribe(self._handle_core_event) # EventBus not available on Engine yet

    async def start(self):
        """Starts the simulation loop in a non-blocking background task."""
        print(f"[System] Starting Simulation {self.run_id}")
        asyncio.create_task(self._run_loop())

    async def _run_loop(self):
        """Drives the core simulation tick by tick."""
        # The Engine.run() method runs the entire simulation.
        # We might need to adapt this if we want tick-by-tick control,
        # but for now let's wrap the run() method.
        
        print(f"[System] Running Simulation {self.run_id}")
        report = await self.orchestrator.run()
        
        # Publish final report
        await self.redis.publish(
            channel=f"sim:{self.run_id}:updates",
            message=report.model_dump_json()
        )
        print(f"[System] Simulation {self.run_id} finished")

    async def inject_agent_action(self, agent_id: str, action: str, params: Dict):
        """Allows the API to force an action into the engine."""
        # TODO: Implement command injection for Engine
        pass

    async def _handle_core_event(self, event):
        """Log core events to the Enterprise Audit Trail."""
        await self.redis.lpush(
            f"sim:{self.run_id}:events",
            event.json()
        )
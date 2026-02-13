import asyncio
import json
from typing import Dict, Any

# Import from your Core library
# Note: Adjusted imports to match actual core structure
# Using simulation_orchestrator directly as it seems to be the canonical entry point
from fba_bench_core.simulation_orchestrator import (
    SimulationOrchestrator,
    SimulationConfig,
)

# Try to import EventBus, fallback to Mock if not found in core
try:
    from fba_bench_core.event_bus import EventBus as CoreBus
except ImportError:
    # Mock EventBus if not available in core
    class CoreBus:
        def __init__(self):
            self.subscribers = []

        def subscribe(self, event_type, callback=None):
            # Handle both (event_type, callback) and (callback) signatures for flexibility
            if callback is None:
                callback = event_type
            self.subscribers.append(callback)

        def publish(self, event):
            for sub in self.subscribers:
                try:
                    sub(event)
                except (AttributeError, TypeError, ValueError):
                    pass


# Import from Enterprise
from fba_bench_api.core.redis_client import RedisClient

# Try to import SimulationORM, fallback to Mock if fails (e.g. due to sqlalchemy version)
try:
    from fba_bench_api.models.simulation import SimulationORM as SimulationState
except ImportError:

    class SimulationState:
        pass


class EnterpriseSimulationAdapter:
    """
    Bridges the gap between the FBA-Bench-Core engine and the Enterprise API.
    Manages the lifecycle of a simulation run.
    """

    def __init__(self, run_id: str, config: Dict[str, Any], redis: RedisClient):
        self.run_id = run_id
        self.redis = redis

        # Initialize the Core Engine
        # Filter config to only include keys supported by SimulationConfig
        valid_keys = SimulationConfig.__annotations__.keys()
        filtered_config = {k: v for k, v in config.items() if k in valid_keys}
        core_config = SimulationConfig(**filtered_config)
        self.orchestrator = SimulationOrchestrator(config=core_config)

        # Ensure orchestrator has event_bus (inject if missing from core Engine)
        if not hasattr(self.orchestrator, "event_bus"):
            self.orchestrator.event_bus = CoreBus()

        # Hook into the Core Event Bus to stream updates to Enterprise Redis
        # Subscription is handled in start() to support async event buses

    async def start(self):
        # Subscribe to event bus if not already done (moved from __init__ due to async nature of real EventBus)
        if hasattr(self.orchestrator, "event_bus"):
            if asyncio.iscoroutinefunction(self.orchestrator.event_bus.subscribe):
                await self.orchestrator.event_bus.subscribe(
                    "*", self._handle_core_event
                )
            else:
                # Fallback for sync mock or sync implementation
                try:
                    self.orchestrator.event_bus.subscribe("*", self._handle_core_event)
                except TypeError:
                    # Handle mock signature mismatch if any
                    self.orchestrator.event_bus.subscribe(self._handle_core_event)

        """Starts the simulation loop in a non-blocking background task."""
        print(f"[System] Starting Simulation {self.run_id}")
        asyncio.create_task(self._run_loop())

    async def _run_loop(self):
        """Drives the core simulation tick by tick."""
        print(f"[System] Running Simulation {self.run_id}")

        # Start the engine in a background task so we can poll it
        # This allows us to stream updates even if the engine runs in a blocking manner
        engine_task = asyncio.create_task(self.orchestrator.run())

        try:
            while not engine_task.done():
                # Extract state
                tick = getattr(self.orchestrator, "current_tick", 0)

                # Try to get KPIs
                kpis = {}
                # Check for get_kpis or get_state or internal calculation methods
                if hasattr(self.orchestrator, "get_kpis"):
                    try:
                        kpis = self.orchestrator.get_kpis()
                    except (AttributeError, TypeError, ValueError):
                        pass
                elif hasattr(self.orchestrator, "get_state"):
                    try:
                        state = self.orchestrator.get_state()
                        # Extract KPIs from state if possible
                        kpis = state.get("kpis", {}) if isinstance(state, dict) else {}
                    except (AttributeError, TypeError, ValueError):
                        pass
                elif hasattr(self.orchestrator, "_calculate_scenario_kpis"):
                    try:
                        kpis = self.orchestrator._calculate_scenario_kpis()
                    except (AttributeError, TypeError, ValueError):
                        pass

                # Construct report
                report = {
                    "tick": tick,
                    "kpis": kpis,
                    "status": "running",
                    "run_id": self.run_id,
                }

                # Publish update
                await self.redis.publish(
                    channel=f"sim:{self.run_id}:updates",
                    message=json.dumps(report, default=str),
                )

                # Poll interval
                await asyncio.sleep(1)

            # Final report
            final_report = await engine_task

            # Publish final
            msg = (
                final_report.model_dump_json()
                if hasattr(final_report, "model_dump_json")
                else json.dumps(final_report, default=str)
            )
            await self.redis.publish(channel=f"sim:{self.run_id}:updates", message=msg)
            print(f"[System] Simulation {self.run_id} finished")

        except (asyncio.CancelledError, SystemExit):
            raise
        except (subprocess.SubprocessError, OSError, RuntimeError, ValueError) as e:
            print(f"[System] Simulation {self.run_id} failed: {e}")
            # Publish error
            await self.redis.publish(
                channel=f"sim:{self.run_id}:updates",
                message=json.dumps({"status": "failed", "error": str(e)}),
            )

    async def inject_agent_action(self, agent_id: str, action: str, params: Dict):
        """Allows the API to force an action into the engine."""
        if (
            not hasattr(self.orchestrator, "event_bus")
            or not self.orchestrator.event_bus
        ):
            return

        try:
            if action in ("set_price", "SetPriceCommand"):
                from fba_events.pricing import SetPriceCommand
                import uuid
                from datetime import datetime

                # Dynamic import of Money to avoid early circular dependencies or missing core
                try:
                    from fba_bench_core.money import Money
                except ImportError:
                    # Fallback for minimal environments
                    from fba_bench.money import Money  # type: ignore

                asin = params.get("asin") or params.get("product_id")
                price_val = params.get("new_price") or params.get("price")

                if price_val is not None:
                    if isinstance(price_val, (int, float, str)):
                        money_price = Money.from_dollars(price_val)
                    else:
                        money_price = (
                            price_val  # Assume already a Money-compatible object
                        )
                else:
                    money_price = Money(0)

                command = SetPriceCommand(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    agent_id=agent_id,
                    asin=str(asin) if asin else "",
                    new_price=money_price,
                )
                await self.orchestrator.event_bus.publish(command)
        except (ImportError, AttributeError, TypeError, ValueError) as e:
            # Log but don't crash the adapter
            print(f"[Error] Failed to inject agent action {action}: {e}")

    async def _handle_core_event(self, event):
        """Log core events to the Enterprise Audit Trail."""
        await self.redis.lpush(f"sim:{self.run_id}:events", event.json())

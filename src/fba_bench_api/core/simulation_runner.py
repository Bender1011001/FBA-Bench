"""
Real Simulation Runner for FBA-Bench Enterprise API.

This module provides the production simulation runner that integrates:
- SimulationOrchestrator for tick generation
- WorldStore for canonical state management
- MarketSimulationService for demand calculation and sales processing
- EventBus for typed event pub/sub

REPLACES: The mock tick generation in routes/simulation.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fba_bench_core.simulation_orchestrator import (
    SimulationConfig,
    SimulationOrchestrator,
)
from fba_bench_core.event_bus import EventBus
from fba_events.time_events import TickEvent
from fba_events.inventory import InventoryUpdate

from services.world_store import WorldStore, ProductState
from services.market_simulator import MarketSimulationService
from money import Money

logger = logging.getLogger(__name__)


@dataclass
class SimulationState:
    """Current state of a running simulation."""

    simulation_id: str
    status: str  # "pending", "running", "completed", "failed", "stopped"
    current_tick: int = 0
    total_ticks: int = 100
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # KPI aggregates
    total_revenue_cents: int = 0
    total_units_sold: int = 0
    total_profit_cents: int = 0
    inventory_value_cents: int = 0
    inventory_units: int = 0
    pending_orders: int = 0

    # Agent tracking
    agents: List[Dict[str, Any]] = field(default_factory=list)

    def to_tick_data(self) -> Dict[str, Any]:
        """Convert to Redis-publishable tick data format."""
        return {
            "type": "tick",
            "tick": self.current_tick,
            "metrics": {
                "total_revenue": self.total_revenue_cents / 100.0,
                "total_profit": self.total_profit_cents / 100.0,
                "units_sold": self.total_units_sold,
                "inventory_value": self.inventory_value_cents / 100.0,
                # Back-compat for existing UI fields in godot_gui/
                "inventory_count": self.inventory_units,
                "pending_orders": int(self.pending_orders),
            },
            "agents": self.agents,
            "status": self.status,
        }


class RealSimulationRunner:
    """
    Production simulation runner that executes actual business simulation logic.

    This integrates:
    - SimulationOrchestrator for tick generation
    - WorldStore for canonical state management
    - MarketSimulationService for demand/sales calculation
    - EventBus for event-driven architecture

    Unlike the mock runner, this produces deterministic, realistic results based
    on actual economic models and agent decisions.
    """

    def __init__(
        self,
        simulation_id: str,
        config: Optional[Dict[str, Any]] = None,
        redis_client: Optional[Any] = None,
    ):
        self.simulation_id = simulation_id
        self.config = config or {}
        self.redis_client = redis_client

        # Core components
        self._event_bus: Optional[EventBus] = None
        self._orchestrator: Optional[SimulationOrchestrator] = None
        self._world_store: Optional[WorldStore] = None
        self._market_service: Optional[MarketSimulationService] = None

        # State tracking
        self._state = SimulationState(
            simulation_id=simulation_id,
            status="pending",
            total_ticks=self.config.get("max_ticks", 100),
        )

        # Product ASINs to process each tick
        self._asins: List[str] = self.config.get(
            "asins", ["ASIN001", "ASIN002", "ASIN003"]
        )

        # Seeding for reproducibility
        self._seed = self.config.get("seed", 42)

        # Control
        self._running = False
        self._runner_task: Optional[asyncio.Task] = None

        # Per-tick stats (for UI)
        self._tick_units_sold: int = 0
        self._tick_units_demanded: int = 0

        # Auto-restock (demo-friendly). This keeps long runs visually interesting.
        # It is intentionally simple: schedule inbound replenishment when inventory is low.
        self._restock_enabled: bool = bool(self.config.get("restock_enabled", True))
        self._restock_reorder_ratio: float = float(
            self.config.get("restock_reorder_ratio", 0.06)
        )
        self._restock_target_ratio: float = float(
            self.config.get("restock_target_ratio", 1.0)
        )
        self._restock_lead_time_min: int = int(
            self.config.get("restock_lead_time_min_ticks", 3)
        )
        self._restock_lead_time_max: int = int(
            self.config.get("restock_lead_time_max_ticks", 7)
        )
        self._inventory_baseline: Dict[str, int] = {}
        # asin -> {"arrival_tick": int}
        self._pending_restocks: Dict[str, Dict[str, int]] = {}
        import random as _random

        self._restock_rng = _random.Random(int(self._seed) + 1337)

        logger.info(f"RealSimulationRunner initialized for simulation {simulation_id}")

    async def initialize(self) -> None:
        """Initialize all simulation components."""
        # Create event bus
        self._event_bus = EventBus()

        # Create world store
        self._world_store = WorldStore(event_bus=self._event_bus)
        await self._world_store.start()

        # Initialize products in world store
        await self._initialize_products()

        # Create market simulation service with seeded random
        self._market_service = MarketSimulationService(
            world_store=self._world_store,
            event_bus=self._event_bus,
            base_demand=self.config.get("base_demand", 100),
            demand_elasticity=self.config.get("elasticity", 1.5),
            use_agent_mode=self.config.get("use_agent_mode", True),
            customers_per_tick=self.config.get("customers_per_tick", 200),
            customer_seed=self._seed,
        )
        await self._market_service.start()

        # Create orchestrator
        orchestrator_config = SimulationConfig(
            tick_interval_seconds=self.config.get("tick_interval", 0.1),
            max_ticks=self._state.total_ticks,
            time_acceleration=self.config.get("time_acceleration", 1.0),
            seed=self._seed,
        )
        self._orchestrator = SimulationOrchestrator(orchestrator_config)

        # Subscribe to events for aggregation
        await self._event_bus.subscribe(TickEvent, self._on_tick_event)

        logger.info(
            f"Simulation {self.simulation_id} initialized with {len(self._asins)} products"
        )

    async def _initialize_products(self) -> None:
        """Set up initial product states in WorldStore."""
        import random

        rng = random.Random(self._seed)

        initial_configs = self.config.get("initial_products", None)

        if initial_configs:
            # Use provided product configurations
            for product_cfg in initial_configs:
                asin = product_cfg["asin"]
                ps = ProductState(
                    asin=asin,
                    price=Money.from_dollars(product_cfg.get("price", 29.99)),
                    inventory_quantity=product_cfg.get("inventory", 500),
                    cost_basis=Money.from_dollars(product_cfg.get("cost", 15.00)),
                    last_updated=datetime.now(timezone.utc),
                    metadata=product_cfg.get("metadata", {}),
                )
                self._world_store.set_product_state(asin, ps)
                self._inventory_baseline[asin] = int(ps.inventory_quantity)
        else:
            # Generate default products with seeded randomness
            for i, asin in enumerate(self._asins):
                # Deterministic variation based on ASIN index and seed
                base_price = 19.99 + (i * 10) + (rng.random() * 20)
                base_inventory = 300 + (i * 100) + rng.randint(0, 200)
                cost_ratio = 0.4 + (rng.random() * 0.2)  # 40-60% of price

                ps = ProductState(
                    asin=asin,
                    price=Money.from_dollars(base_price),
                    inventory_quantity=base_inventory,
                    cost_basis=Money.from_dollars(base_price * cost_ratio),
                    last_updated=datetime.now(timezone.utc),
                    metadata={
                        "review_rating": 3.5 + rng.random() * 1.5,  # 3.5-5.0
                        "review_count": 50 + rng.randint(0, 500),
                        "category": f"Category-{i % 5}",
                    },
                )
                self._world_store.set_product_state(asin, ps)
                self._inventory_baseline[asin] = int(ps.inventory_quantity)

        logger.info(f"Initialized {len(self._asins)} products in WorldStore")

    async def _on_tick_event(self, event: TickEvent) -> None:
        """Process each tick: run market simulation and publish state."""
        self._state.current_tick = event.tick_number

        # Apply inbound restocks first (arrivals happen at the start of a tick).
        if self._restock_enabled:
            await self._apply_due_restocks(event.tick_number)

        # Clear per-tick counters
        self._tick_units_sold = 0
        self._tick_units_demanded = 0

        # Process market simulation for each ASIN and update state synchronously.
        tick_rev_cents = 0
        tick_profit_cents = 0
        for asin in self._asins:
            summary = await self._market_service.process_for_asin(asin)
            if not isinstance(summary, dict) or summary.get("skipped", False):
                continue

            units_demanded = int(summary.get("units_demanded", 0))
            units_sold = int(summary.get("units_sold", 0))
            inv_after = int(summary.get("inventory_after", 0))

            self._tick_units_demanded += max(0, units_demanded)
            self._tick_units_sold += max(0, units_sold)

            tick_rev_cents += int(summary.get("revenue_cents", 0))
            tick_profit_cents += int(summary.get("profit_cents", 0))

            # Ensure WorldStore state is updated before we publish the tick payload.
            product = self._world_store.get_product_state(asin) if self._world_store else None
            if product:
                product.inventory_quantity = max(0, inv_after)
                product.last_updated = datetime.now(timezone.utc)

        # Aggregate totals (cumulative)
        self._state.total_revenue_cents += tick_rev_cents
        self._state.total_profit_cents += tick_profit_cents
        self._state.total_units_sold += self._tick_units_sold

        # Schedule new restocks after sales
        if self._restock_enabled:
            self._schedule_restocks(event.tick_number)
        self._state.pending_orders = len(self._pending_restocks)

        # Calculate current inventory value
        total_inv_value = 0
        total_inv_units = 0
        for asin in self._asins:
            product = self._world_store.get_product_state(asin)
            if product:
                total_inv_units += int(product.inventory_quantity)
                total_inv_value += product.inventory_quantity * product.cost_basis.cents
        self._state.inventory_value_cents = total_inv_value
        self._state.inventory_units = total_inv_units

        # Build agent state from sales data
        self._state.agents = await self._build_agent_state()

        # Publish to Redis if available
        await self._publish_tick_update()

    async def _apply_due_restocks(self, tick_number: int) -> None:
        """Apply any inbound shipments scheduled for this tick."""
        if not self._world_store or not self._event_bus:
            return

        due: List[str] = []
        for asin, payload in list(self._pending_restocks.items()):
            arrival = int(payload.get("arrival_tick", 0))
            if tick_number >= arrival:
                due.append(asin)

        if not due:
            return

        for asin in due:
            product = self._world_store.get_product_state(asin)
            if not product:
                self._pending_restocks.pop(asin, None)
                continue

            prev_qty = int(product.inventory_quantity)
            baseline = int(self._inventory_baseline.get(asin, prev_qty))
            target = int(max(prev_qty, round(baseline * self._restock_target_ratio)))
            if target <= prev_qty:
                self._pending_restocks.pop(asin, None)
                continue

            product.inventory_quantity = target
            product.last_updated = datetime.now(timezone.utc)

            try:
                await self._event_bus.publish(
                    InventoryUpdate(
                        event_id=f"restock_{asin}_{tick_number}",
                        timestamp=datetime.now(timezone.utc),
                        asin=asin,
                        new_quantity=target,
                        previous_quantity=prev_qty,
                        change_reason="inbound_shipment",
                        agent_id="auto_restock",
                        cost_basis=product.cost_basis,
                    )
                )
            except Exception:
                # Restock is best-effort for demo stability.
                pass

            self._pending_restocks.pop(asin, None)

    def _schedule_restocks(self, tick_number: int) -> None:
        """Schedule inbound shipments for low-inventory products."""
        if not self._world_store:
            return

        # Clamp lead time range to avoid invalid randint bounds
        lead_min = max(1, int(self._restock_lead_time_min))
        lead_max = max(lead_min, int(self._restock_lead_time_max))

        for asin in self._asins:
            if asin in self._pending_restocks:
                continue
            baseline = int(self._inventory_baseline.get(asin, 0))
            if baseline <= 0:
                continue
            reorder_point = max(0, int(round(baseline * float(self._restock_reorder_ratio))))
            current_qty = int(self._world_store.get_product_inventory_quantity(asin))
            if current_qty <= reorder_point:
                lead = int(self._restock_rng.randint(lead_min, lead_max))
                self._pending_restocks[asin] = {"arrival_tick": int(tick_number + lead)}

    async def _build_agent_state(self) -> List[Dict[str, Any]]:
        """Build agent visualization state from current simulation state."""
        agents = []

        # Get agent stats from market service
        if self._market_service and self._market_service._use_agent_mode:
            stats = self._market_service.get_agent_stats()

            # Create visualization data based on real customer pool activity
            agents.append(
                {
                    "id": "CustomerPool",
                    "role": "Demand Engine",
                    "x": 300,
                    "y": 200,
                    "state": (
                        "Active" if stats.get("purchase_rate", 0) > 0.1 else "Idle"
                    ),
                    "metrics": {
                        "customers_served": stats.get("total_customers_served", 0),
                        "purchases": stats.get("total_purchases", 0),
                        "purchase_rate": round(stats.get("purchase_rate", 0), 3),
                    },
                }
            )

        # Add market state agent
        agents.append(
            {
                "id": "MarketSimulator",
                "role": "Price/Demand Engine",
                "x": 500,
                "y": 300,
                "state": "Processing",
                "metrics": {
                    "tick_sales": int(self._tick_units_sold),
                    "total_revenue": self._state.total_revenue_cents / 100.0,
                },
            }
        )

        # Add world store state
        agents.append(
            {
                "id": "WorldStore",
                "role": "State Arbiter",
                "x": 400,
                "y": 400,
                "state": "Healthy",
                "metrics": {
                    "products_tracked": len(self._asins),
                    "commands_processed": (
                        self._world_store.commands_processed if self._world_store else 0
                    ),
                },
            }
        )

        return agents

    async def _publish_tick_update(self) -> None:
        """Publish current tick state to Redis for real-time updates."""
        if not self.redis_client:
            return

        try:
            topic = f"simulation-progress:{self.simulation_id}"
            tick_data = self._state.to_tick_data()

            # Add product states for detailed view
            product_states = []
            for asin in self._asins:
                product = (
                    self._world_store.get_product_state(asin)
                    if self._world_store
                    else None
                )
                if product:
                    product_states.append(
                        {
                            "asin": asin,
                            "price": product.price.cents / 100.0,
                            "inventory": product.inventory_quantity,
                            "cost_basis": product.cost_basis.cents / 100.0,
                        }
                    )
            tick_data["products"] = product_states

            await self.redis_client.publish(topic, json.dumps(tick_data))

        except Exception as e:
            logger.warning(f"Failed to publish tick update: {e}")

    async def start(self) -> None:
        """Start the simulation."""
        if self._running:
            logger.warning(f"Simulation {self.simulation_id} already running")
            return

        await self.initialize()

        self._running = True
        self._state.status = "running"
        self._state.started_at = datetime.now(timezone.utc)

        # Start orchestrator (runs in background)
        await self._orchestrator.start(self._event_bus)

        # Monitor completion
        self._runner_task = asyncio.create_task(self._monitor_completion())

        logger.info(f"Simulation {self.simulation_id} started")

    async def _monitor_completion(self) -> None:
        """Monitor orchestrator for completion and publish final results."""
        try:
            while self._running:
                status = self._orchestrator.get_status()

                if not status["is_running"]:
                    # Simulation completed naturally
                    break

                await asyncio.sleep(0.5)

            # Mark as completed
            self._state.status = "completed"
            self._state.stopped_at = datetime.now(timezone.utc)

            # Publish final results
            await self._publish_final_results()

        except asyncio.CancelledError:
            self._state.status = "stopped"
            self._state.stopped_at = datetime.now(timezone.utc)
        except Exception as e:
            self._state.status = "failed"
            self._state.error_message = str(e)
            self._state.stopped_at = datetime.now(timezone.utc)
            logger.error(f"Simulation {self.simulation_id} failed: {e}")

    async def _publish_final_results(self) -> None:
        """Publish final simulation results."""
        if not self.redis_client:
            return

        try:
            topic = f"simulation-progress:{self.simulation_id}"

            # Calculate final metrics
            final_data = {
                "type": "simulation_end",
                "status": self._state.status,
                "results": {
                    "total_ticks": self._state.current_tick,
                    "total_revenue": self._state.total_revenue_cents / 100.0,
                    "total_profit": self._state.total_profit_cents / 100.0,
                    "total_units_sold": self._state.total_units_sold,
                    "final_inventory_value": self._state.inventory_value_cents / 100.0,
                    "profit_margin": (
                        (
                            self._state.total_profit_cents
                            / self._state.total_revenue_cents
                        )
                        * 100
                        if self._state.total_revenue_cents > 0
                        else 0
                    ),
                    "agent_stats": (
                        self._market_service.get_agent_stats()
                        if self._market_service
                        else {}
                    ),
                },
                "timing": {
                    "started_at": (
                        self._state.started_at.isoformat()
                        if self._state.started_at
                        else None
                    ),
                    "stopped_at": (
                        self._state.stopped_at.isoformat()
                        if self._state.stopped_at
                        else None
                    ),
                },
            }

            await self.redis_client.publish(topic, json.dumps(final_data))
            logger.info(f"Published final results for simulation {self.simulation_id}")

        except Exception as e:
            logger.warning(f"Failed to publish final results: {e}")

    async def stop(self) -> None:
        """Stop the simulation gracefully."""
        if not self._running:
            return

        self._running = False

        # Stop orchestrator
        if self._orchestrator:
            await self._orchestrator.stop()

        # Cancel monitor task
        if self._runner_task:
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass

        # Cleanup services
        if self._world_store:
            await self._world_store.stop()

        self._state.status = "stopped"
        self._state.stopped_at = datetime.now(timezone.utc)

        logger.info(f"Simulation {self.simulation_id} stopped")

    def get_state(self) -> SimulationState:
        """Get current simulation state."""
        return self._state

    def get_tick_data(self) -> Dict[str, Any]:
        """Get current tick data for API responses."""
        return self._state.to_tick_data()


# Registry of running simulations
_running_simulations: Dict[str, RealSimulationRunner] = {}


def get_simulation(simulation_id: str) -> Optional[RealSimulationRunner]:
    """Get a running simulation by ID."""
    return _running_simulations.get(simulation_id)


def register_simulation(runner: RealSimulationRunner) -> None:
    """Register a simulation runner."""
    _running_simulations[runner.simulation_id] = runner


def unregister_simulation(simulation_id: str) -> None:
    """Unregister a simulation runner."""
    _running_simulations.pop(simulation_id, None)


async def cleanup_simulation(simulation_id: str) -> None:
    """Stop and cleanup a simulation."""
    runner = _running_simulations.get(simulation_id)
    if runner:
        await runner.stop()
        unregister_simulation(simulation_id)

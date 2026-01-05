"""
Supply Chain Disruption Scenario for FBA-Bench.

This scenario tests an agent's ability to respond to and mitigate the impact of
supply chain disruptions, such as unexpected delays or reduced availability.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from money import Money
from pydantic import Field, PositiveInt, confloat

from benchmarking.agents.base import BaseAgent
from benchmarking.core.results import AgentRunResult
from benchmarking.scenarios.base import BaseScenario, ScenarioConfig
from services.market_simulator import MarketSimulationService
from services.supply_chain_service import SupplyChainService
from services.world_store import WorldStore
from fba_events.supplier import PlaceOrderCommand

logger = logging.getLogger(__name__)


class SupplyChainDisruptionConfig(ScenarioConfig):
    """Configuration for the Supply Chain Disruption Scenario."""

    product_asin: str = Field(
        "B0CSUPPLYCHAIN",
        description="ASIN of the product affected by supply chain disruption.",
    )
    initial_inventory: PositiveInt = Field(
        1000, description="Initial inventory level for the product."
    )
    disruption_magnitude: confloat(ge=0.0, le=1.0) = Field(
        0.5,
        description="Magnitude of the disruption (0.0 to 1.0, e.g., 0.5 means 50% supply reduction).",
    )
    disruption_duration_ticks: PositiveInt = Field(
        3, description="Duration of the disruption in ticks."
    )
    disruption_start_tick: PositiveInt = Field(
        2, description="Tick at which the supply chain disruption begins."
    )
    demand_per_tick: PositiveInt = Field(
        100, description="Simulated base demand for the product per tick."
    )


class SupplyChainDisruptionScenario(BaseScenario):
    """
    Simulates a supply chain disruption and evaluates an agent's response.
    """

    def __init__(self, config: ScenarioConfig):
        super().__init__(config)
        self.scenario_config: SupplyChainDisruptionConfig = SupplyChainDisruptionConfig(
            **config.model_dump()
        )

        self.product_asin: str = self.scenario_config.product_asin
        self.initial_inventory: int = self.scenario_config.initial_inventory
        self.disruption_magnitude: float = self.scenario_config.disruption_magnitude
        self.disruption_duration_ticks: int = (
            self.scenario_config.disruption_duration_ticks
        )
        self.disruption_start_tick: int = self.scenario_config.disruption_start_tick
        self.demand_per_tick: int = self.scenario_config.demand_per_tick

        self.current_tick: int = 0
        self.current_inventory: int = self.initial_inventory
        self.total_revenue_lost: float = 0.0
        self.original_supply_per_tick: int = (
            self.demand_per_tick * 1.2
        )  # Assume some buffer in normal supply
        self.current_supply_per_tick: int = self.original_supply_per_tick

    async def setup(self, *args, **kwargs) -> None:
        """
        Set up the supply chain disruption scenario.
        Initialize inventory and supply levels, and ensure WorldStore has the product.
        """
        logger.info(f"Setting up Supply Chain Disruption Scenario: {self.scenario_id}")
        self.current_tick = 0
        self.current_inventory = self.initial_inventory
        self.total_revenue_lost = 0.0
        self.current_supply_per_tick = self.original_supply_per_tick

        world_store: Optional[WorldStore] = kwargs.get("world_store")
        if world_store:
            # Initialize product in canonical state with a reasonable default price
            try:
                world_store.initialize_product(
                    self.product_asin,
                    Money.from_dollars("25.00"),
                    initial_inventory=self.initial_inventory,
                )
                logger.info(
                    f"Product {self.product_asin} initialized in WorldStore with initial inventory {self.initial_inventory}."
                )
            except Exception:
                # If initialize_product already done, ensure inventory aligns
                pass

        logger.info(
            f"Initial inventory for {self.product_asin}: {self.initial_inventory}"
        )

    async def run(
        self, agent: BaseAgent, run_number: int, *args, **kwargs
    ) -> AgentRunResult:
        """
        Execute a single tick of the supply chain disruption scenario.
        Apply disruption, simulate demand, and measure agent's mitigation.
        """
        start_time = datetime.now()
        logger.info(
            f"Running Supply Chain Disruption for agent {agent.agent_id}, run {run_number}, tick {self.current_tick}"
        )

        # Apply disruption if within the disruption window
        if (
            self.disruption_start_tick
            <= self.current_tick
            < self.disruption_start_tick + self.disruption_duration_ticks
        ):
            reduced_supply = int(
                self.original_supply_per_tick * (1 - self.disruption_magnitude)
            )
            self.current_supply_per_tick = max(
                0, reduced_supply
            )  # Ensure supply doesn't go negative
            logger.warning(
                f"Supply chain disruption active! Supply reduced to {self.current_supply_per_tick} units/tick."
            )
        else:
            self.current_supply_per_tick = self.original_supply_per_tick

        # Simulate demand placeholder (for metrics); MarketSimulationService computes realized sales
        actual_demand = self.demand_per_tick

        # Agent decides on actions (e.g., place replenishment orders)
        agent_decision_output: Dict[str, Any] = {}
        success = True
        errors: List[str] = []

        try:
            agent_input = {
                "product_asin": self.product_asin,
                "current_inventory": self.current_inventory,
                "current_supply_rate": self.current_supply_per_tick,
                "estimated_demand": actual_demand,
                "tick": self.current_tick,
                "disruption_active": (
                    self.disruption_start_tick
                    <= self.current_tick
                    < self.disruption_start_tick + self.disruption_duration_ticks
                ),
            }
            agent_decision_output = await agent.decide(agent_input)

            # Publish PlaceOrderCommand if agent proposed one
            event_bus = kwargs.get("event_bus")
            world_store: Optional[WorldStore] = kwargs.get("world_store")
            supply_chain: Optional[SupplyChainService] = kwargs.get(
                "supply_chain_service"
            )
            market_simulator: Optional[MarketSimulationService] = kwargs.get(
                "market_simulator"
            )

            prev_inventory = (
                world_store.get_product_inventory_quantity(self.product_asin)
                if world_store
                else self.current_inventory
            )

            if event_bus and world_store:
                order_qty = int(agent_decision_output.get("order_quantity", 0) or 0)
                if order_qty > 0:
                    supplier_id = str(
                        agent_decision_output.get("supplier_id", "default_supplier")
                    )
                    max_unit_price = float(
                        agent_decision_output.get("max_unit_price", 100.0)
                    )
                    cmd = PlaceOrderCommand(
                        event_id=f"order_{agent.agent_id}_{self.current_tick}",
                        timestamp=datetime.now(),
                        agent_id=agent.agent_id,
                        supplier_id=supplier_id,
                        asin=self.product_asin,
                        quantity=order_qty,
                        max_price=Money.from_dollars(f"{max_unit_price:.2f}"),
                        reason="SupplyChainDisruptionScenario",
                    )
                    await event_bus.publish(cmd)
                    logger.info(
                        f"Published PlaceOrderCommand for {self.product_asin} qty={order_qty} supplier={supplier_id}"
                    )

            # Apply disruption to supply chain parameters this tick
            if kwargs.get("supply_chain_service"):
                disruption_active = (
                    self.disruption_start_tick
                    <= self.current_tick
                    < self.disruption_start_tick + self.disruption_duration_ticks
                )
                # Increase lead time by 1x magnitude in disruption window and reduce fulfillment rate
                kwargs["supply_chain_service"].set_disruption(
                    active=disruption_active,
                    lead_time_increase=max(
                        0, int(round(self.disruption_magnitude * 2))
                    ),
                    fulfillment_rate=max(0.0, 1.0 - self.disruption_magnitude),
                )
                # Process arrivals for this tick
                await kwargs["supply_chain_service"].process_tick()

            # Run market processing for this ASIN for the tick
            if market_simulator and hasattr(market_simulator, "process_for_asin"):
                await market_simulator.process_for_asin(self.product_asin)

            # Read updated inventory and infer units sold
            latest_inventory = (
                world_store.get_product_inventory_quantity(self.product_asin)
                if world_store
                else prev_inventory
            )
            units_sold = max(0, prev_inventory - latest_inventory)
            unmet_demand = max(0, actual_demand - units_sold)

            if unmet_demand > 0:
                # Estimate lost revenue using current canonical price (fallback $100 if unavailable)
                price_money = (
                    world_store.get_product_state(self.product_asin).price
                    if world_store
                    else Money(10000)
                )
                unit_price = float(price_money.cents) / 100.0
                lost_revenue_this_tick = unmet_demand * unit_price
                self.total_revenue_lost += lost_revenue_this_tick
                logger.warning(
                    f"Unmet demand: {unmet_demand}. Lost revenue this tick: ${lost_revenue_this_tick:.2f}"
                )

        except Exception as e:
            logger.error(
                f"Error in Supply Chain Disruption scenario run for agent {agent.agent_id}: {e}"
            )
            success = False
            errors.append(str(e))
            units_sold = 0
            unmet_demand = actual_demand

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        metrics = {
            "current_inventory": (
                world_store.get_product_inventory_quantity(self.product_asin)
                if world_store
                else self.current_inventory
            ),
            "units_sold_this_tick": units_sold,
            "unmet_demand_this_tick": unmet_demand,
            "total_revenue_lost_so_far": self.total_revenue_lost,
            "supply_rate_this_tick": self.current_supply_per_tick,
            "is_disruption_active": (
                self.disruption_start_tick
                <= self.current_tick
                < self.disruption_start_tick + self.disruption_duration_ticks
            ),
            "stockout": (
                (world_store.get_product_inventory_quantity(self.product_asin) == 0)
                if world_store
                else False
            ),
        }

        self.current_tick += 1

        return AgentRunResult(
            agent_id=agent.agent_id,
            scenario_name=self.config.name,
            run_number=run_number,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            success=success,
            errors=errors,
            metrics=metrics,
        )

    async def teardown(self, *args, **kwargs) -> None:
        """
        Clean up resources after the supply chain disruption scenario.
        """
        logger.info(
            f"Tearing down Supply Chain Disruption Scenario: {self.scenario_id}"
        )
        self.current_tick = 0
        self.current_inventory = self.initial_inventory
        self.total_revenue_lost = 0.0
        logger.info("Supply Chain Disruption Scenario resources cleaned up.")

    async def get_progress(self) -> Dict[str, Any]:
        """
        Provides current progress of the scenario.
        """
        return {
            "current_tick": self.current_tick,
            "current_inventory": self.current_inventory,
            "total_revenue_lost": self.total_revenue_lost,
            "disruption_active": (
                self.disruption_start_tick
                <= self.current_tick
                < self.disruption_start_tick + self.disruption_duration_ticks
            ),
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Returns the configuration schema for the Supply Chain Disruption Scenario.
        """
        return SupplyChainDisruptionConfig.model_json_schema()

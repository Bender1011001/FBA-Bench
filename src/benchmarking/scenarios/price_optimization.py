"""
Price Optimization Scenario for FBA-Bench.

This scenario challenges an agent to optimize product pricing
to maximize revenue or profit over a simulated period.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Union

from money import Money  # Assuming Money class is available

from benchmarking.agents.base import BaseAgent
from benchmarking.core.results import AgentRunResult
from benchmarking.scenarios.base import BaseScenario, ScenarioConfig

logger = logging.getLogger(__name__)


class PriceOptimizationScenario(BaseScenario):
    """
    Simulates a price optimization challenge for an agent.
    """

    def __init__(self, config: Union[ScenarioConfig, Dict[str, Any]]):
        if isinstance(config, dict):
            # Wrap dict in object-like structure or ScenarioConfig if possible, 
            # but simpler to just use SimpleNamespace for compatibility logic below
            from types import SimpleNamespace
            # Ensure parameters exists
            if "parameters" not in config:
                config["parameters"] = {}
            # If we can't fully emulate ScenarioConfig, we might fail validation later, 
            # but here we just need .parameters access.
            # Best is to convert to ScenarioConfig if not already. 
            try:
                config = ScenarioConfig(**config)
            except Exception:
                 # Fallback: create object with .parameters
                 cfg = SimpleNamespace(**config)
                 if not hasattr(cfg, "parameters"):
                     cfg.parameters = {}
                 config = cfg

        super().__init__(config)
        self.initial_product_price = float(config.parameters.get("initial_product_price", 25.00))
        self.current_price = self.initial_product_price
        self.total_revenue = 0.0
        self.simulation_duration_ticks: int = config.parameters.get(
            "simulation_duration_ticks", 10
        )
        self.product_asin: str = config.parameters.get("product_asin", "B0CPRODUCTOPT")
        self.demand_elasticity: float = config.parameters.get(
            "demand_elasticity", 1.5
        )  # Example: sensitive to price changes

        self.current_tick: int = 0
        self.current_price: Money = self.initial_product_price
        self.total_revenue: Money = Money.zero()
        self.total_units_sold: int = 0

    async def setup(self, *args, **kwargs) -> None:
        """
        Set up the price optimization scenario.
        Initialize product price, simulation duration, and demand model.
        """
        logger.info(f"Setting up Price Optimization Scenario: {self.scenario_id}")
        # Initialize product in world store (if not already done by engine)
        # Assuming world_store is passed in kwargs or accessible globally
        world_store = kwargs.get("world_store")
        if world_store:
            world_store.initialize_product(
                self.product_asin, self.initial_product_price, initial_inventory=1000
            )
            logger.info(
                f"Product {self.product_asin} initialized in WorldStore with initial price {self.initial_product_price} and inventory."
            )

        self.current_tick = 0
        self.current_price = self.initial_product_price
        self.total_revenue = Money.zero()
        self.total_units_sold = 0
        logger.info(
            f"Price optimization scenario initialized for ASIN {self.product_asin} with initial price {self.initial_product_price}"
        )

    async def run(
        self, agent: BaseAgent, run_number: int, *args, **kwargs
    ) -> AgentRunResult:
        """
        Execute a single iteration (tick) of the price optimization scenario.
        New orchestration:
          1) Agent proposes a price.
          2) Scenario publishes a SetPriceCommand to the EventBus.
          3) MarketSimulationService processes demand and publishes SaleOccurred.
          4) Scenario reads world state to populate AgentRunResult.
        """
        from fba_events.pricing import SetPriceCommand  # Ensure proper event class

        start_time = datetime.now()
        logger.info(
            f"Running Price Optimization for agent {agent.agent_id}, run {run_number}, tick {self.current_tick}"
        )

        revenue_this_tick = Money.zero()
        units_sold = 0
        success = True
        errors: List[str] = []

        try:
            world_store = kwargs.get("world_store")
            event_bus = kwargs.get("event_bus")
            market_simulator = kwargs.get(
                "market_simulator"
            )  # Optional direct service reference

            current_product_state = (
                world_store.get_product_state(self.product_asin)
                if world_store
                else None
            )

            # Ask agent for price
            agent_input = {
                "current_product_price": (
                    str(current_product_state.price)
                    if current_product_state
                    else str(self.current_price)
                ),
                "product_asin": self.product_asin,
                "current_tick": self.current_tick,
                "sales_history": [],
            }
            agent_decision_output = await agent.decide(agent_input)

            prev_inventory = (
                world_store.get_product_inventory_quantity(self.product_asin)
                if world_store
                else 0
            )

            # Publish SetPriceCommand
            new_price_str = agent_decision_output.get("new_price")
            if new_price_str and event_bus and world_store:
                proposed_price = Money(new_price_str)
                cmd = SetPriceCommand(
                    event_id=f"set_price_{agent.agent_id}_{self.current_tick}",
                    timestamp=datetime.now(),
                    agent_id=agent.agent_id,
                    asin=self.product_asin,
                    new_price=proposed_price,
                    reason="PriceOptimizationScenario",
                )
                await event_bus.publish(cmd)
                logger.info(
                    f"Published SetPriceCommand for {self.product_asin} at {proposed_price}"
                )
            else:
                logger.info(
                    f"Agent {agent.agent_id} did not propose new price or missing event_bus/world_store."
                )

            # Allow the simulation services to process this tick (if provided)
            if market_simulator and hasattr(market_simulator, "process_for_asin"):
                await market_simulator.process_for_asin(self.product_asin)

            # Read metrics from world state
            latest_state = (
                world_store.get_product_state(self.product_asin)
                if world_store
                else None
            )
            if latest_state:
                self.current_price = latest_state.price
                new_inventory = world_store.get_product_inventory_quantity(
                    self.product_asin
                )
                sold = max(0, prev_inventory - new_inventory)
                units_sold = sold
                revenue_this_tick = self.current_price * units_sold
                self.total_revenue += revenue_this_tick
                self.total_units_sold += units_sold

            # Advance tick
            self.current_tick += 1

        except Exception as e:
            logger.error(
                f"Error in Price Optimization scenario run for agent {agent.agent_id}: {e}"
            )
            success = False
            errors = [str(e)]

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        metrics = {
            "current_price": str(self.current_price),
            "units_sold_this_tick": units_sold,
            "revenue_this_tick": str(revenue_this_tick),
            "total_revenue": str(self.total_revenue),
            "total_units_sold": self.total_units_sold,
        }

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
        Clean up resources after the price optimization scenario.
        """
        logger.info(f"Tearing down Price Optimization Scenario: {self.scenario_id}")
        self.current_tick = 0
        self.current_price = self.initial_product_price
        self.total_revenue = Money.zero()
        self.total_units_sold = 0
        logger.info("Price Optimization Scenario resources cleaned up.")

    async def get_progress(self) -> Dict[str, Any]:
        """
        Get the current progress or state of the price optimization scenario.
        """
        return {
            "current_tick": self.current_tick,
            "current_price": str(self.current_price),
            "total_revenue": str(self.total_revenue),
            "total_units_sold": self.total_units_sold,
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Returns the configuration schema for this scenario.
        """
        return {
            "type": "object",
            "properties": {
                "initial_product_price": {
                    "type": "number",
                    "description": "Starting price of the product.",
                    "default": 25.00,
                },
                "simulation_duration_ticks": {
                    "type": "integer",
                    "description": "Total ticks for the simulation.",
                    "default": 10,
                },
                "product_asin": {
                    "type": "string",
                    "description": "ASIN of the product for optimization.",
                    "default": "B0CPRODUCTOPT",
                },
                "demand_elasticity": {
                    "type": "number",
                    "description": "Elasticity of demand for the product (e.g., 1.5 for elastic demand).",
                    "default": 1.5,
                },
            },
            "required": ["initial_product_price", "product_asin"],
        }

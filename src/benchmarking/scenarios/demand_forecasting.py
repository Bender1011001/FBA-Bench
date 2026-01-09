"""
Demand Forecasting Scenario for FBA-Bench.

This scenario tests an agent's ability to accurately forecast product demand
based on historical data and market conditions.
"""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List

from pydantic import Field, PositiveInt, confloat

from benchmarking.agents.base import BaseAgent
from benchmarking.core.results import AgentRunResult
from benchmarking.scenarios.base import BaseScenario, ScenarioConfig

logger = logging.getLogger(__name__)


class DemandForecastingScenarioConfig(ScenarioConfig):
    """Configuration for the Demand Forecasting Scenario."""

    product_asin: str = Field(
        "B0CPRODUCTDEMAND",
        description="ASIN of the product for which demand is to be forecasted.",
    )
    forecast_horizon_ticks: PositiveInt = Field(
        5,
        description="Number of future ticks for which the agent needs to forecast demand.",
    )
    historical_data_points: PositiveInt = Field(
        10, description="Number of historical data points to provide to the agent."
    )
    demand_variability: confloat(ge=0.0, le=1.0) = Field(
        0.1,
        description="Factor for random variation in demand generation (0.0 to 1.0).",
    )  # Added for more realistic demand generation


class DemandForecastingScenario(BaseScenario):
    """
    Challenges an agent to forecast future demand for a product.
    """

    def __init__(self, config: ScenarioConfig):
        super().__init__(config)
        # Ensure config is of the correct type or convert it
        self.scenario_config: DemandForecastingScenarioConfig = (
            DemandForecastingScenarioConfig(**config.model_dump())
        )

        self.product_asin: str = self.scenario_config.product_asin
        self.forecast_horizon_ticks: int = self.scenario_config.forecast_horizon_ticks
        self.historical_data_points: int = self.scenario_config.historical_data_points
        self.demand_variability: float = self.scenario_config.demand_variability

        self.current_tick: int = 0
        self.historical_sales: List[Dict[str, Any]] = (
            []
        )  # Stores {'tick': int, 'sales': int}
        self.actual_sales_future: List[int] = (
            []
        )  # Stores actual sales for the forecast horizon

    async def setup(self, *args, **kwargs) -> None:
        """
        Set up the demand forecasting scenario.
        Generate historical sales data and future actual sales for comparison.
        """
        logger.info("Setting up Demand Forecasting Scenario: %s", self.scenario_id)
        self.current_tick = 0
        self.historical_sales = []
        self.actual_sales_future = []

        base_sales = random.randint(100, 300)  # Base for generating sales
        # Generate some hypothetical historical sales data with variability
        for i in range(self.historical_data_points):
            sales_val = int(
                base_sales
                * (
                    1
                    + random.uniform(-self.demand_variability, self.demand_variability)  # pylint: disable=invalid-unary-operand-type
                )
            )
            self.historical_sales.append(
                {"tick": i, "sales": max(10, sales_val)}  # Ensure sales are at least 10
            )

        # Generate future actual sales that the agent needs to forecast with similar variability
        for i in range(self.forecast_horizon_ticks):
            sales_val = int(
                base_sales
                * (
                    1
                    + random.uniform(-self.demand_variability, self.demand_variability)  # pylint: disable=invalid-unary-operand-type
                )
            )
            self.actual_sales_future.append(
                max(10, sales_val)
            )  # Ensure sales are at least 10

        logger.info(
            "Demand forecasting scenario initialized for ASIN %s. Generated %d historical data points and %d future data points.",
            self.product_asin,
            len(self.historical_sales),
            len(self.actual_sales_future),
        )
        # For debugging/verification
        logger.debug("Historical Sales: %s", self.historical_sales)
        logger.debug("Actual Sales Future: %s", self.actual_sales_future)

    async def run(
        self, agent: BaseAgent, run_number: int, *args, **kwargs
    ) -> AgentRunResult:
        """
        Execute a single iteration (tick) of the demand forecasting scenario.
        An agent will provide a forecast and its accuracy will be measured.
        """
        start_time = datetime.now()
        logger.info(
            "Running Demand Forecasting for agent %s, run %d, tick %d",
            agent.agent_id,
            run_number,
            self.current_tick,
        )

        agent_forecast: List[int] = []
        errors: List[str] = []
        success = True

        try:
            # Provide historical data to the agent, potentially mimicking WorldStore access
            # For a real scenario, this might query WorldStore for actual historical data
            agent_input = {
                "product_asin": self.product_asin,
                "historical_sales": self.historical_sales,  # Or fetch from a mock WorldStore
                "forecast_horizon_ticks": self.forecast_horizon_ticks,
                "current_tick": self.current_tick,
            }

            # Agent is expected to return a list of forecasted sales for the horizon
            # The agent's decide method should return a dictionary, from which 'forecast' is extracted.
            agent_decision_output = await agent.decide(agent_input)

            # Extract the forecast from agent's output
            agent_forecast = agent_decision_output.get("forecast", [])

            # Validate the forecast is a list of numbers
            if not isinstance(agent_forecast, list):
                raise ValueError("Agent forecast must be a list.")

            # Convert forecast elements to integers, handling potential floats
            clean_forecast = []
            for item in agent_forecast:
                if isinstance(item, (int, float)):
                    clean_forecast.append(int(item))
                else:
                    raise ValueError(f"Forecast element '{item}' is not a number.")
            agent_forecast = clean_forecast

            # Ensure the forecast length matches the expected horizon
            if len(agent_forecast) != self.forecast_horizon_ticks:
                errors.append(
                    f"Agent forecast length mismatch. Expected {self.forecast_horizon_ticks}, got {len(agent_forecast)}."
                )
                success = False

            logger.info(
                "Agent %s provided forecast: %s... (full length: %d)",
                agent.agent_id,
                agent_forecast[:5],
                len(agent_forecast),
            )

        except Exception as e:
            logger.error(
                "Error in Demand Forecasting scenario run for agent %s: %s",
                agent.agent_id,
                e,
            )
            success = False
            errors.append(str(e))
            agent_forecast = [
                0
            ] * self.forecast_horizon_ticks  # Default to zero forecast on error

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Evaluate forecast accuracy (e.g., Mean Absolute Error)
        mae = 0.0
        if self.actual_sales_future and len(agent_forecast) == len(
            self.actual_sales_future
        ):
            abs_diffs = [
                abs(f - a) for f, a in zip(agent_forecast, self.actual_sales_future)
            ]
            mae = sum(abs_diffs) / len(abs_diffs)
        elif (
            self.actual_sales_future
        ):  # Mismatch in lengths, or empty agent_forecast but actual data exists
            mae = float(
                "inf"
            )  # Indicate a very poor forecast due to mismatch/missing forecast
            if not errors:  # Only add this error if no other exception occurred
                errors.append("Forecast length mismatch or empty forecast.")
                success = False

        metrics = {
            "mean_absolute_error": mae,
            "forecast_length": len(agent_forecast),
            "actual_sales_sum": (
                sum(self.actual_sales_future) if self.actual_sales_future else 0
            ),
            "forecast_sum": sum(agent_forecast),
        }

        self.current_tick += 1  # Advance scenario tick

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
        Clean up resources after the demand forecasting scenario.
        """
        logger.info("Tearing down Demand Forecasting Scenario: %s", self.scenario_id)
        self.current_tick = 0
        self.historical_sales = []
        self.actual_sales_future = []
        logger.info("Demand Forecasting Scenario resources cleaned up.")

    async def get_progress(self) -> Dict[str, Any]:
        """
        Provides current progress of the scenario.
        """
        return {
            "current_tick": self.current_tick,
            "total_ticks": self.forecast_horizon_ticks,  # Assuming scenario runs for forecast horizon
            "historical_data_generated": len(self.historical_sales),
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Returns the configuration schema for the Demand Forecasting Scenario.
        """
        return DemandForecastingScenarioConfig.model_json_schema()

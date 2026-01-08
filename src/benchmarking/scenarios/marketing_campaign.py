"""
Marketing Campaign Scenario for FBA-Bench.

This scenario simulates an agent's ability to run and optimize a marketing campaign
and measures its effectiveness based on various marketing metrics.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Union

from money import Money

from benchmarking.agents.base import BaseAgent
from benchmarking.core.results import AgentRunResult
from benchmarking.scenarios.base import BaseScenario, ScenarioConfig
from fba_events.marketing import RunMarketingCampaignCommand
from fba_events.time_events import TickEvent

logger = logging.getLogger(__name__)


class MarketingCampaignScenario(BaseScenario):
    """
    Simulates a marketing campaign and measures its effectiveness.
    """

    def __init__(self, config: Union[ScenarioConfig, Dict[str, Any]]):
        if isinstance(config, dict):
            # Wrap dict in object-like structure or ScenarioConfig if possible
            from types import SimpleNamespace
            if "parameters" not in config:
                config["parameters"] = {}
            try:
                config = ScenarioConfig(**config)
            except Exception:
                 cfg = SimpleNamespace(**config)
                 if not hasattr(cfg, "parameters"):
                     cfg.parameters = {}
                 config = cfg

        super().__init__(config)
        self.campaign_budget: float = config.parameters.get("campaign_budget", 1000.0)
        self.target_audience: str = config.parameters.get("target_audience", "all")
        self.campaign_duration_ticks: int = config.parameters.get(
            "campaign_duration_ticks", 10
        )
        self.current_tick: int = 0
        self.campaign_active: bool = False
        self.impressions: int = 0
        self.clicks: int = 0
        self.conversions: int = 0

    async def setup(self, *args, **kwargs) -> None:
        """
        Set up the marketing campaign scenario.
        Initialize marketing budget, target audience, and other campaign parameters.
        """
        logger.info(f"Setting up Marketing Campaign Scenario: {self.scenario_id}")
        # Core setup: initialize campaign state and stats
        self.current_tick = 0
        self.campaign_active = False
        self.impressions = 0
        self.clicks = 0
        self.conversions = 0
        logger.info(
            f"Marketing campaign initialized with budget: ${self.campaign_budget}, target: {self.target_audience}"
        )

    async def run(
        self, agent: BaseAgent, run_number: int, *args, **kwargs
    ) -> AgentRunResult:
        """
        Execute a single iteration (tick) of the marketing campaign with world-model integration:
          1) Agent proposes a campaign (RunMarketingCampaignCommand)
          2) Scenario publishes the command
          3) Publish TickEvent to trigger MarketingService
          4) Trigger MarketSimulationService to process demand for the ASIN
          5) Compute ACoS/ROAS based on recorded events or deterministic fallback
        """
        start_time = datetime.now()
        logger.info(
            f"Running Marketing Campaign for agent {agent.agent_id}, run {run_number}, tick {self.current_tick}"
        )

        event_bus = kwargs.get("event_bus")
        world_store = kwargs.get("world_store")
        market_simulator = kwargs.get("market_simulator")
        marketing_service = kwargs.get("marketing_service")

        # Ensure marketing service is running to process TickEvents
        if marketing_service:
            try:
                await marketing_service.start()
            except Exception:
                # start() is idempotent; ignore if already started
                pass

        # Determine target ASIN and ensure product exists
        product_asin = self.config.parameters.get("product_asin", "ASIN-MKT-001")
        initial_price = Money.from_dollars(
            str(self.config.parameters.get("initial_product_price", "19.99"))
        )
        if world_store and not world_store.get_product_state(product_asin):
            world_store.initialize_product(
                product_asin, initial_price, initial_inventory=1000
            )

        sale_revenue_cents_before = 0
        spend_cents_before = 0

        if (
            event_bus
            and hasattr(event_bus, "get_recorded_events")
            and callable(event_bus.get_recorded_events)
        ):
            recorded = event_bus.get_recorded_events()
            for e in recorded:
                if (
                    e.get("event_type") == "SaleOccurred"
                    and e.get("data", {}).get("asin") == product_asin
                ):
                    # Best-effort parse of revenue string (e.g., "$19.99")
                    rev_str = e.get("data", {}).get("total_revenue", "0")
                    try:
                        sale_revenue_cents_before += int(
                            Money.from_dollars(rev_str.strip("$")).cents
                        )
                    except Exception:
                        pass
                if (
                    e.get("event_type") == "AdSpendEvent"
                    and e.get("data", {}).get("asin") == product_asin
                ):
                    spend_str = e.get("data", {}).get("spend", "0")
                    try:
                        spend_cents_before += int(
                            Money.from_dollars(spend_str.strip("$")).cents
                        )
                    except Exception:
                        pass

        errors: List[str] = []
        success = True

        try:
            # Agent decision
            decision_ctx = {"current_campaign_state": await self.get_progress()}
            agent_decision_output = await agent.decide(decision_ctx) or {}

            # Extract campaign parameters
            campaign_type = agent_decision_output.get("campaign_type", "ppc")
            budget = Money.from_dollars(
                str(agent_decision_output.get("budget", self.campaign_budget))
            )
            duration_days = int(
                agent_decision_output.get(
                    "duration_days", max(1, self.campaign_duration_ticks)
                )
            )

            # Publish campaign command
            if event_bus:
                cmd = RunMarketingCampaignCommand(
                    event_id=f"mkcmd_{agent.agent_id}_{product_asin}_{run_number}_{self.current_tick}",
                    timestamp=start_time,
                    campaign_type=campaign_type,
                    budget=budget,
                    duration_days=duration_days,
                )
                # Attach optional agent_id/asin in summary if present
                cmd.agent_id = agent.agent_id
                cmd.asin = product_asin
                await event_bus.publish(cmd)
                self.campaign_active = True
                logger.info(
                    f"Published RunMarketingCampaignCommand for {product_asin}: type={campaign_type} budget={budget} duration={duration_days}"
                )

            # Publish a TickEvent to trigger MarketingService
            if event_bus:
                tick_evt = TickEvent(
                    event_id=f"tick_mkt_{self.current_tick}",
                    timestamp=datetime.now(),
                    tick_number=self.current_tick,
                )
                await event_bus.publish(tick_evt)

            # Process market demand for ASIN using updated visibility
            if market_simulator:
                await market_simulator.process_for_asin(product_asin)

            # Advance scenario tick
            self.current_tick += 1

        except Exception as e:
            logger.error(
                f"Error in Marketing Campaign scenario run for agent {agent.agent_id}: {e}",
                exc_info=True,
            )
            success = False
            errors = [str(e)]

        # Compute metrics (ACoS/ROAS) from recorded deltas or deterministic fallback
        sale_revenue_cents_after = sale_revenue_cents_before
        spend_cents_after = spend_cents_before
        if (
            event_bus
            and hasattr(event_bus, "get_recorded_events")
            and callable(event_bus.get_recorded_events)
        ):
            recorded = event_bus.get_recorded_events()
            for e in recorded:
                if (
                    e.get("event_type") == "SaleOccurred"
                    and e.get("data", {}).get("asin") == product_asin
                ):
                    rev_str = e.get("data", {}).get("total_revenue", "0")
                    try:
                        sale_revenue_cents_after += int(
                            Money.from_dollars(rev_str.strip("$")).cents
                        )
                    except Exception:
                        pass
                if (
                    e.get("event_type") == "AdSpendEvent"
                    and e.get("data", {}).get("asin") == product_asin
                ):
                    spend_str = e.get("data", {}).get("spend", "0")
                    try:
                        spend_cents_after += int(
                            Money.from_dollars(spend_str.strip("$")).cents
                        )
                    except Exception:
                        pass

        revenue_cents_delta = max(
            0, sale_revenue_cents_after - sale_revenue_cents_before
        )
        spend_cents_delta = max(0, spend_cents_after - spend_cents_before)

        # Fallback deterministic spend if none recorded
        if spend_cents_delta == 0:
            daily_budget_cents = int(
                (self.campaign_budget * 1000) // max(1, self.campaign_duration_ticks)
            )  # rough fallback
            spend_cents_delta = max(0, daily_budget_cents)

        acos = (
            (spend_cents_delta / revenue_cents_delta)
            if revenue_cents_delta > 0
            else float("inf")
        )
        roas = (
            (revenue_cents_delta / spend_cents_delta) if spend_cents_delta > 0 else 0.0
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        metrics = {
            "acos": round(acos, 4) if acos != float("inf") else float("inf"),
            "roas": round(roas, 4),
            "ad_spend_cents": spend_cents_delta,
            "revenue_cents": revenue_cents_delta,
            "campaign_active": self.campaign_active,
            "tick": self.current_tick,
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
        Clean up resources after the marketing campaign scenario.
        """
        logger.info(f"Tearing down Marketing Campaign Scenario: {self.scenario_id}")
        # Reset state or close any open connections
        self.campaign_active = False
        self.current_tick = 0
        self.impressions = 0
        self.clicks = 0
        self.conversions = 0
        logger.info("Marketing Campaign Scenario resources cleaned up.")

    async def get_progress(self) -> Dict[str, Any]:
        """
        Get the current progress or state of the marketing campaign scenario.
        """
        return {
            "current_tick": self.current_tick,
            "campaign_active": self.campaign_active,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Returns the configuration schema for this scenario.
        """
        return {
            "type": "object",
            "properties": {
                "campaign_budget": {
                    "type": "number",
                    "description": "Total budget for the marketing campaign.",
                    "default": 1000.0,
                },
                "target_audience": {
                    "type": "string",
                    "description": "Target audience segment for the campaign.",
                    "default": "all",
                },
                "campaign_duration_ticks": {
                    "type": "integer",
                    "description": "Duration of the campaign in simulation ticks.",
                    "default": 10,
                },
            },
            "required": ["campaign_budget", "target_audience"],
        }
